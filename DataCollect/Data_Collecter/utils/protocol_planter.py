# -*- coding: utf-8 -*-
"""
Planter（足底压力传感器）协议解析模块
功能：解析0xAA协议帧，提取左右脚各18个感应点的压力数据
"""
import struct

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
    [38] 可选尾字节 / 校验字节
    """
    if not packet or len(packet) not in (38, 39):
        return None

    if packet[0] != FRAME_HEADER:
        return None

    foot_id = packet[1]
    if foot_id not in (LEFT_FOOT_ID, RIGHT_FOOT_ID):
        return None

    try:
        data_bytes = packet[2:38]
        if len(data_bytes) != 36:
            return None
        values = list(struct.unpack('<HHHHHHHHHHHHHHHHHH', data_bytes))
        side = 'Left' if foot_id == LEFT_FOOT_ID else 'Right'
        return side, values
    except struct.error:
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


# ==================== 测试代码 ====================
if __name__ == '__main__':
    print("[TEST] Planter协议解析测试")
    
    # 构造测试帧（左脚）
    test_frame_left = bytes([0xAA, 0x01] + [i for i in range(36)])
    result = parse_planter_frame(test_frame_left)
    if result:
        side, values = result
        print(f"[TEST] 左脚: side={side}, values[:5]={values[:5]}")
    
    # 构造测试帧（右脚）
    test_frame_right = bytes([0xAA, 0x02] + [i for i in range(36)])
    result = parse_planter_frame(test_frame_right)
    if result:
        side, values = result
        print(f"[TEST] 右脚: side={side}, values[:5]={values[:5]}")
    
    print("[TEST] 测试完成")