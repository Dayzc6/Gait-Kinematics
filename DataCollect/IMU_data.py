# IMU_Data
# 加速度、角速度和角度
# conda activate base
import serial
import time
import math
from threading import Lock

# 四元数转换
import numpy as np
from scipy.spatial.transform import Rotation as R

# 协议固定参数
PORT = 'COM11'
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

# 支持的Flag类型（扩展可添加更多）
FLAG_ACC_GYRO_MAG_ANGLE = 0x61     # 加速度+角速度+角度
FLAG_QUATERNION = 0x66             # 四元数(无法使用)

class WitMotionIMU:
    def __init__(self, port, baudrate, timeout=1):
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.ser = None
        self.byte_buffer = []  # 逐字节缓冲池（仅存bytes对象）

    def open_serial(self):
        """打开串口"""
        try:
            self.ser = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=self.timeout
            )
            print(f"✅ 串口连接成功：{self.port}（波特率：{self.baudrate}）")
            print("="*80)
            return True
        except serial.SerialException as e:
            print(f"❌ 串口连接失败：{e}")
            return False

    def extract_valid_frame(self):
        """提取符合协议的29字节完整帧（修复类型错误）"""
        # ========== 修复点1：强制转换缓冲池元素为bytes ==========
        # 过滤非bytes元素，确保缓冲池只有bytes
        self.byte_buffer = [b if isinstance(b, bytes) else bytes([b]) for b in self.byte_buffer]
        buffer_bytes = b''.join(self.byte_buffer)
        valid_frame = None

        # 查找0x55包头，定位有效帧起始
        head_pos = buffer_bytes.find(FRAME_HEAD)
        if head_pos != -1:
            # 设备号在包头前1字节
            frame_start = head_pos - 1 if head_pos > 0 else 0
            frame_end = frame_start + FRAME_TOTAL_LEN

            # 校验帧长度
            if frame_end <= len(buffer_bytes):
                candidate_frame = buffer_bytes[frame_start:frame_end]
                if len(candidate_frame) == FRAME_TOTAL_LEN:
                    valid_frame = candidate_frame
                    # 清空缓冲（保留未匹配字节）
                    self.byte_buffer = list(buffer_bytes[frame_end:])
            else:
                # 长度不足，保留有效部分
                self.byte_buffer = list(buffer_bytes[frame_start:])
        else:
            # 无包头，保留最后30字节
            if len(buffer_bytes) > FRAME_TOTAL_LEN + 1:
                self.byte_buffer = list(buffer_bytes[-FRAME_TOTAL_LEN-1:])

        return valid_frame

    def to_signed_short(self, raw):
        """转换为16位有符号短整型（处理补码负数）"""
        return raw if raw <= 0x7FFF else raw - 0x10000

    def parse_flag_61_frame(self, frame):
        """解析Flag=0x61帧（加速度+角速度+磁场+角度）"""
        # 加速度X/Y/Z（3-8字节）
        ax_raw = self.to_signed_short((frame[4] << 8) | frame[3])
        ay_raw = self.to_signed_short((frame[6] << 8) | frame[5])
        az_raw = self.to_signed_short((frame[8] << 8) | frame[7])

        # 角速度X/Y/Z（9-14字节）
        wx_raw = self.to_signed_short((frame[10] << 8) | frame[9])
        wy_raw = self.to_signed_short((frame[12] << 8) | frame[11])
        wz_raw = self.to_signed_short((frame[14] << 8) | frame[13])

        # 磁场X/Y/Z（15-20字节）
        # hx_raw = self.to_signed_short((frame[16] << 8) | frame[15])
        # hy_raw = self.to_signed_short((frame[18] << 8) | frame[17])
        # hz_raw = self.to_signed_short((frame[20] << 8) | frame[19])

        # 欧拉角（21-26字节）
        roll_raw = self.to_signed_short((frame[22] << 8) | frame[21])
        pitch_raw = self.to_signed_short((frame[24] << 8) | frame[23])
        yaw_raw = self.to_signed_short((frame[26] << 8) | frame[25])

        # 电池电量（27-28字节）
        bat_raw = (frame[28] << 8) | frame[27]
        bat_voltage = bat_raw * 0.01
        # 电量百分比映射（官方标准）
        bat_percent = self.calc_battery_percent(bat_voltage)

        # 四元数转换
        x=round((roll_raw / 32768) * 180, 4)
        y=round((pitch_raw / 32768) * 180, 4)
        z=round((yaw_raw / 32768) * 180, 4)
        # WT9011的内部姿态解算遵循Z-Y-X
        rot=R.from_euler('zyx',[z,y,x],degrees=True)
        quat_scipy=rot.as_quat()
        quat_scipy=quat_scipy/np.linalg.norm(quat_scipy)
        # euler_scipy=rot.as_euler('xyz',degrees=True)

        # 物理值转换
        return {
            "加速度(m/s²)": {
                "X": round((ax_raw / 32768) * 16 * 9.8, 4),
                "Y": round((ay_raw / 32768) * 16 * 9.8, 4),
                "Z": round((az_raw / 32768) * 16 * 9.8, 4)
            },
            "角速度(°/s)": {
                "X": round((wx_raw / 32768) * 2000, 4), # 
                "Y": round((wy_raw / 32768) * 2000, 4),
                "Z": round((wz_raw / 32768) * 2000, 4)
            },
            #"磁场": {
                #"X(mG)": hx_raw, "Y(mG)": hy_raw, "Z(mG)": hz_raw,
                #"X(uT)": round(hx_raw * 0.1, 1),
                #"Y(uT)": round(hy_raw * 0.1, 1),
                #"Z(uT)": round(hz_raw * 0.1, 1)
            #},
            "欧拉角(°)": {
                "Roll": round((roll_raw / 32768) * 180, 4),
                "Pitch": round((pitch_raw / 32768) * 180, 4),
                "Yaw": round((yaw_raw / 32768) * 180, 4)
            },
            "四元数([x,y,z,w])":{
                "x": quat_scipy[0],
                "y": quat_scipy[1],
                "z": quat_scipy[2],
                "w": quat_scipy[3]
            },
            "电池信息": {
                "电压(V)": round(bat_voltage, 2),
                "百分比(%)": bat_percent
            }
        }

    def calc_battery_percent(self, voltage):
        """计算电池百分比（官方映射表）"""
        if voltage > 3.96:
            return 100
        elif 3.93 <= voltage <= 3.96:
            return 90
        elif 3.87 <= voltage <= 3.93:
            return 75
        elif 3.82 <= voltage <= 3.87:
            return 60
        elif 3.79 <= voltage <= 3.82:
            return 50
        elif 3.77 <= voltage <= 3.79:
            return 40
        elif 3.73 <= voltage <= 3.77:
            return 30
        elif 3.70 <= voltage <= 3.73:
            return 20
        elif 3.68 <= voltage <= 3.70:
            return 15
        elif 3.50 <= voltage <= 3.68:
            return 10
        elif 3.40 <= voltage <= 3.50:
            return 5
        else:
            return 0

    def parse_imu_data(self, frame):
        """统一解析入口（兼容不同Flag帧）"""
        # 基础信息
        device_id = frame[DEVICE_ID_OFFSET]
        flag = frame[FLAG_OFFSET]

        result = {
            "基础信息": {
                "设备号": f"0x{device_id:02X}",
                "标志位(Flag)": f"0x{flag:02X}"
            }
        }

        # 根据Flag解析对应数据
        if flag == FLAG_ACC_GYRO_MAG_ANGLE:
            result["基础信息"]["帧类型"] = "加速度+角速度+磁场+角度"
            result.update(self.parse_flag_61_frame(frame))
        elif flag == FLAG_QUATERNION:
            result["基础信息"]["帧类型"] = "四元数"
            result.update(self.parse_flag_66_frame(frame))
        else:
            result["错误"] = f"不支持的Flag值：0x{flag:02X}（仅支持0x61/0x66）"

        return result

    def run(self):
        """主运行逻辑"""
        if not self.open_serial():
            return

        try:
            while True:
                # ========== 修复点2：确保读取的字节是bytes类型 ==========
                byte = self.ser.read(1)
                if byte:
                    # 强制转换为bytes（避免int类型）
                    if isinstance(byte, int):
                        byte = bytes([byte])
                    self.byte_buffer.append(byte)
                    
                    valid_frame = self.extract_valid_frame()
                    if valid_frame:
                        # 打印原始帧（带空格）
                        frame_hex = ' '.join([f"{b:02X}" for b in valid_frame])
                        print(f"\n📌 接收到29字节协议帧：")
                        print(f"原始数据：{frame_hex}")

                        # 解析并输出
                        result = self.parse_imu_data(valid_frame)
                        print("🔍 解算结果：")
                        for category, data in result.items():
                            print(f"  {category}：")
                            for key, value in data.items():
                                print(f"    {key}：{value}")
                        print("-"*80)

                        if hasattr(self, 'on_frame_parsed'):
                            self.on_frame_parsed(valid_frame, result)
                time.sleep(0.001)

        except KeyboardInterrupt:
            print("\n\n🛑 用户终止程序")
        finally:
            if self.ser and self.ser.is_open:
                self.ser.close()
                print("✅ 串口已关闭")

class MultiIMUManager:
    def __init__(self, port, baudrate, timeout=0.1, device_ids=None, expire_threshold=0.5):
        """
        初始化多IMU管理器
        :param port: 串口端口
        :param baudrate: 波特率
        :param timeout: 串口超时
        :param device_ids: 目标IMU设备号列表（默认02-08，即[0x02,0x03,...,0x08]）
        :param expire_threshold: 数据过期阈值（秒），默认500ms
        """
        # 目标设备号（02-08，十六进制）
        self.device_ids = device_ids if device_ids else [0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08]
        self.expire_threshold = expire_threshold  # 数据过期阈值
        self.lock = Lock()  # 线程锁，保证多线程下数据安全
        
        # 初始化数据缓存（每个设备号对应一个缓存项）
        self.imu_data_cache = {dev_id: {"data": None, "timestamp": 0.0} for dev_id in self.device_ids}
        
        # 初始化底层单IMU解析器
        self.single_imu = WitMotionIMU(port=port, baudrate=baudrate, timeout=timeout)
        
        # 重写单IMU的帧解析后处理逻辑（核心：按设备号分发）
        # 注：此处通过替换回调函数实现，避免修改原有类
        self.single_imu.on_frame_parsed = self.distribute_frame_to_imu

    def distribute_frame_to_imu(self, frame, parsed_data):
        """
        帧分发核心函数：将解析后的帧数据分发到对应设备号的缓存
        :param frame: 原始29字节帧（bytes）
        :param parsed_data: 解析后的字典数据
        """
        # 提取帧中的设备号（协议第0字节）
        dev_id = frame[0]
        
        # 仅处理目标设备号（02-08）
        if dev_id in self.device_ids:
            with self.lock:  # 加锁保证数据安全
                # 更新该设备的缓存（刷新数据+时间戳）
                self.imu_data_cache[dev_id]["data"] = parsed_data
                self.imu_data_cache[dev_id]["timestamp"] = time.time()
                print(f"📌 设备0x{dev_id:02X}数据已更新")

    def get_synced_data(self, strict_sync=True):
        """
        获取7个IMU的同步数据
        :param strict_sync: 是否严格同步（True=等待所有设备数据有效，False=返回当前所有数据）
        :return: 字典，key=设备号，value=解析后数据（None表示过期/无效）
        """
        synced_data = {}
        current_time = time.time()
        
        with self.lock:
            for dev_id in self.device_ids:
                cache = self.imu_data_cache[dev_id]
                # 判断数据是否有效（未过期）
                is_valid = (current_time - cache["timestamp"]) <= self.expire_threshold
                if is_valid:
                    synced_data[dev_id] = cache["data"]
                else:
                    synced_data[dev_id] = None
        
        # 严格同步模式：等待所有设备数据有效（最多等待1秒）
        if strict_sync:
            wait_start = time.time()
            while None in synced_data.values() and (time.time() - wait_start) < 1.0:
                time.sleep(0.001)  # 微延时等待数据
                # 重新获取数据
                synced_data = self.get_synced_data(strict_sync=False)
        
        return synced_data

    def run(self):
        """
        启动多IMU同步接收主循环
        """
        # 启动底层串口读取和帧解析
        print(f"🚀 启动7个IMU同步接收（设备号：{[hex(d) for d in self.device_ids]}）")
        print("="*100)

        # 方式：启动单IMU的读取，同时定时获取同步数据输出
        try:
            # 启动底层串口读取（此处需调整单IMU的run为非阻塞，或用线程）
            import threading
            read_thread = threading.Thread(target=self.single_imu.run, daemon=True)
            read_thread.start()
            
            # 主循环：定时获取并输出同步数据
            while True:
                # 获取同步数据（严格模式）
                synced_data = self.get_synced_data(strict_sync=True)
                
                # 输出7个IMU的同步数据
                print(f"\n⏱️  同步数据快照（{time.strftime('%Y-%m-%d %H:%M:%S')}）")
                for dev_id in self.device_ids:
                    data = synced_data[dev_id]
                    if data:
                        print(f"📟 设备0x{dev_id:02X}：")
                        # 按需输出关键数据（如加速度、欧拉角）
                        if "加速度(m/s²)" in data:
                            acc = data["加速度(m/s²)"]
                            print(f"    加速度：X={acc['X']}, Y={acc['Y']}, Z={acc['Z']}")
                        if "欧拉角(°)" in data:
                            angle = data["欧拉角(°)"]
                            print(f"    欧拉角：Roll={angle['Roll']}, Pitch={angle['Pitch']}, Yaw={angle['Yaw']}")
                    else:
                        print(f"❌ 设备0x{dev_id:02X}：数据过期/未接收")
                print("-"*100)
                
                time.sleep(0.1)  # 100ms输出一次同步数据（可调整）
                
        except KeyboardInterrupt:
            print("\n\n🛑 停止多IMU同步接收")
        finally:
            # 关闭串口
            if self.single_imu.ser and self.single_imu.ser.is_open:
                self.single_imu.ser.close()
            print("✅ 串口已关闭")

# ===================== 启动程序 =====================
if __name__ == "__main__":
    # 初始化多IMU管理器（串口参数与之前一致）
    multi_imu = MultiIMUManager(port=PORT, baudrate=BAUDRATE, expire_threshold=0.5)
    # 启动同步接收
    multi_imu.run()