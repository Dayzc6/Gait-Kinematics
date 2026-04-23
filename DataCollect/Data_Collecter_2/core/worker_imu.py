# -*- coding: utf-8 -*-
"""
IMU数据接收线程模块
功能：持续从串口读取IMU数据帧，解析并更新共享数据
"""
import sys
import os
import time
import serial
from threading import Thread, Lock

# 尝试导入配置
try:
    from DataCollect.Data_Collecter_2 import config
    from DataCollect.Data_Collecter_2.utils.protocol_imu import parse_imu_frame
except ImportError:
    import config
    from utils.protocol_imu import parse_imu_frame


class IMUWorker(Thread):
    """
    IMU接收线程
    
    工作原理：
    1. 通过串口以460800波特率读取原始字节流
    2. 解析0x55协议帧，提取7个IMU设备的数据
    3. 更新共享数据容器，供主记录线程使用
    
    数据格式：
    {
        "Trunk": {Acc, Gyro, Euler, Quat},
        "L_Femur": {...},
        "L_Tibia": {...},
        "L_Foot": {...},
        "R_Femur": {...},
        "R_Tibia": {...},
        "R_Foot": {...}
    }
    """

    def __init__(self, port, baudrate, timeout=0.1):
        """
        初始化IMU接收线程
        
        Args:
            port: 串口号，如'COM12'
            baudrate: 波特率，默认460800
            timeout: 串口超时时间（秒）
        """
        super().__init__()
        self.daemon = True

        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout

        # 线程控制
        self.is_running = False
        self.ser = None

        # 共享数据容器
        self.data_lock = Lock()
        self.imu_data = {
            name: {
                "Acc": {"X": 0.0, "Y": 0.0, "Z": 0.0},
                "Gyro": {"X": 0.0, "Y": 0.0, "Z": 0.0},
                "Euler": {"Roll": 0.0, "Pitch": 0.0, "Yaw": 0.0},
                "Quat": {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0}
            } for name in config.IMU_NAMES
        }

    def get_latest_data(self):
        """
        获取最新IMU数据
        
        Returns:
            dict: 所有IMU设备数据的深拷贝
        """
        with self.data_lock:
            # 返回深拷贝，避免外部修改
            import copy
            return copy.deepcopy(self.imu_data)

    def is_connected(self):
        """检查串口连接状态"""
        return self.ser is not None and self.ser.is_open

    def run(self):
        """
        主循环：读取串口数据并解析
        """
        # 打开串口
        try:
            self.ser = serial.Serial(
                self.port,
                self.baudrate,
                timeout=self.timeout
            )
            # 设置较大缓冲区
            self.ser.set_buffer_size(rx_size=10240)
            print(f"[IMUWorker] 串口已打开: {self.port} @ {self.baudrate}")
        except Exception as e:
            print(f"[IMUWorker] 串口打开失败: {e}")
            return

        self.is_running = True

        # 接收缓冲区
        raw_buffer = b""

        try:
            while self.is_running:
                # 读取可用数据
                if self.ser.in_waiting > 0:
                    raw_buffer += self.ser.read(self.ser.in_waiting)
                    
                    # 防止缓冲区无限增长
                    if len(raw_buffer) > 5000:
                        raw_buffer = raw_buffer[-1000:]

                    # 解析帧
                    while True:
                        # 查找帧�� 0x55
                        head_idx = raw_buffer.find(b'\x55')
                        if head_idx == -1:
                            break
                        
                        # 检查是否需要从上一字节开始
                        if head_idx > 0:
                            start_idx = head_idx - 1
                        else:
                            start_idx = 0
                        
                        end_idx = start_idx + config.IMU_FRAME_TOTAL_LEN
                        
                        if end_idx <= len(raw_buffer):
                            frame = raw_buffer[start_idx:end_idx]
                            
                            # 解析帧
                            result = parse_imu_frame(frame)
                            if result:
                                dev_id, imu_data_dict = result
                                
                                # 根据device_id获取IMU名称
                                imu_name = config.IMU_DICT.get(dev_id)
                                if imu_name:
                                    with self.data_lock:
                                        self.imu_data[imu_name] = imu_data_dict
                            
                            # 移除已处理的数据
                            raw_buffer = raw_buffer[end_idx:]
                            continue
                        else:
                            # 数据不够一帧
                            break

                # 极短休眠，避免CPU满载
                time.sleep(0.001)

        except Exception as e:
            print(f"[IMUWorker] 接收异常: {e}")
        finally:
            self.stop()

    def stop(self):
        """
        停止接收线程并关闭串口
        """
        self.is_running = False
        if self.ser and self.ser.is_open:
            try:
                self.ser.close()
            except:
                pass
        print("[IMUWorker] 线程已停止")