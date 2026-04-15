# env:conda activate Vicon_SDK
# base
import numpy as np
import pandas as pd
import serial
import time
import csv
import tkinter as tk
from threading import Thread,Lock
from scipy.spatial.transform import Rotation as R

# vicon_sdk_data
import vicon_dssdk.ViconDataStream as VDS

# ===IMU协议固定参数===

PORT = 'COM12'                     # IMU COM口
BAUDRATE = 460800                  
TIMEOUT = 0.1
FRAME_HEAD = b'\x55'               # 数据包头（0x55）
FRAME_TOTAL_LEN = 29               # 所有RF帧总长度均为29字节
DEVICE_ID_OFFSET = 0               # 设备号偏移：第0字节
DATA_HEAD_OFFSET = 1               # 数据包头偏移：第1字节
FLAG_OFFSET = 2                    # 标志位偏移：第2字节

# 各编号数据对应的部位
# 02-上身 03-左大腿 04-左小腿 05-左脚背
# 06-右大腿 07-右小腿 08-右脚背
# IMU 设备号到英文部位的映射
# 设备有02-08 | 09-15 两套编号
IMU_DICT = {
    0x09: "Trunk",    0x0A: "L_Femur", 0x0B: "L_Tibia", 0x0C: "L_Foot",
    0x0D: "R_Femur",  0x0E: "R_Tibia", 0x0F: "R_Foot"
}
IMU_NAMES = list(IMU_DICT.values())

# 支持的Flag类型
FLAG_ACC_GYRO_MAG_ANGLE = 0x61     # 加速度+角速度+角度

# ===Vicon_SDK设置参数===
VICON_HOST_IP = "192.168.137.201:801"  # Vicon主机上的端口，在同一无线网络中的 IPv4 地址；xxx.xxx.xxx.xxx:801
'''
def get_vicon_segs(client):
    # 获取subject
    subject_count=client.GetSubjectCount()
    if subject_count==0:
        print("no subject")

    subject_info=client.GetSubjectName(0)

    if isinstance(subject_info,tuple):
        subject_name=subject_info[1]
    else:
        subject_name=subject_info

    segs_info = client.GetSegmentNames(subject_name)

    if isinstance(segs_info, tuple):
        segs = segs_info[1]
    else:
        segs = segs_info

    return subject_name,segs
'''
def get_vicon_segs(client):
    """获取第一个 Subject 的名称及其所有 Segment 名称"""
    # SDK 1.13 习惯用法：必须先 GetFrame 才能获取内容
    client.GetFrame() 
# 修复位置：改用 GetSubjectNames() 获取列表
    subjects = client.GetSubjectNames() 
    
    if not subjects:
        print("Error: No subjects found.")
        return None, []

    # 直接取第一个 subject 的名字
    subject_name = subjects[0]
    
    # 获取该 subject 下的所有 segment
    segs = client.GetSegmentNames(subject_name)

    return subject_name, segs

# ————————————————CSV写入模块——————————————  
class CSV_Writer:
    def __init__(self,vicon_segs,imu_names):    
        # 动态生成文件名
        current_time=time.strftime("%Y%m%d_%H%M%S")
        self.filename=f"subject_trial_{current_time}.csv"
        self.vicon_segs=vicon_segs

        # 动态表头
        self.headers=['Timestamp','Vicon_Frame_Num']

        # 添加Vicon部位表头
        for seg in vicon_segs:
            self.headers.extend([f"{seg}_X", f"{seg}_Y", f"{seg}_Z"])

        # 添加IMU部位表头
        for name in imu_names:
            # 1. 加速度 (Acc)
            self.headers.extend([f"{name}_Acc_X", f"{name}_Acc_Y", f"{name}_Acc_Z"])
            # 2. 角速度 (Gyro)
            self.headers.extend([f"{name}_Gyro_X", f"{name}_Gyro_Y", f"{name}_Gyro_Z"])
            # 3. 欧拉角 (Euler)
            self.headers.extend([f"{name}_Roll", f"{name}_Pitch", f"{name}_Yaw"])
            # 4. 四元数 (Quat)
            self.headers.extend([f"{name}_Quat_x", f"{name}_Quat_y", f"{name}_Quat_z", f"{name}_Quat_w"])            

        # 创建并初始化CSV文件
        self.file=open(self.filename,mode='w',newline='')
        self.writer=csv.writer(self.file)
        self.writer.writerow(self.headers)
        self.file.flush()
        
        print(f'CSV Writer: {self.filename} ')

    def append_row(self,current_time,vicon_frame,vicon_data,imu_data):
        # 记录写入时的时间戳
        row_data=[current_time,vicon_frame]

        # 按表头顺序提取Vicon数据
        for seg in self.vicon_segs:
            coords=vicon_data.get(seg,{"X":0.0,"Y":0.0,"Z":0.0})
            row_data.extend([coords['X'],coords['Y'],coords['Z']])

        # 按表头顺序提取imu数据
        for name in IMU_NAMES:
            data=imu_data[name]

            row_data.extend([data["Acc"]["X"], data["Acc"]["Y"], data["Acc"]["Z"]])
            row_data.extend([data["Gyro"]["X"], data["Gyro"]["Y"], data["Gyro"]["Z"]])
            row_data.extend([data["Euler"]["Roll"], data["Euler"]["Pitch"], data["Euler"]["Yaw"]])
            row_data.extend([data["Quat"]["x"], data["Quat"]["y"], data["Quat"]["z"], data["Quat"]["w"]])

        self.writer.writerow(row_data)

# ————————————————vicon数据接受模块——————————————
class Vicon_Thread(Thread):
    def __init__(self,host_ip,seg_ids):
        super().__init__()
        self.host_ip=host_ip
        self.seg_ids=seg_ids

        # 连接客户端
        self.client=VDS.Client()
        self.client.Connect(host_ip)
        self.client.EnableSegmentData()
        self.client.SetStreamMode(0)

        # 初始化数据字典
        self.seg_data={seg: {"X": 0.0, "Y": 0.0, "Z": 0.0} for seg in self.seg_ids}
        self.current_frame_num=0
        self.data_lock=Lock()
        self.is_running=True

        # 检查连接状态
        # 检查帧率
        if self.client.IsConnected():
            print('connect to Vicon successfully')
            print(f'FrameRate: {self.client.GetFrameRate()} Hz')
        else:
            print('check out connection')

        try:
            self.client.SetStreamMode(0)
        except Exception as e:
            print('Vicon_Thread fail to set stream')

    def get_latest_data(self):
        with self.data_lock:
            return self.current_frame_num, self.seg_data.copy()

    def run(self):
        try:
            while self.is_running:
                if self.client.GetFrame()==1:
                    frame_num=self.client.GetFrameNumber()
                    subject_count=self.client.GetSubjectCount()
                    if subject_count==0:
                        continue
                    
                    subject=self.client.GetSubjectNames(0)

                    if subject:
                        subject_name=subject[1]
                        temp_data={}

                        for seg in self.seg_ids:
                            res=self.client.GetSegmentGlobalTranslation(subject_name, seg)   
                            # res[0] 为 Success(1), res[2] 为 Occluded(False)
                            if res[0]==1 and not res[2]:
                                temp_data[seg] = {"X": res[1][0], "Y": res[1][1], "Z": res[1][2]}
                            else:
                                temp_data[seg] = {"X": 0.0, "Y": 0.0, "Z": 0.0}

                        with self.data_lock:
                            self.current_frame_num=frame_num
                            self.seg_data.update(temp_data)

                time.sleep(0.001)
        finally:
            self.client.Disconnect()    

    def stop(self):
        self.is_running=False           
                
# ————————————————IMU数据接受模块——————————————
class IMU_Thread(Thread):
    def __init__(self, port, baudrate, timeout):
        super().__init__()
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.is_running = True
        self.ser = None
        # self.byte_buffer = []
        self.data_lock = Lock() # 线程锁，防止读写冲突
        
        # 初始化严谨的三级字典架构: 部位 - 物理量 - 方向轴
        self.imu_data = {
            name: {
                "Acc": {"X": 0.0, "Y": 0.0, "Z": 0.0},
                "Gyro": {"X": 0.0, "Y": 0.0, "Z": 0.0},
                "Euler": {"Roll": 0.0, "Pitch": 0.0, "Yaw": 0.0},
                "Quat": {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0}
            } for name in IMU_NAMES
        }
        
    def to_signed_short(self, raw):
        """处理 16 位补码转有符号整数"""
        return raw if raw <= 0x7FFF else raw - 0x10000

    def parse_frame(self, frame):
        """解析单帧 29 字节数据并更新字典"""
        dev_id = frame[0]
        flag = frame[2]
        
        # 仅解算已知部位且 Flag 为 0x61 的数据
        if dev_id in IMU_DICT and flag == 0x61:
            name = IMU_DICT[dev_id]
            
            # 原始数据提取
            ax, ay, az = self.to_signed_short((frame[4]<<8)|frame[3]), self.to_signed_short((frame[6]<<8)|frame[5]), self.to_signed_short((frame[8]<<8)|frame[7])
            gx, gy, gz = self.to_signed_short((frame[10]<<8)|frame[9]), self.to_signed_short((frame[12]<<8)|frame[11]), self.to_signed_short((frame[14]<<8)|frame[13])
            r, p, y = self.to_signed_short((frame[22]<<8)|frame[21]), self.to_signed_short((frame[24]<<8)|frame[23]), self.to_signed_short((frame[26]<<8)|frame[25])

            # 物理量换算
            roll_deg = round((r / 32768) * 180, 4)
            pitch_deg = round((p / 32768) * 180, 4)
            yaw_deg = round((y / 32768) * 180, 4)

            # 四元数换算 (Scipy 内部 ZYX 顺序对应 Yaw, Pitch, Roll)
            rot = R.from_euler('zyx', [yaw_deg, pitch_deg, roll_deg], degrees=True)
            quat = rot.as_quat()
            quat = quat / np.linalg.norm(quat) # 归一化

            # 加锁更新字典
            with self.data_lock:
                self.imu_data[name]["Acc"] = {"X": round((ax/32768)*16*9.8, 4), "Y": round((ay/32768)*16*9.8, 4), "Z": round((az/32768)*16*9.8, 4)}
                self.imu_data[name]["Gyro"] = {"X": round((gx/32768)*2000, 4), "Y": round((gy/32768)*2000, 4), "Z": round((gz/32768)*2000, 4)}
                self.imu_data[name]["Euler"] = {"Roll": roll_deg, "Pitch": pitch_deg, "Yaw": yaw_deg}
                self.imu_data[name]["Quat"] = {"x": round(quat[0], 4), "y": round(quat[1], 4), "z": round(quat[2], 4), "w": round(quat[3], 4)}

    def get_latest_data(self):
        """供外部安全调用的数据接口"""
        with self.data_lock:
            return self.imu_data.copy()

    def run(self):
            try:
                # 增加读写缓冲区大小 (针对 7 个高频 IMU)
                self.ser = serial.Serial(self.port, self.baudrate, timeout=self.timeout)
                self.ser.set_buffer_size(rx_size=10240, tx_size=10240) 
                print(f'IMU:{self.port}')
            except Exception as e:
                print(f'IMU:{e}')
                return

            raw_buffer = b"" # 使用 bytes 对象代替 list，效率提升 10 倍以上

            try:
                while self.is_running:
                    if self.ser.in_waiting > 0:
                        # 1. 直接读取所有可用字节
                        raw_buffer += self.ser.read(self.ser.in_waiting)
                        
                        # 2. 限制缓冲区最大长度，防止内存溢出（如果数据一直解不出来）
                        if len(raw_buffer) > 5000:
                            raw_buffer = raw_buffer[-1000:]

                        # 3. 快速检索所有可能的包头
                        while True:
                            head_idx = raw_buffer.find(FRAME_HEAD)
                            if head_idx == -1:
                                break
                            
                            # 判断包头位置（由于你的协议是 ID 在包头前一位，所以 head_idx 必须 > 0）
                            if head_idx > 0:
                                start_idx = head_idx - 1
                                end_idx = start_idx + FRAME_TOTAL_LEN
                                
                                if end_idx <= len(raw_buffer):
                                    frame = raw_buffer[start_idx:end_idx]
                                    # 校验：如果是 0x55 开头的有效帧
                                    if frame[1] == 0x55: 
                                        self.parse_frame(frame)
                                    # 移除已处理的部分
                                    raw_buffer = raw_buffer[end_idx:]
                                    continue
                                else:
                                    # 数据不足一帧，等待下次读取
                                    break
                            else:
                                # 异常情况：0x55 在第一位，前面没有 ID，丢弃这一位继续找
                                raw_buffer = raw_buffer[1:]
                                
                    time.sleep(0.001) # 保持高频轮询
            finally:
                if self.ser and self.ser.is_open:
                    self.ser.close()

    def stop(self):
        """安全停止线程"""
        self.is_running = False

# ==================== GUI 控制与高精度采样线程 ====================
class MainApp:
    def __init__(self):
        # 初始化Vicon_segs
        temp_client=VDS.Client()
        temp_client.Connect(VICON_HOST_IP)
        temp_client.EnableSegmentData()
        temp_client.GetFrame()
        subject_name,VICON_SEGS=get_vicon_segs(temp_client)
        self.VICON_SEGS=VICON_SEGS
        temp_client.Disconnect()

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
        self.root.title("Vicon—IMU同步采集")
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
        self.csv_writer = CSV_Writer(self.VICON_SEGS, IMU_NAMES)
        
        # 启动高精度定时拉取线程
        self.record_thread = Thread(target=self.precise_recording_loop)
        self.record_thread.start()

    def stop_record(self):
        self.is_recording = False
        if self.record_thread:
            self.record_thread.join()
        
        self.btn_start.config(state=tk.NORMAL)
        self.btn_stop.config(state=tk.DISABLED)
        self.status_label.config(text="状态:记录已保存，待机中", fg="blue")
        print("数据已保存。")

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
        print("正在关闭所有硬件连接...")
        self.is_recording = False
        self.vicon_thread.stop()
        self.imu_thread.stop()
        self.vicon_thread.join()
        self.imu_thread.join()
        self.root.destroy()
        print("系统已完全退出。")

# ————————————————运行——————————————
if __name__ == '__main__':
    app = MainApp()
    app.root.mainloop()


    






