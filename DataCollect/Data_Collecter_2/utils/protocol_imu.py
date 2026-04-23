# -*- coding: utf-8 -*-
"""
IMU协议解析模块
功能：解析IMU串口发送的0x55协议帧，计算加速度、角速度、欧拉角和四元数
"""
import numpy as np
from scipy.spatial.transform import Rotation as R


def to_signed_short(raw):
    """
    将无符号uint16转换为有符号int16
    
    Args:
        raw: int, 0-65535范围内的无符号数
    
    Returns:
        int, -32768~32767范围内的有符号数
    """
    return raw if raw <= 0x7FFF else raw - 0x10000


def parse_imu_frame(frame):
    """
    解析IMU数据帧（0x55协议）
    
    帧格式（29字节）：
    [0] device_id   - 设备ID (0x09-0x0F)
    [1] 0x55      - 帧头标志
    [2] flag       - 0x61
    [3-4] ax      - 加速度X (int16, 小端)
    [5-6] ay      - 加速度Y
    [7-8] az      - 加速度Z
    [9-10] gx     - 角速度X
    [11-12] gy     - 角速度Y
    [13-14] gz     - 角速度Z
    [15-20] 保留
    [21-22] r      - Roll (int16)
    [23-24] p      - Pitch
    [25-26] y      - Yaw
    [27-28] 校验和
    
    物理转换：
    - 加速度: ±16g -> (raw/32768)*16*9.8 m/s²
    - 角速度: ±2000°/s -> (raw/32768)*2000 °/s
    - 欧拉角: ±180° -> (raw/32768)*180 °
    
    Args:
        frame: bytes, 29字节的原始帧数据
    
    Returns:
        tuple: (device_id, imu_data_dict) 或 None
            - device_id: int, 设备ID
            - imu_data_dict: dict, 包含Acc/Gyro/Euler/Quat数据的字典
    """
    if not frame or len(frame) < 29:
        return None

    # 基础校验
    if frame[1] != 0x55:
        return None

    dev_id = frame[0]
    flag = frame[2]

    # 只解析有效帧（flag=0x61）
    if flag != 0x61:
        return None

    # 解析加速度（3轴，int16小端）
    ax = to_signed_short((frame[4] << 8) | frame[3])
    ay = to_signed_short((frame[6] << 8) | frame[5])
    az = to_signed_short((frame[8] << 8) | frame[7])

    # 解析角速度（3轴）
    gx = to_signed_short((frame[10] << 8) | frame[9])
    gy = to_signed_short((frame[12] << 8) | frame[11])
    gz = to_signed_short((frame[14] << 8) | frame[13])

    # 解析欧拉角（Roll, Pitch, Yaw）
    r = to_signed_short((frame[22] << 8) | frame[21])
    p = to_signed_short((frame[24] << 8) | frame[23])
    y = to_signed_short((frame[26] << 8) | frame[25])

    # 转换为物理值
    roll_deg = round((r / 32768) * 180, 4)
    pitch_deg = round((p / 32768) * 180, 4)
    yaw_deg = round((y / 32768) * 180, 4)

    # 欧拉角转四元数
    rot = R.from_euler('zyx', [yaw_deg, pitch_deg, roll_deg], degrees=True)
    quat = rot.as_quat()
    quat = quat / np.linalg.norm(quat)

    # 构建IMU数据字典
    imu_data = {
        "Acc": {
            "X": round((ax / 32768) * 16 * 9.8, 4),
            "Y": round((ay / 32768) * 16 * 9.8, 4),
            "Z": round((az / 32768) * 16 * 9.8, 4)
        },
        "Gyro": {
            "X": round((gx / 32768) * 2000, 4),
            "Y": round((gy / 32768) * 2000, 4),
            "Z": round((gz / 32768) * 2000, 4)
        },
        "Euler": {
            "Roll": roll_deg,
            "Pitch": pitch_deg,
            "Yaw": yaw_deg
        },
        "Quat": {
            "x": round(quat[0], 4),
            "y": round(quat[1], 4),
            "z": round(quat[2], 4),
            "w": round(quat[3], 4)
        }
    }

    return dev_id, imu_data