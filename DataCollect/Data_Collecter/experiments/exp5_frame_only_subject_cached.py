# -*- coding: utf-8 -*-
"""
实验5：frame-only（缓存subject名 + 运行时诊断）
- 先获取一次 subject_name
- 正式采集阶段只获取 frame_num + recv_timestamp
- 用于验证 GetSubjectNames 等诊断调用是否影响基础接收表现
"""
import os
import sys
import time

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

from common import (
    connect_vicon,
    get_first_subject_name,
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
        subject_name = get_first_subject_name(client)
        diagnostics = collect_runtime_diagnostics(client, subject_name=subject_name)
        diagnostics['subject_cached_before_capture'] = True
        print_runtime_diagnostics(diagnostics, 'exp5_frame_only_subject_cached')

        headers = ['frame_num', 'recv_timestamp']
        rows = []
        start = time.time()
        while time.time() - start < DURATION_SECONDS:
            if client.GetFrame():
                recv_ts = time.time()
                frame_num = client.GetFrameNumber()
                rows.append([frame_num, recv_ts])

        filename = make_experiment_filename('exp5_frame_only_subject_cached')
        write_rows(filename, headers, rows)
        summary = summarize_frame_quality(rows)
        print_summary(summary, 'exp5_frame_only_subject_cached')
        print(f"CSV 已保存: {filename}")
    finally:
        client.Disconnect()


if __name__ == '__main__':
    run_experiment()
