# -*- coding: utf-8 -*-
"""
Planter（足底压力传感器）协议解析模块
功能：解析0xAA协议帧，提取左右脚各18个感应点的压力数据
"""
import struct
import time

# 尝试导入配置
try:
    from DataCollect.Data_Collecter_2 import config
except ImportError:
    import config


# 协议常量
SENSOR_POINTS = 18
FRAME_HEADER = 0xAA
LEFT_FOOT_ID = 0x01
RIGHT_FOOT_ID = 0x02


def parse_planter_frame(packet):
    """
    解析Planter数据帧（0xAA协议）
    
    帧格式（38-39字节）：
    [0] 0xAA         - 帧头
    [1] foot_id      - 0x01=左脚，0x02=右脚
    [2-37] data      - 18×uint16（小端序）
    
    Args:
        packet: bytes, 原始帧数据
    
    Returns:
        tuple: (side, values_list) 或 None
            - side: "Left" 或 "Right"
            - values_list: 18个压力值的列表
    """
    if not packet or len(packet) < 2:
        return None

    # 帧头校验
    if packet[0] != FRAME_HEADER:
        return None

    # 提取脚ID
    foot_id = packet[1]
    if foot_id not in (LEFT_FOOT_ID, RIGHT_FOOT_ID):
        return None

    # 解析数据（18个uint16，小端）
    try:
        # 尝试38字节格式
        if len(packet) >= 38:
            data_bytes = packet[2:38]
            values = list(struct.unpack('<HHHHHHHHHHHHHHHHHH', data_bytes))
            side = "Left" if foot_id == LEFT_FOOT_ID else "Right"
            return side, values
        # 尝试39字节格式
        elif len(packet) >= 39:
            data_bytes = packet[2:38]  # 取前36字节（18×2）
            if len(data_bytes) >= 36:
                values = list(struct.unpack('<HHHHHHHHHHHHHHHHHH', data_bytes))
                side = "Left" if foot_id == LEFT_FOOT_ID else "Right"
                return side, values
    except struct.error:
        pass

    return None


def get_foot_side(foot_id):
    """
    将foot_id转换为字符串
    
    Args:
        foot_id: int, 0x01或0x02
    
    Returns:
        str: "Left" 或 "Right"
    """
    return "Left" if foot_id == LEFT_FOOT_ID else "Right"