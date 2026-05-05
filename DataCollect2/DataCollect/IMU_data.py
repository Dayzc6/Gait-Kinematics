# env:conda activate Vicon_SDK
import numpy as np
import serial
import time
from threading import Thread, Lock
from scipy.spatial.transform import Rotation as R

# ==================== 全局参数配置 ====================
PORT = 'COM12'                     # 请根据实际情况修改
BAUDRATE = 460800                  
TIMEOUT = 0.1
FRAME_HEAD = b'\x55'               
FRAME_TOTAL_LEN = 29               

# IMU 设备号到英文部位的映射
# 设备有02-08 | 09-15 两套编号
IMU_DICT = {
    0x09: "Trunk",    0x0A: "L_Femur", 0x0B: "L_Tibia", 0x0C: "L_Foot",
    0x0D: "R_Femur",  0x0E: "R_Tibia", 0x0F: "R_Foot"
}
IMU_NAMES = list(IMU_DICT.values())

# ==================== IMU 接收模块 ====================
class IMU_Thread(Thread):
    def __init__(self, port, baudrate, timeout):
        super().__init__()
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.is_running = True
        self.ser = None
        self.byte_buffer = []
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
                print(f'✅ IMU 串口已打开: {self.port}')
            except Exception as e:
                print(f'❌ IMU 串口打开失败: {e}')
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


# ==================== 独立测试模块 ====================
if __name__ == '__main__':
    # 实例化并启动 IMU 线程
    imu_thread = IMU_Thread(PORT, BAUDRATE, TIMEOUT)
    imu_thread.start()
    
    print("\n🚀 开始独立接收 IMU 数据 (按 Ctrl+C 停止)...\n")
    
    try:
        while True:
            # 获取最新数据副本
            latest_data = imu_thread.get_latest_data()
            
            # 为了避免刷屏，这里仅打印 Trunk (躯干) 的欧拉角作为测试验证
            # 你可以根据需要修改这里的 print 逻辑
            trunk_euler = latest_data["Trunk"]["Euler"]
            trunk_acc = latest_data["Trunk"]["Acc"]

            L_Femur_euler = latest_data["L_Femur"]["Euler"]
            L_Femur_acc = latest_data["L_Femur"]["Acc"]

            L_Tibia_euler = latest_data["L_Tibia"]["Euler"]
            L_Tibia_acc = latest_data["L_Tibia"]["Acc"]

            L_Foot_euler = latest_data["L_Foot"]["Euler"]
            L_Foot_acc = latest_data["L_Foot"]["Acc"]

            R_Femur_euler = latest_data["R_Femur"]["Euler"]
            R_Femur_acc = latest_data["R_Femur"]["Acc"]

            R_Tibia_euler = latest_data["R_Tibia"]["Euler"]
            R_Tibia_acc = latest_data["R_Tibia"]["Acc"]

            R_Foot_euler = latest_data["R_Foot"]["Euler"]
            R_Foot_acc = latest_data["R_Foot"]["Acc"]

            print("实时数据:\n",
                f"Trunk | 欧拉角: {trunk_euler} | 加速度: {trunk_acc}\n",
                f"L_Femur | 欧拉角: {L_Femur_euler} | 加速度: {L_Femur_acc}\n ",
                f"R_Femur | 欧拉角: {R_Femur_euler} | 加速度: {R_Femur_acc}\n ",
                f"L_Tibia | 欧拉角: {L_Tibia_euler} | 加速度: {L_Tibia_acc}\n ",  
                f"R_Tibia | 欧拉角: {R_Tibia_euler} | 加速度: {R_Tibia_acc}\n ",  
                f"L_Foot | 欧拉角: {L_Foot_euler} | 加速度: {L_Foot_acc}\n ",  
                f"R_Foot | 欧拉角: {R_Foot_euler} | 加速度: {R_Foot_acc}\n ",  
                end='\r')
            
            # 以 10Hz 的频率刷新终端打印
            time.sleep(0.1)
            
    except KeyboardInterrupt:
        print("\n\n🛑 收到停止指令，正在关闭串口...")
        imu_thread.stop()
        imu_thread.join()
        print("✅ 程序已安全退出。")


