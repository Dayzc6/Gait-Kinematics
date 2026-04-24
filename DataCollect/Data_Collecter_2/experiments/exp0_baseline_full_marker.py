# -*- coding: utf-8 -*-
"""
实验0：基线实验（全量字段）
- 获取 frame_num + recv_timestamp + 全量 marker
- 用于与当前主系统结果对照
"""
import os
import sys
import time

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)
ROOT_DIR = os.path.dirname(CURRENT_DIR)
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from common import connect_vicon, get_first_subject_name, make_experiment_filename, write_rows, summarize_frame_quality, print_summary
import config

DURATION_SECONDS = 20


def run_experiment():
    client = connect_vicon(enable_segment=False, enable_marker=True)
    try:
        subject_name = get_first_subject_name(client)
        markers = config.VICON_MARKERS
        headers = ['frame_num', 'recv_timestamp']
        for marker in markers:
            headers.extend([f'{marker}_x', f'{marker}_y', f'{marker}_z'])

        rows = []
        start = time.time()
        while time.time() - start < DURATION_SECONDS:
            if client.GetFrame():
                recv_ts = time.time()
                frame_num = client.GetFrameNumber()
                row = [frame_num, recv_ts]
                for marker in markers:
                    try:
                        pos, occluded = client.GetMarkerGlobalTranslation(subject_name, marker)
                        if not occluded:
                            row.extend([pos[0], pos[1], pos[2]])
                        else:
                            row.extend([0.0, 0.0, 0.0])
                    except Exception:
                        row.extend([0.0, 0.0, 0.0])
                rows.append(row)

        filename = make_experiment_filename('exp0_baseline_full_marker')
        write_rows(filename, headers, rows)
        summary = summarize_frame_quality(rows)
        print_summary(summary, 'exp0_baseline_full_marker')
        print(f"CSV 已保存: {filename}")
    finally:
        client.Disconnect()


if __name__ == '__main__':
    run_experiment()
