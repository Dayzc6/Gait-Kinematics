# -*- coding: utf-8 -*-
"""
路线2：对齐并重采样到 Vicon 时间轴
输入：
- session vicon jsonl
- imu observations jsonl
- planter observations jsonl
输出：aligned dataset jsonl
规则：
- 以 Vicon frame_num + recv_timestamp 为主轴
- 只允许历史且在窗口内的 IMU / Planter observations 匹配
- 当前第一版采用“Vicon 时间轴上的最近历史观测”策略，后续可扩展为更复杂重采样方法
"""
import argparse
import os
import sys

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(CURRENT_DIR)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from common import JsonlWriter, latest_matching_file, latest_session_prefix, make_output_path, read_jsonl, session_file

try:
    from DataCollect.Data_Collecter import config
except ImportError:
    import config


def find_best_history(rows, target_ts, max_lag_ms):
    candidates = [r for r in rows if r['recv_timestamp'] <= target_ts]
    if not candidates:
        return None
    pkt = max(candidates, key=lambda x: x['recv_timestamp'])
    lag_ms = (target_ts - pkt['recv_timestamp']) * 1000.0
    if lag_ms < 0 or lag_ms > max_lag_ms:
        return None
    return pkt


def align(vicon_path: str, imu_path: str, planter_path: str, output_path: str):
    vicon_rows = read_jsonl(vicon_path)
    imu_rows = read_jsonl(imu_path) if imu_path else []
    planter_rows = read_jsonl(planter_path) if planter_path else []

    writer = JsonlWriter(output_path)
    count = 0
    try:
        for row in vicon_rows:
            ts = row['recv_timestamp']
            imu_pkt = find_best_history(imu_rows, ts, config.IMU_MAX_LAG_MS)
            planter_pkt = find_best_history(planter_rows, ts, config.PLANTER_MAX_LAG_MS)
            writer.write({
                'frame_num': row['frame_num'],
                'vicon_recv_timestamp': ts,
                'frame_rate': row.get('frame_rate'),
                'imu_recv_timestamp': imu_pkt['recv_timestamp'] if imu_pkt else None,
                'planter_recv_timestamp': planter_pkt['recv_timestamp'] if planter_pkt else None,
                'imu_matched_flag': 1 if imu_pkt else 0,
                'planter_matched_flag': 1 if planter_pkt else 0,
                'imu_stale_ms': ((ts - imu_pkt['recv_timestamp']) * 1000.0) if imu_pkt else None,
                'planter_stale_ms': ((ts - planter_pkt['recv_timestamp']) * 1000.0) if planter_pkt else None,
                'imu_data': imu_pkt['data'] if imu_pkt else None,
                'planter_data': {
                    'Left': planter_pkt['left'],
                    'Right': planter_pkt['right'],
                } if planter_pkt else None,
            })
            count += 1
    finally:
        writer.close()

    print(f'[route2] align_to_vicon done, rows={count}, file={output_path}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--vicon', help='vicon minimal/session jsonl path')
    parser.add_argument('--imu', help='imu observations jsonl path')
    parser.add_argument('--planter', help='planter observations jsonl path')
    parser.add_argument('--output', help='aligned jsonl path')
    args = parser.parse_args()

    vicon_path = args.vicon
    if not vicon_path:
        session_prefix = latest_session_prefix()
        if session_prefix:
            candidate = session_file(session_prefix, 'vicon')
            if os.path.exists(candidate):
                vicon_path = candidate
    if not vicon_path:
        vicon_path = latest_matching_file('vicon_minimal')
    if not vicon_path:
        raise SystemExit('No Vicon log found')

    imu_path = args.imu or latest_matching_file('imu_observations')
    planter_path = args.planter or latest_matching_file('planter_observations')
    output_path = args.output or make_output_path('aligned', '.jsonl')
    align(vicon_path, imu_path, planter_path, output_path)
