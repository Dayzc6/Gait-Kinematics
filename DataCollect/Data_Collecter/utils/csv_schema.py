# -*- coding: utf-8 -*-
"""
CSV schema 与行展开工具
"""
import os
import sys

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(CURRENT_DIR)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

try:
    from DataCollect.Data_Collecter import config
except ImportError:
    import config


def synced_record_to_row(record):
    row = [
        record.timestamp,
        record.vicon_frame_num,
        record.vicon_recv_timestamp,
        record.imu_recv_timestamp if record.imu_recv_timestamp is not None else '',
        record.planter_recv_timestamp if record.planter_recv_timestamp is not None else '',
        record.vicon_gap_flag,
        record.vicon_gap_size,
        record.imu_stale_ms if record.imu_stale_ms is not None else '',
        record.planter_stale_ms if record.planter_stale_ms is not None else '',
        record.imu_matched_flag,
        record.planter_matched_flag,
        record.imu_matched_count,
        record.planter_matched_count,
        record.imu_all_matched_flag,
        record.planter_both_matched_flag,
        record.vicon_original_valid_flag,
        record.vicon_held_flag,
        record.vicon_timeout_zero_flag,
    ]

    for seg in config.VICON_SEGS:
        coords = record.vicon_seg_data.get(seg, {'X': 0.0, 'Y': 0.0, 'Z': 0.0})
        row.extend([coords['X'], coords['Y'], coords['Z']])

    for marker in config.VICON_MARKERS:
        coords = record.vicon_marker_data.get(marker, {'X': 0.0, 'Y': 0.0, 'Z': 0.0})
        row.extend([coords['X'], coords['Y'], coords['Z']])

    for imu_name in config.IMU_NAMES:
        row.extend([
            record.imu_device_matched_flags.get(imu_name, 0),
            record.imu_device_held_flags.get(imu_name, 0),
            record.imu_device_timeout_zero_flags.get(imu_name, 0),
            record.imu_device_recv_timestamps.get(imu_name, '') if record.imu_device_recv_timestamps.get(imu_name) is not None else '',
            record.imu_device_stale_ms.get(imu_name, '') if record.imu_device_stale_ms.get(imu_name) is not None else '',
        ])
        d = record.imu_data.get(imu_name, {
            'Acc': {'X': 0.0, 'Y': 0.0, 'Z': 0.0},
            'Gyro': {'X': 0.0, 'Y': 0.0, 'Z': 0.0},
            'Euler': {'Roll': 0.0, 'Pitch': 0.0, 'Yaw': 0.0},
            'Quat': {'x': 0.0, 'y': 0.0, 'z': 0.0, 'w': 1.0},
        })
        row.extend([
            d['Acc']['X'], d['Acc']['Y'], d['Acc']['Z'],
            d['Gyro']['X'], d['Gyro']['Y'], d['Gyro']['Z'],
            d['Euler']['Roll'], d['Euler']['Pitch'], d['Euler']['Yaw'],
            d['Quat']['x'], d['Quat']['y'], d['Quat']['z'], d['Quat']['w'],
        ])

    for side in ['Left', 'Right']:
        row.extend([
            record.planter_side_matched_flags.get(side, 0),
            record.planter_side_held_flags.get(side, 0),
            record.planter_side_zero_confirmed_flags.get(side, 0),
            record.planter_side_timeout_zero_flags.get(side, 0),
            record.planter_side_recv_timestamps.get(side, '') if record.planter_side_recv_timestamps.get(side) is not None else '',
            record.planter_side_stale_ms.get(side, '') if record.planter_side_stale_ms.get(side) is not None else '',
        ])
        values = record.planter_data.get(side, [0] * config.PLANTER_SENSOR_POINTS)
        values = (values + [0] * config.PLANTER_SENSOR_POINTS)[:config.PLANTER_SENSOR_POINTS]
        row.extend(values)

    return row
