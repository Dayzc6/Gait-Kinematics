# -*- coding: utf-8 -*-
"""
实验2：segment-only
- 获取 frame_num + recv_timestamp + 全量 segment
- 不读取 marker
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
    client = connect_vicon(enable_segment=True, enable_marker=False)
    try:
        subject_name = get_first_subject_name(client)
        segs = config.VICON_SEGS
        headers = ['frame_num', 'recv_timestamp']
        for seg in segs:
            headers.extend([f'{seg}_x', f'{seg}_y', f'{seg}_z'])

        rows = []
        start = time.time()
        while time.time() - start < DURATION_SECONDS:
            if client.GetFrame():
                recv_ts = time.time()
                frame_num = client.GetFrameNumber()
                row = [frame_num, recv_ts]
                for seg in segs:
                    try:
                        pos, occluded = client.GetSegmentGlobalTranslation(subject_name, seg)
                        if not occluded:
                            row.extend([pos[0], pos[1], pos[2]])
                        else:
                            row.extend([0.0, 0.0, 0.0])
                    except Exception:
                        row.extend([0.0, 0.0, 0.0])
                rows.append(row)

        filename = make_experiment_filename('exp2_segment_only')
        write_rows(filename, headers, rows)
        summary = summarize_frame_quality(rows)
        print_summary(summary, 'exp2_segment_only')
        print(f"CSV 已保存: {filename}")
    finally:
        client.Disconnect()


if __name__ == '__main__':
    run_experiment()
