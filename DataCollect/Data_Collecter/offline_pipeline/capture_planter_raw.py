# -*- coding: utf-8 -*-
"""
路线2：Planter 原始字节流采集
记录：
- recv_timestamp
- side
- raw_hex
目标：采集阶段尽量不解算，只保留原始数据与时间戳
"""
import os
import sys
import time
from threading import Thread

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


class SinglePortRecorder(Thread):
    def __init__(self, port, side, writer):
        super().__init__()
        self.daemon = True
        self.port = port
        self.side = side
        self.writer = writer
        self.ser = None
        self.is_running = False
        self.chunk_count = 0

    def run(self):
        try:
            self.ser = serial.Serial(
                self.port,
                config.PLANTER_BAUD_RATE,
                timeout=config.PLANTER_TIMEOUT,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
            )
            print(f'[route2] Planter {self.side} open: {self.port} @ {config.PLANTER_BAUD_RATE}')
        except Exception as e:
            print(f'[route2] Planter {self.side} open failed: {e}')
            return

        self.is_running = True
        end_time = time.time() + DURATION_SECONDS
        try:
            while self.is_running and time.time() < end_time:
                data = self.ser.read(10)
                if data:
                    self.writer.write({
                        'recv_timestamp': time.time(),
                        'side': self.side,
                        'raw_hex': bytes_to_hex(data),
                    })
                    self.chunk_count += 1
                time.sleep(0.001)
        finally:
            if self.ser and self.ser.is_open:
                self.ser.close()

    def stop(self):
        self.is_running = False


def run_capture():
    output_prefix = make_session_prefix('planter_raw')
    output_path = output_prefix + '.jsonl'
    writer = JsonlWriter(output_path)

    left = SinglePortRecorder(config.PLANTER_LEFT_PORT, 'Left', writer)
    right = SinglePortRecorder(config.PLANTER_RIGHT_PORT, 'Right', writer)
    try:
        left.start()
        right.start()
        left.join()
        right.join()
        print(f'[route2] Planter raw capture done, left_chunks={left.chunk_count}, right_chunks={right.chunk_count}, file={output_path}')
    finally:
        left.stop()
        right.stop()
        writer.close()


if __name__ == '__main__':
    run_capture()
