# -*- coding: utf-8 -*-
"""
实验4：frame-only（带固定sleep）
- 只获取 frame_num + recv_timestamp
- 每轮 GetFrame 成功后额外 sleep 1ms
- 用于验证 worker_vicon 中固定 sleep 是否会显著拉低接收频率
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
SLEEP_SECONDS = 0.001


def run_experiment():
    client = connect_vicon(enable_segment=False, enable_marker=False)
    try:
        diagnostics = collect_runtime_diagnostics(client)
        diagnostics['loop_sleep_seconds'] = SLEEP_SECONDS
        print_runtime_diagnostics(diagnostics, 'exp4_frame_only_with_sleep')

        headers = ['frame_num', 'recv_timestamp']
        rows = []
        start = time.time()
        while time.time() - start < DURATION_SECONDS:
            if client.GetFrame():
                recv_ts = time.time()
                frame_num = client.GetFrameNumber()
                rows.append([frame_num, recv_ts])
                time.sleep(SLEEP_SECONDS)

        filename = make_experiment_filename('exp4_frame_only_with_sleep')
        write_rows(filename, headers, rows)
        summary = summarize_frame_quality(rows)
        print_summary(summary, 'exp4_frame_only_with_sleep')
        print(f"CSV 已保存: {filename}")
    finally:
        client.Disconnect()


if __name__ == '__main__':
    run_experiment()
