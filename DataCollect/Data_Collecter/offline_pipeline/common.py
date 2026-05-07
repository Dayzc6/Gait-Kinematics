# -*- coding: utf-8 -*-
"""
route2 通用工具
- 原始采集日志目录创建
- JSON Lines 读写
- 十六进制 bytes 编码/解码
- 查找最新日志文件
- 统一 session 组文件查找
"""
import glob
import json
import os
from datetime import datetime
from typing import Iterable, Optional


PIPELINE_DIR = os.path.dirname(os.path.abspath(__file__))
RAW_DIR = os.path.join(PIPELINE_DIR, 'raw_logs')
os.makedirs(RAW_DIR, exist_ok=True)


def make_session_prefix(prefix: str) -> str:
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    return os.path.join(RAW_DIR, f'{prefix}_{ts}')


def make_output_path(prefix: str, suffix: str) -> str:
    return make_session_prefix(prefix) + suffix


class JsonlWriter:
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.fp = open(file_path, 'w', encoding='utf-8')

    def write(self, record):
        self.fp.write(json.dumps(record, ensure_ascii=False) + '\n')
        self.fp.flush()

    def writemany(self, records: Iterable[dict]):
        for record in records:
            self.write(record)

    def close(self):
        try:
            self.fp.close()
        except Exception:
            pass


def read_jsonl(file_path: str):
    rows = []
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def latest_matching_file(prefix: str, ext: str = '.jsonl') -> Optional[str]:
    pattern = os.path.join(RAW_DIR, f'{prefix}_*{ext}')
    files = sorted(glob.glob(pattern))
    return files[-1] if files else None


def latest_session_prefix() -> Optional[str]:
    files = sorted(glob.glob(os.path.join(RAW_DIR, 'session_*_vicon.jsonl')))
    if not files:
        return None
    latest = files[-1]
    if latest.endswith('_vicon.jsonl'):
        return latest[:-len('_vicon.jsonl')]
    return None


def session_file(session_prefix: str, suffix: str) -> str:
    return f'{session_prefix}_{suffix}.jsonl'


def bytes_to_hex(data: bytes) -> str:
    return data.hex()


def hex_to_bytes(hex_str: str) -> bytes:
    return bytes.fromhex(hex_str)
