# -*- coding: utf-8 -*-
"""
路线2：检查原始日志与中间结果是否存在、是否有记录
"""
import glob
import json
import os

from common import RAW_DIR


def validate_file(path):
    rows = 0
    sample = None
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            rows += 1
            if sample is None:
                sample = obj
    return {'file': os.path.basename(path), 'rows': rows, 'sample': sample}


def main():
    files = sorted(glob.glob(os.path.join(RAW_DIR, '*.jsonl')))
    if not files:
        print('[route2] no raw/intermediate logs found')
        return
    for p in files:
        print(validate_file(p))


if __name__ == '__main__':
    main()
