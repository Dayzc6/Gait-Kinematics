# -*- coding: utf-8 -*-
"""
独立实时采集通用工具
- 会话目录创建
- CSV writer
- metadata 写入
"""
import csv
import json
import os
import time
from datetime import datetime
from threading import Lock


MODULE_DIR = os.path.dirname(os.path.abspath(__file__))
SESSIONS_DIR = os.path.join(MODULE_DIR, 'sessions')
os.makedirs(SESSIONS_DIR, exist_ok=True)


def make_session_id(prefix: str = 'session') -> str:
    return f"{prefix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"


def create_session_dir(session_id: str) -> str:
    session_dir = os.path.join(SESSIONS_DIR, session_id)
    os.makedirs(session_dir, exist_ok=True)
    return session_dir


def now_wall() -> float:
    return time.time()


def now_mono() -> float:
    return time.perf_counter()


class CsvStreamWriter:
    def __init__(self, file_path: str, headers):
        self.file_path = file_path
        self.headers = list(headers)
        self.fp = open(file_path, 'w', newline='', encoding='utf-8')
        self.writer = csv.writer(self.fp)
        self.writer.writerow(self.headers)
        self.lock = Lock()

    def write_row(self, row):
        with self.lock:
            self.writer.writerow(row)

    def flush(self):
        with self.lock:
            self.fp.flush()

    def close(self):
        try:
            with self.lock:
                self.fp.flush()
                self.fp.close()
        except Exception:
            pass


def write_metadata(file_path: str, metadata: dict):
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)
