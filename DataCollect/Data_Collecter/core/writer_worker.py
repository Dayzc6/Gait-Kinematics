# -*- coding: utf-8 -*-
"""
写盘线程
- 从 write_queue 接收同步记录
- 批量写入 synced.csv
- 同时接收 imu_raw / planter_raw 并分别落盘
"""
import csv
import os
import queue
import sys
import time
from datetime import datetime
from threading import Thread

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(CURRENT_DIR)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

try:
    from DataCollect.Data_Collecter_2 import config
    from DataCollect.Data_Collecter_2.utils.csv_schema import (
        synced_record_to_row,
        imu_raw_packet_to_rows,
        planter_raw_packet_to_rows,
    )
except ImportError:
    import config
    from utils.csv_schema import synced_record_to_row, imu_raw_packet_to_rows, planter_raw_packet_to_rows


class WriterWorker(Thread):
    def __init__(self, synced_queue, imu_raw_queue, planter_raw_queue, output_dir=None):
        super().__init__()
        self.daemon = True
        self.synced_queue = synced_queue
        self.imu_raw_queue = imu_raw_queue
        self.planter_raw_queue = planter_raw_queue
        self.output_dir = output_dir or config.DATA_DIR
        os.makedirs(self.output_dir, exist_ok=True)

        timestamp_str = datetime.now().strftime('%Y%m%d_%H%M%S')
        self.synced_filename = os.path.join(self.output_dir, f'subject_trial_{timestamp_str}_synced.csv')
        self.imu_raw_filename = os.path.join(self.output_dir, f'subject_trial_{timestamp_str}_imu_raw.csv')
        self.planter_raw_filename = os.path.join(self.output_dir, f'subject_trial_{timestamp_str}_planter_raw.csv')

        self.is_running = False
        self._init_files()

    def _init_files(self):
        with open(self.synced_filename, 'w', newline='', encoding='utf-8') as f:
            csv.writer(f).writerow(config.generate_synced_headers())
        with open(self.imu_raw_filename, 'w', newline='', encoding='utf-8') as f:
            csv.writer(f).writerow(config.generate_imu_raw_headers())
        with open(self.planter_raw_filename, 'w', newline='', encoding='utf-8') as f:
            csv.writer(f).writerow(config.generate_planter_raw_headers())
        print(f'[WriterWorker] 已创建文件: {self.synced_filename}')

    def run(self):
        self.is_running = True
        synced_batch = []
        imu_batch = []
        planter_batch = []
        last_flush = time.time()

        print('[WriterWorker] 写盘线程启动')
        while self.is_running or not self._all_queues_empty():
            self._drain_queue(self.synced_queue, synced_batch, kind='synced')
            self._drain_queue(self.imu_raw_queue, imu_batch, kind='imu')
            self._drain_queue(self.planter_raw_queue, planter_batch, kind='planter')

            now = time.time()
            if (
                len(synced_batch) >= config.WRITER_BATCH_SIZE or
                len(imu_batch) >= config.WRITER_BATCH_SIZE or
                len(planter_batch) >= config.WRITER_BATCH_SIZE or
                (now - last_flush) >= config.WRITER_FLUSH_INTERVAL
            ):
                self._flush_batches(synced_batch, imu_batch, planter_batch)
                synced_batch.clear()
                imu_batch.clear()
                planter_batch.clear()
                last_flush = now

            time.sleep(0.01)

        self._flush_batches(synced_batch, imu_batch, planter_batch)
        print('[WriterWorker] 写盘线程已停止')

    def _drain_queue(self, q, batch, kind='synced'):
        while True:
            try:
                item = q.get_nowait()
                if kind == 'synced':
                    batch.append(synced_record_to_row(item))
                elif kind == 'imu':
                    batch.extend(imu_raw_packet_to_rows(item))
                elif kind == 'planter':
                    batch.extend(planter_raw_packet_to_rows(item))
            except queue.Empty:
                break
            except Exception as e:
                print(f'[WriterWorker] 读取队列异常({kind}): {e}')
                break

    def _flush_batches(self, synced_batch, imu_batch, planter_batch):
        if synced_batch:
            with open(self.synced_filename, 'a', newline='', encoding='utf-8') as f:
                csv.writer(f).writerows(synced_batch)
        if imu_batch:
            with open(self.imu_raw_filename, 'a', newline='', encoding='utf-8') as f:
                csv.writer(f).writerows(imu_batch)
        if planter_batch:
            with open(self.planter_raw_filename, 'a', newline='', encoding='utf-8') as f:
                csv.writer(f).writerows(planter_batch)

    def _all_queues_empty(self):
        return self.synced_queue.empty() and self.imu_raw_queue.empty() and self.planter_raw_queue.empty()

    def stop(self):
        self.is_running = False

    def get_main_filename(self):
        return self.synced_filename
