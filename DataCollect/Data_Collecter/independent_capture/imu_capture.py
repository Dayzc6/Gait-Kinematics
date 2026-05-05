# -*- coding: utf-8 -*-
"""
独立 IMU 实时采集模块
- 单串口读取 RF 汇聚后的 IMU 数据
- 每成功解析一帧，就按 device_name 独立写入一行 CSV
- 不做七设备 snapshot，不做跨设备同步
"""
import os
import sys
import time
from threading import Event, Thread

import serial

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(CURRENT_DIR)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

try:
    from DataCollect.Data_Collecter.independent_capture import local_config as config
    from DataCollect.Data_Collecter.utils.protocol_imu import parse_imu_frame
    from DataCollect.Data_Collecter.independent_capture.common import now_mono, now_wall
    from DataCollect.Data_Collecter.independent_capture.schema import IMU_HEADERS
except ImportError:
    from independent_capture import local_config as config
    from utils.protocol_imu import parse_imu_frame
    from independent_capture.common import now_mono, now_wall
    from independent_capture.schema import IMU_HEADERS


class IMUCaptureWorker(Thread):
    def __init__(self, session_id, trial_id, subject_id, csv_writer, port=None, baudrate=None, timeout=None):
        super().__init__(daemon=True)
        self.session_id = session_id
        self.trial_id = trial_id
        self.subject_id = subject_id
        self.csv_writer = csv_writer
        self.port = port or config.IMU_PORT
        self.baudrate = baudrate or config.IMU_BAUDRATE
        self.timeout = config.IMU_TIMEOUT if timeout is None else timeout
        self.stop_event = Event()
        self.ser = None
        self.device_seq = {name: 0 for name in config.IMU_NAMES}
        self.stats = {
            'decoded_rows': 0,
            'parse_failures': 0,
            'unknown_device_frames': 0,
        }

    def stop(self):
        self.stop_event.set()

    def get_stats(self):
        return dict(self.stats)

    def run(self):
        try:
            self.ser = serial.Serial(self.port, self.baudrate, timeout=self.timeout)
            try:
                self.ser.set_buffer_size(rx_size=10240)
            except Exception:
                pass
            print(f'[IMUCapture] open {self.port} @ {self.baudrate}')
        except Exception as e:
            print(f'[IMUCapture] open failed: {e}')
            return

        raw_buffer = b''
        last_flush = now_mono()
        try:
            while not self.stop_event.is_set():
                waiting = self.ser.in_waiting
                if waiting > 0:
                    raw_buffer += self.ser.read(waiting)
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
                            self.stats['parse_failures'] += 1
                            continue

                        dev_id, imu_data = result
                        device_name = config.IMU_DICT.get(dev_id)
                        if not device_name:
                            self.stats['unknown_device_frames'] += 1
                            continue

                        recv_wall = now_wall()
                        recv_mono = now_mono()
                        self.device_seq[device_name] += 1
                        row = [
                            self.session_id,
                            self.trial_id,
                            self.subject_id,
                            recv_wall,
                            recv_wall,
                            recv_mono,
                            dev_id,
                            device_name,
                            self.device_seq[device_name],
                            1,
                            imu_data['Acc']['X'], imu_data['Acc']['Y'], imu_data['Acc']['Z'],
                            imu_data['Gyro']['X'], imu_data['Gyro']['Y'], imu_data['Gyro']['Z'],
                            imu_data['Euler']['Roll'], imu_data['Euler']['Pitch'], imu_data['Euler']['Yaw'],
                            imu_data['Quat']['x'], imu_data['Quat']['y'], imu_data['Quat']['z'], imu_data['Quat']['w'],
                        ]
                        self.csv_writer.write_row(row)
                        self.stats['decoded_rows'] += 1

                now = now_mono()
                if (now - last_flush) >= 0.5:
                    self.csv_writer.flush()
                    last_flush = now
                time.sleep(0.001)
        except Exception as e:
            print(f'[IMUCapture] runtime error: {e}')
        finally:
            if self.ser and self.ser.is_open:
                try:
                    self.ser.close()
                except Exception:
                    pass
            self.csv_writer.flush()
            print('[IMUCapture] stopped')
