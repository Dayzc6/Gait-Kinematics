# -*- coding: utf-8 -*-
"""
IMU 数据接收线程
- 接收并解析单设备 IMU 帧
- 仅在 7 个设备都已更新且时间窗口足够小时，生成一次完整 IMU snapshot
- 供 SyncEngine 按 Vicon 时间严格匹配
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
    from DataCollect.Data_Collecter import config
    from DataCollect.Data_Collecter.utils.protocol_imu import parse_imu_frame
    from DataCollect.Data_Collecter.utils.data_models import IMUPacket
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
        self.raw_queue = raw_queue  # 保留参数，但正式链路当前不使用 raw 输出

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
        self.latest_device_timestamp = {name: None for name in config.IMU_NAMES}
        self.packet_buffer = deque(maxlen=config.IMU_BUFFER_MAXLEN)
        self.last_snapshot_ts = None

    def get_latest_data(self):
        with self.data_lock:
            return copy.deepcopy(self.imu_data)

    def get_buffer_snapshot(self):
        with self.buffer_lock:
            return list(self.packet_buffer)

    def is_connected(self):
        return self.available and self.ser is not None and self.ser.is_open

    def _maybe_emit_snapshot(self):
        timestamps = list(self.latest_device_timestamp.values())
        if any(ts is None for ts in timestamps):
            return

        min_ts = min(timestamps)
        max_ts = max(timestamps)
        if (max_ts - min_ts) * 1000.0 > config.IMU_SNAPSHOT_WINDOW_MS:
            return

        snapshot_ts = max_ts
        if self.last_snapshot_ts is not None and snapshot_ts <= self.last_snapshot_ts:
            return

        packet = IMUPacket(recv_timestamp=snapshot_ts, data=copy.deepcopy(self.imu_data))
        with self.buffer_lock:
            self.packet_buffer.append(packet)
        self.last_snapshot_ts = snapshot_ts

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

                        recv_ts = time.time()
                        with self.data_lock:
                            self.imu_data[imu_name] = imu_data_dict
                            self.latest_device_timestamp[imu_name] = recv_ts
                            self._maybe_emit_snapshot()

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
