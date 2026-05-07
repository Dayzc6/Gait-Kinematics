# -*- coding: utf-8 -*-
"""
路线2：IMU 原始字节流采集
记录：
- recv_timestamp
- raw_hex
目标：采集阶段尽量不解算，只保留原始数据与时间戳
"""
import os
import sys
import time

import serial

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(CURRENT_DIR)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from common import JsonlWriter, bytes_to_hex, make_session_prefix

try:
    from DataCollect.Data_Collecter import config
except ImportError:
    import config

DURATION_SECONDS = 20


def run_capture():
    output_prefix = make_session_prefix('imu_raw')
    output_path = output_prefix + '.jsonl'
    writer = JsonlWriter(output_path)
    ser = None
    try:
        ser = serial.Serial(config.IMU_PORT, config.IMU_BAUDRATE, timeout=config.IMU_TIMEOUT)
        try:
            ser.set_buffer_size(rx_size=10240)
        except Exception:
            pass
        print(f'[route2] IMU raw capture open: {config.IMU_PORT} @ {config.IMU_BAUDRATE}')

        start = time.time()
        chunks = 0
        while time.time() - start < DURATION_SECONDS:
            waiting = ser.in_waiting
            if waiting > 0:
                data = ser.read(waiting)
                if data:
                    writer.write({
                        'recv_timestamp': time.time(),
                        'raw_hex': bytes_to_hex(data),
                    })
                    chunks += 1
            time.sleep(0.001)

        print(f'[route2] IMU raw capture done, chunks={chunks}, file={output_path}')
    finally:
        writer.close()
        if ser and ser.is_open:
            ser.close()


if __name__ == '__main__':
    run_capture()
