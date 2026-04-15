# env:conda activate Vicon_SDK
import numpy as np
import pandas as pd
import serial
import time
import csv
import tkinter as tk
from threading import Thread, Lock
from scipy.spatial.transform import Rotation as R
import vicon_dssdk.ViconDataStream as VDS

# ==================== 全局参数配置 ====================
PORT = 'COM12'                     
BAUDRATE = 460800                  
TIMEOUT = 0.1
FRAME_HEAD = b'\x55'               
FRAME_TOTAL_LEN = 29               

VICON_HOST_IP = "192.168.137.201:801"

IMU_DICT = {
    0x09: "Trunk",    0x0A: "L_Femur", 0x0B: "L_Tibia", 0x0C: "L_Foot",
    0x0D: "R_Femur",  0x0E: "R_Tibia", 0x0F: "R_Foot"
}
IMU_NAMES = list(IMU_DICT.values())

# VICON_SEGS = ['Root', 'L_Femur', 'L_Tibia', 'L_Foot', 'R_Femur', 'R_Tibia', 'R_Foot']
def get_vicon_segs():
    temp_client=VDS.Client()
    temp_client.Connect(VICON_HOST_IP)
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
        
# ==================== CSV 写入模块 ====================
class CSV_Writer:
    def __init__(self, vicon_segs, imu_names):    
        current_time = time.strftime("%Y%m%d_%H%M%S")
        self.filename = f"subject_trial_{current_time}.csv"
        
        self.headers = ['Timestamp', 'Vicon_Frame_Num']
        for seg in vicon_segs:
            self.headers.extend([f"Vicon_{seg}_X", f"Vicon_{seg}_Y", f"Vicon_{seg}_Z"])

        for seg in imu_names:
            self.headers.extend([f"IMU_{seg}_Acc_X", f"IMU_{seg}_Acc_Y", f"IMU_{seg}_Acc_Z"])
            self.headers.extend([f"IMU_{seg}_Gyro_X", f"IMU_{seg}_Gyro_Y", f"IMU_{seg}_Gyro_Z"])
            self.headers.extend([f"IMU_{seg}_Roll", f"IMU_{seg}_Pitch", f"IMU_{seg}_Yaw"])
            self.headers.extend([f"IMU_{seg}_Quat_x", f"IMU_{seg}_Quat_y", f"IMU_{seg}_Quat_z", f"IMU_{seg}_Quat_w"])

        with open(self.filename, mode='w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(self.headers)
        print(f'✅ CSV 文件已创建: {self.filename}')

    def append_row(self, current_time, vicon_frame, vicon_data, imu_data):
        row_data = [current_time, vicon_frame]

        for seg in VICON_SEGS:
            coords = vicon_data.get(seg, {"X": 0.0, "Y": 0.0, "Z": 0.0})
            row_data.extend([coords['X'], coords['Y'], coords['Z']])

        for seg in IMU_NAMES:
            d = imu_data[seg]
            row_data.extend([
                d["Acc"]["X"], d["Acc"]["Y"], d["Acc"]["Z"],
                d["Gyro"]["X"], d["Gyro"]["Y"], d["Gyro"]["Z"],
                d["Euler"]["Roll"], d["Euler"]["Pitch"], d["Euler"]["Yaw"],
                d["Quat"]["x"], d["Quat"]["y"], d["Quat"]["z"], d["Quat"]["w"]
            ])

        with open(self.filename, mode='a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(row_data)

# ==================== Vicon 接收模块 ====================
class Vicon_Thread(Thread):
    def __init__(self, host_ip, seg_ids):
        super().__init__()
        self.host_ip = host_ip
        self.seg_ids = seg_ids
        self.seg_data = {seg: {"X": 0.0, "Y": 0.0, "Z": 0.0} for seg in self.seg_ids}
        self.current_frame_num = 0
        self.data_lock = Lock()
        self.is_running = True
        
        self.client = VDS.Client()
        self.client.Connect(host_ip)
        self.client.EnableSegmentData()
        
        if self.client.IsConnected():
            print('✅ Vicon 连接成功')
        try:
            self.client.SetStreamMode(0)
        except:
            pass

    def get_latest_data(self):
        with self.data_lock:
            return self.current_frame_num, self.seg_data.copy()

    def run(self):
        try:
            while self.is_running:
                if self.client.GetFrame():
                    frame_num = self.client.GetFrameNumber()
                    subjects = self.client.GetSubjectNames()
                    if subjects:
                        subject_name = subjects[0]
                        temp_data = {}
                        for seg in self.seg_ids:
                            # res = self.client.GetSegmentGlobalTranslation(subject_name, seg)
                            pos,occluded = self.client.GetSegmentGlobalTranslation(subject_name, seg)   
                            # if res[0] == 1 and not res[2]:
                                # temp_data[seg] = {"X": res[1][0], "Y": res[1][1], "Z": res[1][2]}
                            if not occluded:
                                temp_data[seg]={"X": pos[0], "Y": pos[1], "Z": pos[2]}
                            else:
                                temp_data[seg] = self.seg_data[seg]
                        
                        with self.data_lock:
                            self.current_frame_num = frame_num
                            self.seg_data.update(temp_data)
                time.sleep(0.001) # Vicon 线程极速轮询
        finally:
            self.client.Disconnect()

    def stop(self):
        self.is_running = False

# ==================== IMU 接收模块 ====================
class IMU_Thread(Thread):
    def __init__(self, port, baudrate, timeout):
        super().__init__()
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.is_running = True
        self.ser = None
        self.data_lock = Lock()
        
        self.imu_data = {
            name: {
                "Acc": {"X": 0.0, "Y": 0.0, "Z": 0.0},
                "Gyro": {"X": 0.0, "Y": 0.0, "Z": 0.0},
                "Euler": {"Roll": 0.0, "Pitch": 0.0, "Yaw": 0.0},
                "Quat": {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0}
            } for name in IMU_NAMES
        }
        
    def to_signed_short(self, raw):
        return raw if raw <= 0x7FFF else raw - 0x10000

    def parse_frame(self, frame):
        dev_id = frame[0]
        flag = frame[2]
        
        if dev_id in IMU_DICT and flag == 0x61:
            name = IMU_DICT[dev_id]
            ax, ay, az = self.to_signed_short((frame[4]<<8)|frame[3]), self.to_signed_short((frame[6]<<8)|frame[5]), self.to_signed_short((frame[8]<<8)|frame[7])
            gx, gy, gz = self.to_signed_short((frame[10]<<8)|frame[9]), self.to_signed_short((frame[12]<<8)|frame[11]), self.to_signed_short((frame[14]<<8)|frame[13])
            r, p, y = self.to_signed_short((frame[22]<<8)|frame[21]), self.to_signed_short((frame[24]<<8)|frame[23]), self.to_signed_short((frame[26]<<8)|frame[25])

            roll_deg = round((r / 32768) * 180, 4)
            pitch_deg = round((p / 32768) * 180, 4)
            yaw_deg = round((y / 32768) * 180, 4)

            rot = R.from_euler('zyx', [yaw_deg, pitch_deg, roll_deg], degrees=True)
            quat = rot.as_quat()
            quat = quat / np.linalg.norm(quat)

            with self.data_lock:
                self.imu_data[name]["Acc"] = {"X": round((ax/32768)*16*9.8, 4), "Y": round((ay/32768)*16*9.8, 4), "Z": round((az/32768)*16*9.8, 4)}
                self.imu_data[name]["Gyro"] = {"X": round((gx/32768)*2000, 4), "Y": round((gy/32768)*2000, 4), "Z": round((gz/32768)*2000, 4)}
                self.imu_data[name]["Euler"] = {"Roll": roll_deg, "Pitch": pitch_deg, "Yaw": yaw_deg}
                self.imu_data[name]["Quat"] = {"x": round(quat[0], 4), "y": round(quat[1], 4), "z": round(quat[2], 4), "w": round(quat[3], 4)}

    def get_latest_data(self):
        with self.data_lock:
            return self.imu_data.copy()

    def run(self):
        try:
            self.ser = serial.Serial(self.port, self.baudrate, timeout=self.timeout)
            self.ser.set_buffer_size(rx_size=10240) 
            print(f'✅ IMU 串口已打开: {self.port}')
        except Exception as e:
            print(f'❌ IMU 串口打开失败: {e}')
            return

        raw_buffer = b""
        try:
            while self.is_running:
                if self.ser.in_waiting > 0:
                    raw_buffer += self.ser.read(self.ser.in_waiting)
                    if len(raw_buffer) > 5000:
                        raw_buffer = raw_buffer[-1000:]

                    while True:
                        head_idx = raw_buffer.find(FRAME_HEAD)
                        if head_idx == -1: break
                        if head_idx > 0:
                            start_idx = head_idx - 1
                            end_idx = start_idx + FRAME_TOTAL_LEN
                            if end_idx <= len(raw_buffer):
                                frame = raw_buffer[start_idx:end_idx]
                                if frame[1] == 0x55: 
                                    self.parse_frame(frame)
                                raw_buffer = raw_buffer[end_idx:]
                                continue
                            else: break
                        else: raw_buffer = raw_buffer[1:]
                time.sleep(0.001)
        finally:
            if self.ser and self.ser.is_open:
                self.ser.close()

    def stop(self):
        self.is_running = False

# ==================== GUI 控制与高精度采样线程 ====================
class MainApp:
    def __init__(self):
        # 1. 启动硬件监听线程（一直在后台跑，更新最新数据）
        self.vicon_thread = Vicon_Thread(VICON_HOST_IP, VICON_SEGS)
        self.imu_thread = IMU_Thread(PORT, BAUDRATE, TIMEOUT)
        self.vicon_thread.start()
        self.imu_thread.start()

        # 2. 状态控制
        self.is_recording = False
        self.record_thread = None
        self.csv_writer = None

        # 3. 创建 GUI
        self.root = tk.Tk()
        self.root.title("Vicon+IMU 同步采集系统")
        self.root.geometry("300x150")

        self.status_label = tk.Label(self.root, text="状态: 待机中 (硬件已连接)", font=("Arial", 12), fg="blue")
        self.status_label.pack(pady=15)

        self.btn_start = tk.Button(self.root, text="▶ 开始记录", command=self.start_record, bg="green", fg="white", font=("Arial", 12, "bold"))
        self.btn_start.pack(side=tk.LEFT, padx=20)

        self.btn_stop = tk.Button(self.root, text="⏹ 停止记录", command=self.stop_record, bg="red", fg="white", font=("Arial", 12, "bold"), state=tk.DISABLED)
        self.btn_stop.pack(side=tk.RIGHT, padx=20)

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def start_record(self):
        self.is_recording = True
        self.btn_start.config(state=tk.DISABLED)
        self.btn_stop.config(state=tk.NORMAL)
        self.status_label.config(text="状态: 正在记录数据 (200Hz)...", fg="green")
        
        # 实例化 CSV 写入器，开始新文件
        self.csv_writer = CSV_Writer(VICON_SEGS, IMU_NAMES)
        
        # 启动高精度定时拉取线程
        self.record_thread = Thread(target=self.precise_recording_loop)
        self.record_thread.start()

    def stop_record(self):
        self.is_recording = False
        if self.record_thread:
            self.record_thread.join()
        
        self.btn_start.config(state=tk.NORMAL)
        self.btn_stop.config(state=tk.DISABLED)
        self.status_label.config(text="状态: 记录已保存，待机中", fg="blue")
        print("✅ 数据已安全保存。")

    def precise_recording_loop(self):
        # 目标采集间隔 (5ms = 200Hz)
        interval = 0.005 
        next_time = time.perf_counter()

        while self.is_recording:
            # 1. 抓取瞬时数据
            v_frame, v_data = self.vicon_thread.get_latest_data()
            i_data = self.imu_thread.get_latest_data()
            current_timestamp = time.time() # 记录绝对物理时间

            # 2. 写入数据
            self.csv_writer.append_row(current_timestamp, v_frame, v_data, i_data)

            # 3. 高精度对齐 (微秒级等待，补齐 5ms)
            next_time += interval
            sleep_time = next_time - time.perf_counter()
            if sleep_time > 0:
                # 留出 1ms 给系统级 sleep，剩下极小时间用空循环自旋以确保极高精度
                if sleep_time > 0.001:
                    time.sleep(sleep_time - 0.001)
                while time.perf_counter() < next_time:
                    pass 

    def on_close(self):
        print("🛑 正在关闭所有硬件连接...")
        self.is_recording = False
        self.vicon_thread.stop()
        self.imu_thread.stop()
        self.vicon_thread.join()
        self.imu_thread.join()
        self.root.destroy()
        print("✅ 系统已完全退出。")

if __name__ == '__main__':
    app = MainApp()
    app.root.mainloop()