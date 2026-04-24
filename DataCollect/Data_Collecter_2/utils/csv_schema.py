# -*- coding: utf-8 -*-
"""
CSV schema 与行展开工具
"""
try:
    from DataCollect.Data_Collecter_2 import config
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
    ]

    for seg in config.VICON_SEGS:
        coords = record.vicon_seg_data.get(seg, {"X": 0.0, "Y": 0.0, "Z": 0.0})
        row.extend([coords['X'], coords['Y'], coords['Z']])

    for marker in config.VICON_MARKERS:
        coords = record.vicon_marker_data.get(marker, {"X": 0.0, "Y": 0.0, "Z": 0.0})
        row.extend([coords['X'], coords['Y'], coords['Z']])

    for imu_name in config.IMU_NAMES:
        d = record.imu_data.get(imu_name, {
            "Acc": {"X": 0.0, "Y": 0.0, "Z": 0.0},
            "Gyro": {"X": 0.0, "Y": 0.0, "Z": 0.0},
            "Euler": {"Roll": 0.0, "Pitch": 0.0, "Yaw": 0.0},
            "Quat": {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0}
        })
        row.extend([
            d['Acc']['X'], d['Acc']['Y'], d['Acc']['Z'],
            d['Gyro']['X'], d['Gyro']['Y'], d['Gyro']['Z'],
            d['Euler']['Roll'], d['Euler']['Pitch'], d['Euler']['Yaw'],
            d['Quat']['x'], d['Quat']['y'], d['Quat']['z'], d['Quat']['w']
        ])

    left = record.planter_data.get('Left', [0] * config.PLANTER_SENSOR_POINTS)
    right = record.planter_data.get('Right', [0] * config.PLANTER_SENSOR_POINTS)
    left = (left + [0] * config.PLANTER_SENSOR_POINTS)[:config.PLANTER_SENSOR_POINTS]
    right = (right + [0] * config.PLANTER_SENSOR_POINTS)[:config.PLANTER_SENSOR_POINTS]
    row.extend(left)
    row.extend(right)

    return row


def imu_raw_packet_to_rows(packet):
    rows = []
    for device_name, d in packet.data.items():
        rows.append([
            packet.recv_timestamp,
            device_name,
            d['Acc']['X'], d['Acc']['Y'], d['Acc']['Z'],
            d['Gyro']['X'], d['Gyro']['Y'], d['Gyro']['Z'],
            d['Euler']['Roll'], d['Euler']['Pitch'], d['Euler']['Yaw'],
            d['Quat']['x'], d['Quat']['y'], d['Quat']['z'], d['Quat']['w']
        ])
    return rows


def planter_raw_packet_to_rows(packet):
    left = [packet.recv_timestamp, 'Left'] + packet.left[:config.PLANTER_SENSOR_POINTS]
    right = [packet.recv_timestamp, 'Right'] + packet.right[:config.PLANTER_SENSOR_POINTS]
    return [left, right]
