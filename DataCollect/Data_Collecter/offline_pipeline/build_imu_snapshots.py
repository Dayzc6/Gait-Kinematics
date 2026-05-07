# -*- coding: utf-8 -*-
"""
路线2：构建严格完整的 IMU observations
输入：decode_imu_raw.py 输出的设备级观测
输出：完整 IMU observation jsonl
规则：
- 7 个设备都已出现
- 最早/最晚设备时间差 <= IMU_SNAPSHOT_WINDOW_MS
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
    latest_data = {name: None for name in config.IMU_NAMES}
    latest_ts = {name: None for name in config.IMU_NAMES}
    last_observation_ts = None
    count = 0
    writer = JsonlWriter(output_path)
    try:
        for row in rows:
            name = row['device_name']
            latest_data[name] = row['imu_data']
            latest_ts[name] = row['recv_timestamp']

            if any(ts is None for ts in latest_ts.values()):
                continue

            min_ts = min(latest_ts.values())
            max_ts = max(latest_ts.values())
            if (max_ts - min_ts) * 1000.0 > config.IMU_SNAPSHOT_WINDOW_MS:
                continue

            observation_ts = max_ts
            if last_observation_ts is not None and observation_ts <= last_observation_ts:
                continue

            writer.write({
                'recv_timestamp': observation_ts,
                'device_timestamps': dict(latest_ts),
                'data': dict(latest_data),
            })
            last_observation_ts = observation_ts
            count += 1
    finally:
        writer.close()

    print(f'[route2] build_imu_observations done, observations={count}, file={output_path}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', help='decoded imu jsonl path')
    parser.add_argument('--output', help='imu observation jsonl path')
    args = parser.parse_args()

    input_path = args.input or latest_matching_file('imu_decoded')
    if not input_path:
        raise SystemExit('No imu_decoded log found')
    output_path = args.output or make_output_path('imu_observations', '.jsonl')
    build_observations(input_path, output_path)
