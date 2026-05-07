# -*- coding: utf-8 -*-
"""
路线2：构建严格成对的 Planter observations
输入：decode_planter_raw.py 输出的左右脚观测
输出：完整双脚 observation jsonl
规则：
- 左右脚都已出现
- 左右脚时间差 <= PLANTER_PAIR_WINDOW_MS
"""
import argparse
import os
import sys

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(CURRENT_DIR)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from common import JsonlWriter, latest_matching_file, make_output_path, read_jsonl

try:
    from DataCollect.Data_Collecter import config
except ImportError:
    import config


def build_observations(input_path: str, output_path: str):
    rows = read_jsonl(input_path)
    latest = {'Left': None, 'Right': None}
    last_observation_ts = None
    count = 0
    writer = JsonlWriter(output_path)
    try:
        for row in rows:
            latest[row['side']] = row
            if latest['Left'] is None or latest['Right'] is None:
                continue

            left_ts = latest['Left']['recv_timestamp']
            right_ts = latest['Right']['recv_timestamp']
            if abs(left_ts - right_ts) * 1000.0 > config.PLANTER_PAIR_WINDOW_MS:
                continue

            observation_ts = max(left_ts, right_ts)
            if last_observation_ts is not None and observation_ts <= last_observation_ts:
                continue

            writer.write({
                'recv_timestamp': observation_ts,
                'left_timestamp': left_ts,
                'right_timestamp': right_ts,
                'left': latest['Left']['values'],
                'right': latest['Right']['values'],
            })
            last_observation_ts = observation_ts
            count += 1
    finally:
        writer.close()

    print(f'[route2] build_planter_observations done, observations={count}, file={output_path}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', help='decoded planter jsonl path')
    parser.add_argument('--output', help='planter observations jsonl path')
    args = parser.parse_args()

    input_path = args.input or latest_matching_file('planter_decoded')
    if not input_path:
        raise SystemExit('No planter_decoded log found')
    output_path = args.output or make_output_path('planter_observations', '.jsonl')
    build_observations(input_path, output_path)
