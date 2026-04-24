# -*- coding: utf-8 -*-
"""
实验结果汇总分析脚本
用法：
python experiments/analyze_results.py experiments/data/xxx.csv
"""
import csv
import os
import sys
from collections import Counter

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)


def analyze_csv(path):
    rows = list(csv.reader(open(path, encoding='utf-8')))
    if len(rows) <= 1:
        print(f"文件无有效数据: {path}")
        return

    data = rows[1:]
    frames = [int(r[0]) for r in data]
    recv_ts = [float(r[1]) for r in data]
    diffs = [b - a for a, b in zip(frames, frames[1:])]
    recv_diffs = [b - a for a, b in zip(recv_ts, recv_ts[1:])]

    gap_rows = sum(1 for d in diffs if d != 1)
    gap_sum = sum(max(0, d - 1) for d in diffs)

    print("=" * 60)
    print(f"分析文件: {os.path.basename(path)}")
    print("=" * 60)
    print(f"rows: {len(data)}")
    print(f"first_frame: {frames[0]}")
    print(f"last_frame: {frames[-1]}")
    print(f"frame_span: {frames[-1] - frames[0] + 1}")
    print(f"gap_rows: {gap_rows}")
    print(f"gap_sum: {gap_sum}")
    print(f"diff_counter_top10: {Counter(diffs).most_common(10)}")
    if recv_diffs:
        avg_dt = sum(recv_diffs) / len(recv_diffs)
        print(f"avg_recv_dt: {avg_dt}")
        print(f"min_recv_dt: {min(recv_diffs)}")
        print(f"max_recv_dt: {max(recv_diffs)}")
        print(f"effective_hz: {1.0 / avg_dt if avg_dt > 0 else 'inf'}")
    print("=" * 60)


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("用法: python experiments/analyze_results.py experiments/data/xxx.csv")
        sys.exit(1)
    analyze_csv(sys.argv[1])
