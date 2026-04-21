# ==================== ✅ 修改说明 ====================
# 1. ✅ 引入 Vicon 数据队列（避免覆盖丢帧）
# 2. ✅ CSV 改为“常驻文件 + 批量写入”
# 3. ✅ 删除 busy-wait 自旋
# 4. ✅ 删除 Vicon 线程 sleep 限速
# 5. ✅ 降低锁粒度
# ================================================

print("1. 程序开始启动...")

import socket
import numpy as np
import pandas as pd
import serial
import time
import csv
import tkinter as tk
from threading import Thread, Lock
from collections import deque  # ✅ 新增
from scipy.spatial.transform import Rotation as R

import vicon_dssdk.ViconDataStream as VDS

# ==================== 参数 ====================
PORT = 'COM12'
BAUDRATE = 460800
TIMEOUT = 0.1
FRAME_HEAD = b'\x55'
FRAME_TOTAL_LEN = 29

VICON_HOST_IP = "192.168.137.157"

IMU_DICT = {
    0x09: "Trunk", 0x0A: "L_Femur", 0x0B: "L_Tibia", 0x0C: "L_Foot",
    0x0D: "R_Femur", 0x0E: "R_Tibia", 0x0F: "R_Foot"
}
IMU_NAMES = list(IMU_DICT.values())

def get_vicon_segs():
    print("--- 准备连接 Vicon，目标 IP:", VICON_HOST_IP)
    temp_client=VDS.Client()
    print("--- 正在尝试执行 Connect (这里可能会卡住10秒)...")
    temp_client.Connect(VICON_HOST_IP)
    print("--- Connect 执行完毕！是否真的连上了？", temp_client.IsConnected())
    temp_client.EnableSegmentData()

    try:
        temp_client.SetStreamMode(0)
    except:
        pass
    
    segs=[]
    for _ in range(10):
        if temp_client.GetFrame():
            subjects=temp_client.GetSubjectNames()
            if subjects:
                s_name=subjects[0]
                print(s_name)
                segs=temp_client.GetSegmentNames(s_name)
                seg_1=segs[1]
                
                pos, occluded = temp_client.GetSegmentGlobalTranslation(s_name,seg_1)
                print(f"{seg_1}")
                print((pos, occluded))
                
                if not occluded:
                    print(f"{seg_1}: X:{pos[0]:.2f}, Y: {pos[1]:.2f}, Z: {pos[2]:.2f}")
                
        time.sleep(0.1)

    temp_client.Disconnect()
    print(segs)
    return segs

VICON_SEGS=get_vicon_segs()

def get_vicon_markers():
    temp_client = VDS.Client()
    temp_client.Connect(VICON_HOST_IP)
    temp_client.EnableMarkerData()

    try:
        temp_client.SetStreamMode(0)
    except:
        pass

    markers = []
    for _ in range(10):
        if temp_client.GetFrame():
            subjects = temp_client.GetSubjectNames()
            if subjects:
                s_name = subjects[0]
                print(f"获取到 subject: {s_name}")
                
                # 1. 获取原始数据
                raw_markers = temp_client.GetMarkerNames(s_name)
                
                # 2. 兼容性解析（提取纯字符串）
                temp_markers = []
                # 情况 A: 如果返回的是 (Result, [markers_list])
                if isinstance(raw_markers, tuple) and len(raw_markers) == 2 and isinstance(raw_markers[1], list):
                    raw_list = raw_markers[1]
                else:
                    raw_list = raw_markers

                # 情况 B: 如果列表里包含的是元组，如 [('Marker1', 'Parent'), ...]
                for m in raw_list:
                    if isinstance(m, tuple) or isinstance(m, list):
                        temp_markers.append(m[0]) # 提取真正的 marker 名字
                    else:
                        temp_markers.append(m)    # 本身就是纯字符串
                
                markers = temp_markers
                
                if markers:
                    marker_1 = markers[0]
                    pos, occluded = temp_client.GetMarkerGlobalTranslation(s_name, marker_1)
                    print(f"{marker_1}")
                    print((pos, occluded))
                    
                    if not occluded:
                        print(f"{marker_1}: X:{pos[0]:.2f}, Y: {pos[1]:.2f}, Z: {pos[2]:.2f}")
                
        time.sleep(0.1)

    temp_client.Disconnect()
    print("✅ 解析成功的纯 Marker 列表:", markers)
    return markers

VICON_MARKERS=get_vicon_markers()


# ==================== CSV 写入（优化） ====================
class CSV_Writer:
    def __init__(self, vicon_segs, vicon_markers, imu_names):
        current_time = time.strftime("%Y%m%d_%H%M%S")
        self.filename = f"subject_trial_{current_time}.csv"

        self.file = open(self.filename, 'w', newline='')  # ✅ 常驻文件
        self.writer = csv.writer(self.file)
        self.buffer = []  # ✅ 批量缓存

        self.headers = ['Timestamp', 'Vicon_Frame_Num']
        for seg in vicon_segs:
            self.headers.extend([f"Vicon_{seg}_X", f"Vicon_{seg}_Y", f"Vicon_{seg}_Z"])

        for marker in vicon_markers:
            self.headers.extend([f"Vicon_{marker}_X", f"Vicon_{marker}_Y", f"Vicon_{marker}_Z"])

        for seg in imu_names:
            self.headers.extend([f"IMU_{seg}_Acc_X", f"IMU_{seg}_Acc_Y", f"IMU_{seg}_Acc_Z"])

        self.writer.writerow(self.headers)

    def append_row(self, row_data):
        self.buffer.append(row_data)

        if len(self.buffer) >= 50:  # ✅ 批量写
            self.writer.writerows(self.buffer)
            self.buffer.clear()

    def close(self):
        if self.buffer:
            self.writer.writerows(self.buffer)
        self.file.close()

# ==================== Vicon 线程（核心优化） ====================
class Vicon_Thread(Thread):
    def __init__(self, host_ip, seg_ids, marker_ids):
        super().__init__()
        self.client = VDS.Client()
        self.client.Connect(host_ip)
        self.client.EnableSegmentData()
        self.client.EnableMarkerData()

        self.seg_ids = seg_ids
        self.marker_ids = marker_ids

        self.buffer = deque(maxlen=10000)  # ✅ 队列缓存
        self.lock = Lock()
        self.is_running = True

    def run(self):
        while self.is_running:
            if self.client.GetFrame():
                frame_num = self.client.GetFrameNumber()
                subjects = self.client.GetSubjectNames()
                if not subjects:
                    continue

                subject = subjects[0]

                seg_data = {}
                marker_data = {}

                for seg in self.seg_ids:
                    pos, occluded = self.client.GetSegmentGlobalTranslation(subject, seg)
                    if not occluded:
                        seg_data[seg] = pos

                for marker in self.marker_ids:
                    pos, occluded = self.client.GetMarkerGlobalTranslation(subject, marker)
                    if not occluded:
                        marker_data[marker] = pos

                # ✅ 最小锁时间
                with self.lock:
                    self.buffer.append((frame_num, seg_data, marker_data))

        self.client.Disconnect()

    def get_data(self):
        with self.lock:
            if self.buffer:
                return self.buffer.popleft()  # ✅ 不再覆盖
            else:
                return None

    def stop(self):
        self.is_running = False

# ==================== IMU（基本保持） ====================
class IMU_Thread(Thread):
    def __init__(self, port, baudrate, timeout):
        super().__init__()
        self.ser = serial.Serial(port, baudrate, timeout=timeout)
        self.lock = Lock()
        self.is_running = True

        self.imu_data = {name: {"Acc": {"X":0,"Y":0,"Z":0}} for name in IMU_NAMES}

    def run(self):
        while self.is_running:
            if self.ser.in_waiting:
                self.ser.read(self.ser.in_waiting)

    def get_latest_data(self):
        with self.lock:
            return self.imu_data.copy()

    def stop(self):
        self.is_running = False

# ==================== 主程序 ====================
class MainApp:
    def __init__(self):
        self.vicon = Vicon_Thread(VICON_HOST_IP, VICON_SEGS, VICON_MARKERS)
        self.imu = IMU_Thread(PORT, BAUDRATE, TIMEOUT)

        self.vicon.start()
        self.imu.start()

        self.writer = CSV_Writer(VICON_SEGS, VICON_MARKERS, IMU_NAMES)
        self.is_running = True

        self.thread = Thread(target=self.loop)
        self.thread.start()

    def loop(self):
        interval = 0.01

        while self.is_running:
            data = self.vicon.get_data()

            if data:
                frame, seg, marker = data
                imu = self.imu.get_latest_data()

                row = [time.time(), frame]
                for seg_name in self.vicon.seg_ids:
                    pos = seg.get(seg_name, (0.0, 0.0, 0.0))
                    row.extend([pos[0], pos[1], pos[2]])

                # -------- Vicon Marker --------
                for marker_name in self.vicon.marker_ids:
                    pos = marker.get(marker_name, (0.0, 0.0, 0.0))
                    row.extend([pos[0], pos[1], pos[2]])

                # -------- IMU --------
                for imu_name in IMU_NAMES:
                    d = imu[imu_name]
                    row.extend([
                        d["Acc"]["X"], d["Acc"]["Y"], d["Acc"]["Z"],
                        d["Gyro"]["X"], d["Gyro"]["Y"], d["Gyro"]["Z"],
                        d["Euler"]["Roll"], d["Euler"]["Pitch"], d["Euler"]["Yaw"],
                        d["Quat"]["x"], d["Quat"]["y"], d["Quat"]["z"], d["Quat"]["w"]
                    ])

                self.writer.append_row(row)


                self.writer.append_row(row)

            time.sleep(interval)  # ✅ 替代 busy-wait

    def stop(self):
        self.is_running = False
        self.thread.join()
        self.vicon.stop()
        self.imu.stop()
        self.writer.close()


if __name__ == '__main__':
    app = MainApp()
    time.sleep(10)
    app.stop()
