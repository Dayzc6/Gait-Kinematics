# -*- coding: utf-8 -*-
"""
实验1：frame-only
- 只获取 frame_num + recv_timestamp
- 不读取任何 segment / marker
- 用于验证 SDK/网络基础拉流能力
- 补充运行时诊断：GetFrameRate / subject 数量等
"""
import os
import sys
import time

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

from common import (
    connect_vicon,
    make_experiment_filename,
    write_rows,
    summarize_frame_quality,
    print_summary,
    collect_runtime_diagnostics,
    print_runtime_diagnostics,
)

DURATION_SECONDS = 20


def run_experiment():
    client = connect_vicon(enable_segment=False, enable_marker=False)
    try:
        diagnostics = collect_runtime_diagnostics(client)
        print_runtime_diagnostics(diagnostics, 'exp1_frame_only')

        headers = ['frame_num', 'recv_timestamp']
        rows = []
        start = time.time()
        while time.time() - start < DURATION_SECONDS:
            if client.GetFrame():
                print(client.GetFrameRates())
                recv_ts = time.time()
                frame_num = client.GetFrameNumber()
                rows.append([frame_num, recv_ts])

        filename = make_experiment_filename('exp1_frame_only')
        write_rows(filename, headers, rows)
        summary = summarize_frame_quality(rows)
        print_summary(summary, 'exp1_frame_only')
        print(f"CSV 已保存: {filename}")
    finally:
        client.Disconnect()


if __name__ == '__main__':
    run_experiment()
