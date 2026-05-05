# -*- coding: utf-8 -*-
"""
独立实时采集本地配置
- 包含 Vicon / IMU / Planter 独立采集所需字段
- 明确避免导入主 config.py 触发副作用
"""

# ==================== IMU 配置 ====================
IMU_PORT = 'COM9'
IMU_BAUDRATE = 460800
IMU_TIMEOUT = 0.1
IMU_FRAME_TOTAL_LEN = 29

IMU_DICT = {
    0x09: 'Trunk',
    0x0A: 'L_Femur',
    0x0B: 'L_Tibia',
    0x0C: 'L_Foot',
    0x0D: 'R_Femur',
    0x0E: 'R_Tibia',
    0x0F: 'R_Foot',
}
IMU_NAMES = list(IMU_DICT.values())

# ==================== Planter 配置 ====================
PLANTER_LEFT_PORT = 'COM10'
PLANTER_RIGHT_PORT = 'COM13'
PLANTER_BAUD_RATE = 115200
PLANTER_TIMEOUT = 2
PLANTER_SENSOR_POINTS = 18
PLANTER_FRAME_HEADER = 0xAA
PLANTER_FRAME_LENGTH_CANDIDATES = (39, 38)
PLANTER_USE_SAFE_FRAME_PARSER = True

# ==================== Vicon 配置（独立采集） ====================
VICON_HOST_IP = '192.168.10.1'
VICON_STREAM_MODE = 0
VICON_ENABLE_SEGMENTS = False
VICON_RATE_PRINT_INTERVAL = 5.0
