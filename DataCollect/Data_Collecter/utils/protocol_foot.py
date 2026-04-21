# 专门存放足底压力传感器的数据帧解析逻辑
import struct
import time
from config import PLANTER_SENSOR_POINTS

def parse_packet_frame(packet: bytes):
    """
    帧头识别与校验：识别 0xAA 帧头，并验证长度是否满足 38 字节（2字节头 + 18*2数据）。
    物理值转换：将 2 字节原始 uint16 转换为压力值。
    左右脚身份识别：根据帧内第 2 个字节（0x01 或 0x02）判断数据归属。
    """

    """
    解析足底压力原始字节流
    返回：tuple -> (side_id, values_list) 或 None
    """

    # 基础检查：头校验和长度校验 (2 + 18*2 = 38)
    FRAME_HEADER = 0xAA
    if not packet or len(packet) < 2 or packet[0] != FRAME_HEADER:
        return False
    
    # 1. 提取身份标识
    # 0x01 代表左脚，0x02 代表右脚
    sensor_id = packet[1]
    if sensor_id not in (0x01, 0x02):
        return None
    
    # 解析 18 个感应点数据 (小端 uint16)
    # 使用 struct.unpack 一次性解析更高效
    # 'H' 代表 unsigned short (2 bytes)
    try:
        data_part = packet[2:38]
        # 解压成 18 个数字的元组
        values = struct.unpack('<' + 'H' * PLANTER_SENSOR_POINTS, data_part)
        return sensor_id, list(values)
    except Exception as e:
        # print(f"解析足底数据失败: {e}")
        return None

def get_foot_side_name(sensor_id):
    """辅助函数：将ID转换为字符串，方便存入共享字典"""
    return "Foot_L" if sensor_id == 0x01 else "Foot_R"

  
