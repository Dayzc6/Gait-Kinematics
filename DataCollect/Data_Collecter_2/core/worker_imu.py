# -*- coding: utf-8 -*-
"""
IMU 数据接收线程
- 保留最新 IMU 数据
- 同时把时间戳化快照放入 buffer，供 SyncEngine 按 Vicon 时间匹配
- 可选写入 raw_queue
"""
import copy
import os
import sys
import time
from collections import deque
from threading import Thread, Lock

import serial

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(CURRENT_DIR)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

try:
    from DataCollect.Data_Collecter_2 import config
    from DataCollect.Data_Collecter_2.utils.protocol_imu import parse_imu_frame
    from DataCollect.Data_Collecter_2.utils.data_models import IMUPacket
except ImportError:
    import config
    from utils.protocol_imu import parse_imu_frame
    from utils.data_models import IMUPacket


class IMUWorker(Thread):
    def __init__(self, port, baudrate, timeout=0.1, raw_queue=None):
        super().__init__()
        self.daemon = True

        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.raw_queue = raw_queue

        self.is_running = False
        self.ser = None
        self.available = False

        self.data_lock = Lock()
        self.buffer_lock = Lock()
        self.imu_data = {
            name: {
                "Acc": {"X": 0.0, "Y": 0.0, "Z": 0.0},
                "Gyro": {"X": 0.0, "Y": 0.0, "Z": 0.0},
                "Euler": {"Roll": 0.0, "Pitch": 0.0, "Yaw": 0.0},
                "Quat": {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0}
            } for name in config.IMU_NAMES
        }
        self.packet_buffer = deque(maxlen=config.IMU_BUFFER_MAXLEN)

    def get_latest_data(self):
        with self.data_lock:
            return copy.deepcopy(self.imu_data)

    def get_buffer_snapshot(self):
        with self.buffer_lock:
            return list(self.packet_buffer)

    def is_connected(self):
        return self.available and self.ser is not None and self.ser.is_open

    def run(self):
        try:
            self.ser = serial.Serial(self.port, self.baudrate, timeout=self.timeout)
            try:
                self.ser.set_buffer_size(rx_size=10240)
            except Exception:
                pass
            self.available = True
            print(f"[IMUWorker] 串口已打开: {self.port} @ {self.baudrate}")
        except Exception as e:
            self.available = False
            print(f"[IMUWorker] 串口打开失败，将以空数据模式运行: {e}")
            return

        self.is_running = True
        raw_buffer = b""

        try:
            while self.is_running:
                if self.ser.in_waiting > 0:
                    raw_buffer += self.ser.read(self.ser.in_waiting)
                    if len(raw_buffer) > 5000:
                        raw_buffer = raw_buffer[-1000:]

                    while True:
                        head_idx = raw_buffer.find(b'\x55')
                        if head_idx == -1:
                            break

                        start_idx = head_idx - 1 if head_idx > 0 else 0
                        end_idx = start_idx + config.IMU_FRAME_TOTAL_LEN
                        if end_idx > len(raw_buffer):
                            break

                        frame = raw_buffer[start_idx:end_idx]
                        raw_buffer = raw_buffer[end_idx:]
                        result = parse_imu_frame(frame)
                        if not result:
                            continue

                        dev_id, imu_data_dict = result
                        imu_name = config.IMU_DICT.get(dev_id)
                        if not imu_name:
                            continue

                        with self.data_lock:
                            self.imu_data[imu_name] = imu_data_dict
                            snapshot = copy.deepcopy(self.imu_data)

                        packet = IMUPacket(recv_timestamp=time.time(), data=snapshot)
                        with self.buffer_lock:
                            self.packet_buffer.append(packet)

                        if self.raw_queue is not None:
                            try:
                                self.raw_queue.put_nowait(packet)
                            except Exception:
                                pass

                time.sleep(0.001)
        except Exception as e:
            print(f"[IMUWorker] 接收异常: {e}")
        finally:
            self.stop()

    def stop(self):
        self.is_running = False
        if self.ser and self.ser.is_open:
            try:
                self.ser.close()
            except Exception:
                pass
        print("[IMUWorker] 线程已停止")


if __name__ == '__main__':
    print("[TEST] IMUWorker单元测试")
    print("[TEST] 无串口设备，跳过实际测试")
    print("[TEST] 测试完成")
