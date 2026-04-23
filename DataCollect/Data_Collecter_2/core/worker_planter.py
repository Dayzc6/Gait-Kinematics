# -*- coding: utf-8 -*-
"""
Planter（足底压力传感器）接收线程模块
功能：从串口读取左/右脚压力数据帧（分时复用）
"""
import sys
import os
import time
import serial
from threading import Thread, Lock

# 尝试导入配置
try:
    from DataCollect.Data_Collecter_2 import config
    from DataCollect.Data_Collecter_2.utils.protocol_planter import parse_planter_frame
except ImportError:
    import config
    from utils.protocol_planter import parse_planter_frame


class PlanterWorker(Thread):
    """
    Planter接收线程（单串口分时复用）
    
    工作原理：
    1. 通过串口以115200波特率读取原始字节流
    2. 根据帧内foot_id（0x01=左，0x02=右）区分左右脚
    3. 解析18个感应点的压力值，更新共享数据
    
    数据格式：
    {
        "Left": [value0, value1, ..., value17],  # 18个点
        "Right": [value0, value1, ..., value17]
    }
    """

    def __init__(self, port, baudrate=115200, timeout=2):
        """
        初始化Planter接收线程
        
        Args:
            port: 串口号，如'COM11'
            baudrate: 波特率，默认115200
            timeout: 串口超时时间
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
        self.left_data = [0] * config.PLANTER_SENSOR_POINTS
        self.right_data = [0] * config.PLANTER_SENSOR_POINTS
        
        # 是否初始化过
        self._initialized = False

    def get_latest_data(self):
        """
        获取最新压力数据
        
        Returns:
            dict: {"Left": [18个值], "Right": [18个值]}
        """
        with self.data_lock:
            import copy
            return {
                "Left": copy.copy(self.left_data),
                "Right": copy.copy(self.right_data)
            }

    def is_connected(self):
        """检查串口连接状态"""
        return self.ser is not None and self.ser.is_open

    def _init_sensor(self):
        """
        初始化传感器：发送初始化命令
        """
        if not self.ser or not self.ser.is_open:
            return False
        
        try:
            # 发送初始化命令（左脚）
            self.ser.write(b'INIT_LEFT\n')
            time.sleep(0.5)
            ack = self.ser.read_all()
            print(f"[PlanterWorker] INIT_LEFT响应: {ack.hex() if ack else 'None'}")
            
            # 发送初始化命令（右脚）
            self.ser.write(b'INIT_RIGHT\n')
            time.sleep(0.5)
            ack = self.ser.read_all()
            print(f"[PlanterWorker] INIT_RIGHT响应: {ack.hex() if ack else 'None'}")
            
            self._initialized = True
            return True
        except Exception as e:
            print(f"[PlanterWorker] 初始化命令失败: {e}")
            return False

    def run(self):
        """
        主循环：读取串口数据并解析
        """
        # 打开串口
        try:
            self.ser = serial.Serial(
                self.port,
                self.baudrate,
                timeout=self.timeout,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE
            )
            print(f"[PlanterWorker] 串口已打开: {self.port} @ {self.baudrate}")
            
            # 初始化传感器
            self._init_sensor()
            
        except Exception as e:
            print(f"[PlanterWorker] 串口打开失败: {e}")
            return

        self.is_running = True

        # 接收缓冲区
        raw_buffer = bytearray()

        try:
            while self.is_running:
                # 读取可用数据
                chunk = self.ser.read(10)
                if chunk:
                    raw_buffer.extend(chunk)

                # 解析帧
                while True:
                    # 1) 丢弃帧头前的噪声
                    while raw_buffer and raw_buffer[0] != 0xAA:
                        raw_buffer.pop(0)
                    
                    if len(raw_buffer) < 3:
                        break

                    # 2) 检查foot_id
                    foot_id = raw_buffer[1]
                    if foot_id not in (0x01, 0x02):
                        raw_buffer.pop(0)
                        continue

                    # 3) 尝试两种长度
                    frame = None
                    for frame_len in config.PLANTER_FRAME_LENGTH_CANDIDATES:
                        if len(raw_buffer) >= frame_len:
                            frame = bytes(raw_buffer[:frame_len])
                            del raw_buffer[:frame_len]
                            break
                    
                    if frame is None:
                        break

                    # 4) 解析数据
                    result = parse_planter_frame(frame)
                    if result:
                        side, values = result
                        with self.data_lock:
                            if side == "Left":
                                self.left_data = values
                            else:
                                self.right_data = values

                # 休眠，避免CPU满载
                time.sleep(0.002)

        except Exception as e:
            print(f"[PlanterWorker] 接收异常: {e}")
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
        print("[PlanterWorker] 线程已停止")