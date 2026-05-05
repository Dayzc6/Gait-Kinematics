# -*- coding: utf-8 -*-
"""
写盘线程
- 只从 write_queue 接收同步记录
- 批量写入单一主文件 synced.csv
- 不再额外输出 imu_raw.csv / planter_raw.csv，以降低系统负载
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
    from DataCollect.Data_Collecter import config
    from DataCollect.Data_Collecter.utils.csv_schema import synced_record_to_row
except ImportError:
    import config
    from utils.csv_schema import synced_record_to_row


class WriterWorker(Thread):
    def __init__(self, synced_queue, output_dir=None):
        super().__init__()
        self.daemon = True
        self.synced_queue = synced_queue
        self.output_dir = output_dir or config.DATA_DIR
        os.makedirs(self.output_dir, exist_ok=True)

        timestamp_str = datetime.now().strftime('%Y%m%d_%H%M%S')
        self.synced_filename = os.path.join(self.output_dir, f'subject_trial_{timestamp_str}_synced.csv')

        self.is_running = False
        self._init_files()

    def _init_files(self):
        with open(self.synced_filename, 'w', newline='', encoding='utf-8') as f:
            csv.writer(f).writerow(config.generate_synced_headers())
        print(f'[WriterWorker] 已创建文件: {self.synced_filename}')

    def run(self):
        self.is_running = True
        synced_batch = []
        last_flush = time.time()

        print('[WriterWorker] 写盘线程启动')
        while self.is_running or not self.synced_queue.empty():
            self._drain_queue(self.synced_queue, synced_batch)

            now = time.time()
            if (
                len(synced_batch) >= config.WRITER_BATCH_SIZE or
                (now - last_flush) >= config.WRITER_FLUSH_INTERVAL
            ):
                self._flush_batch(synced_batch)
                synced_batch.clear()
                last_flush = now

            time.sleep(0.01)

        self._flush_batch(synced_batch)
        print('[WriterWorker] 写盘线程已停止')

    def _drain_queue(self, q, batch):
        while True:
            try:
                item = q.get_nowait()
                batch.append(synced_record_to_row(item))
            except queue.Empty:
                break
            except Exception as e:
                print(f'[WriterWorker] 读取队列异常(synced): {e}')
                break

    def _flush_batch(self, synced_batch):
        if synced_batch:
            with open(self.synced_filename, 'a', newline='', encoding='utf-8') as f:
                csv.writer(f).writerows(synced_batch)

    def stop(self):
        self.is_running = False

    def get_main_filename(self):
        return self.synced_filename

