# -*- coding: utf-8 -*-
"""
路线2：导出最终训练数据集（第一版）
当前版本：
- 读取 aligned jsonl
- 直接导出为 csv
- 保留核心字段，便于先验证路线2整体可运行性
"""
import argparse
import csv
import os
import sys

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(CURRENT_DIR)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from common import latest_matching_file, make_output_path, read_jsonl

try:
    from DataCollect.Data_Collecter import config
except ImportError:
    import config


def export_csv(input_path: str, output_path: str):
    rows = read_jsonl(input_path)
    headers = [
        'frame_num',
        'vicon_recv_timestamp',
        'frame_rate',
        'imu_recv_timestamp',
        'planter_recv_timestamp',
        'imu_matched_flag',
        'planter_matched_flag',
        'imu_stale_ms',
        'planter_stale_ms',
    ]

    for name in config.IMU_NAMES:
        headers.extend([
            f'IMU_{name}_Acc_X', f'IMU_{name}_Acc_Y', f'IMU_{name}_Acc_Z',
            f'IMU_{name}_Gyro_X', f'IMU_{name}_Gyro_Y', f'IMU_{name}_Gyro_Z',
            f'IMU_{name}_Roll', f'IMU_{name}_Pitch', f'IMU_{name}_Yaw',
            f'IMU_{name}_Quat_x', f'IMU_{name}_Quat_y', f'IMU_{name}_Quat_z', f'IMU_{name}_Quat_w',
        ])

    for side in ['Left', 'Right']:
        for i in range(config.PLANTER_SENSOR_POINTS):
            headers.append(f'Planter_{side}_{i}')

    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(headers)

        for row in rows:
            out = [
                row['frame_num'],
                row['vicon_recv_timestamp'],
                row.get('frame_rate'),
                row.get('imu_recv_timestamp'),
                row.get('planter_recv_timestamp'),
                row.get('imu_matched_flag', 0),
                row.get('planter_matched_flag', 0),
                row.get('imu_stale_ms'),
                row.get('planter_stale_ms'),
            ]

            imu_data = row.get('imu_data') or {}
            for name in config.IMU_NAMES:
                d = imu_data.get(name, {
                    'Acc': {'X': 0.0, 'Y': 0.0, 'Z': 0.0},
                    'Gyro': {'X': 0.0, 'Y': 0.0, 'Z': 0.0},
                    'Euler': {'Roll': 0.0, 'Pitch': 0.0, 'Yaw': 0.0},
                    'Quat': {'x': 0.0, 'y': 0.0, 'z': 0.0, 'w': 1.0},
                })
                out.extend([
                    d['Acc']['X'], d['Acc']['Y'], d['Acc']['Z'],
                    d['Gyro']['X'], d['Gyro']['Y'], d['Gyro']['Z'],
                    d['Euler']['Roll'], d['Euler']['Pitch'], d['Euler']['Yaw'],
                    d['Quat']['x'], d['Quat']['y'], d['Quat']['z'], d['Quat']['w'],
                ])

            planter = row.get('planter_data') or {'Left': [0]*config.PLANTER_SENSOR_POINTS, 'Right': [0]*config.PLANTER_SENSOR_POINTS}
            out.extend((planter.get('Left', []) + [0]*config.PLANTER_SENSOR_POINTS)[:config.PLANTER_SENSOR_POINTS])
            out.extend((planter.get('Right', []) + [0]*config.PLANTER_SENSOR_POINTS)[:config.PLANTER_SENSOR_POINTS])
            writer.writerow(out)

    print(f'[route2] export_training_dataset done, rows={len(rows)}, file={output_path}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', help='aligned jsonl path')
    parser.add_argument('--output', help='output csv path')
    args = parser.parse_args()

    input_path = args.input or latest_matching_file('aligned')
    if not input_path:
        raise SystemExit('No aligned log found')
    output_path = args.output or make_output_path('training_dataset', '.csv')
    export_csv(input_path, output_path)
