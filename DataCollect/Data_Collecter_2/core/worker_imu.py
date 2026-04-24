# -*- coding: utf-8 -*-
"""
IMU 接收线程
保留原有串口接收与解析逻辑，同时增加：
1. latest 数据
2. 带时间戳的环形缓冲区
3. 原始流写队列
"""
import time
import serial
from collections import deque
from threading import Thread, Lock

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

        self.is_running = True
        self.ser = None
        self.data_lock = Lock()
        self.imu_data = {
            name: {
                "Acc": {"X": 0.0, "Y": 0.0, "Z": 0.0},
                "Gyro": {"X": 0.0, "Y": 0.0, "Z": 0.0},
                "Euler": {"Roll": 0.0, "Pitch": 0.0, "Yaw": 0.0},
                "Quat": {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0}
            } for name in config.IMU_NAMES
        }
        self.latest_packet = None
        self.packet_buffer = deque(maxlen=config.IMU_BUFFER_SIZE)

    def get_latest_data(self):
        with self.data_lock:
            import copy
            return copy.deepcopy(self.imu_data)

    def get_latest_packet(self):
        with self.data_lock:
            return self.latest_packet

    def get_buffer_snapshot(self):
        with self.data_lock:
            return list(self.packet_buffer)

    def is_connected(self):
        return self.ser is not None and self.ser.is_open

    def run(self):
        try:
            self.ser = serial.Serial(self.port, self.baudrate, timeout=self.timeout)
            self.ser.set_buffer_size(rx_size=10240)
            print(f'[IMUWorker] 串口已打开: {self.port}')
        except Exception as e:
            print(f'[IMUWorker] 串口打开失败: {e}')
            return

        raw_buffer = b""
        try:
            while self.is_running:
                if self.ser.in_waiting > 0:
                    raw_buffer += self.ser.read(self.ser.in_waiting)
                    if len(raw_buffer) > 5000:
                        raw_buffer = raw_buffer[-1000:]

                    while True:
                        head_idx = raw_buffer.find(config.IMU_FRAME_HEAD)
                        if head_idx == -1:
                            break
                        if head_idx > 0:
                            start_idx = head_idx - 1
                            end_idx = start_idx + config.IMU_FRAME_TOTAL_LEN
                            if end_idx <= len(raw_buffer):
                                frame = raw_buffer[start_idx:end_idx]
                                if frame[1] == 0x55:
                                    result = parse_imu_frame(frame)
                                    if result:
                                        dev_id, imu_data_dict = result
                                        imu_name = config.IMU_DICT.get(dev_id)
                                        if imu_name:
                                            recv_ts = time.time()
                                            with self.data_lock:
                                                self.imu_data[imu_name] = imu_data_dict
                                                packet_data = {k: v.copy() if isinstance(v, dict) else v for k, v in self.imu_data.items()}
                                                packet = IMUPacket(recv_timestamp=recv_ts, data=self.get_latest_data())
                                                self.latest_packet = packet
                                                self.packet_buffer.append(packet)
                                            if self.raw_queue is not None:
                                                try:
                                                    self.raw_queue.put(packet, timeout=0.01)
                                                except Exception:
                                                    pass
                                raw_buffer = raw_buffer[end_idx:]
                                continue
                            else:
                                break
                        else:
                            raw_buffer = raw_buffer[1:]
                time.sleep(0.001)
        finally:
            if self.ser and self.ser.is_open:
                self.ser.close()

    def stop(self):
        self.is_running = False
