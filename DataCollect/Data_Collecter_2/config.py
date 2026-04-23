# -*- coding: utf-8 -*-
"""
全局配置模块 - DataCollecter_2
包含Vicon、IMU、Planter的所有配置参数，以及CSV表头定义
"""
import os
import sys
import time

# 添加项目根目录到路径，以便导入Vicon SDK
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

# ==================== 目录配置 ====================
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(PROJECT_ROOT, "data")

# 确保data目录存在
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

# ==================== IMU 配置 ====================
IMU_PORT = 'COM12'
IMU_BAUDRATE = 460800
IMU_TIMEOUT = 0.1
IMU_FRAME_HEAD = b'\x55'
IMU_FRAME_TOTAL_LEN = 29

# IMU设备ID与名称映射
IMU_DICT = {
    0x09: "Trunk",
    0x0A: "L_Femur",
    0x0B: "L_Tibia",
    0x0C: "L_Foot",
    0x0D: "R_Femur",
    0x0E: "R_Tibia",
    0x0F: "R_Foot"
}
IMU_NAMES = list(IMU_DICT.values())

# ==================== Planter 配置 ====================
PLANTER_PORT = 'COM11'
PLANTER_BAUD_RATE = 115200
PLANTER_TIMEOUT = 2
PLANTER_SENSOR_POINTS = 18
PLANTER_FRAME_HEADER = 0xAA
PLANTER_FRAME_LENGTH_CANDIDATES = (39, 38)

# ==================== Vicon 配置 ====================
VICON_HOST_IP = "192.168.137.157"

# ==================== 采样配置 ====================
RECORDING_INTERVAL = 0.001  # 记录线程轮询间隔（秒），约1000Hz检测帧号变化

# ==================== Vicon动态获取函数 ====================
def get_vicon_segs():
    """
    连接Vicon并获取Subject的Segment列表
    返回: segment名称列表
    """
    try:
        import vicon_dssdk.ViconDataStream as VDS
    except ImportError:
        print("[ERROR] 无法导入Vicon SDK，请确保已安装vicon-dssdk")
        return []

    temp_client = VDS.Client()
    print(f"[INFO] 正在连接Vicon: {VICON_HOST_IP} ...")
    
    try:
        temp_client.Connect(VICON_HOST_IP)
    except Exception as e:
        print(f"[ERROR] Vicon连接失败: {e}")
        return []
    
    print(f"[INFO] Vicon连接状态: {temp_client.IsConnected()}")
    temp_client.EnableSegmentData()

    try:
        temp_client.SetStreamMode(0)  # Pull模式
    except:
        pass

    segs = []
    for _ in range(10):
        if temp_client.GetFrame():
            subjects = temp_client.GetSubjectNames()
            if subjects:
                s_name = subjects[0]
                print(f"[INFO] Subject名称: {s_name}")
                segs = temp_client.GetSegmentNames(s_name)
                break
        time.sleep(0.1)

    temp_client.Disconnect()
    print(f"[INFO] 获取到Segments: {segs}")
    return segs


def get_vicon_markers():
    """
    连接Vicon并获取Subject的Marker列表
    返回: marker名称列表
    """
    try:
        import vicon_dssdk.ViconDataStream as VDS
    except ImportError:
        print("[ERROR] 无法导入Vicon SDK")
        return []

    temp_client = VDS.Client()
    temp_client.Connect(VICON_HOST_IP)
    temp_client.EnableMarkerData()

    try:
        temp_client.SetStreamMode(0)
    except:
        pass

    markers = []
    for _ in range(10):
        if temp_client.GetFrame():
            subjects = temp_client.GetSubjectNames()
            if subjects:
                s_name = subjects[0]
                raw_markers = temp_client.GetMarkerNames(s_name)

                # 兼容性解析：提取纯字符串列表
                temp_markers = []
                if isinstance(raw_markers, tuple) and len(raw_markers) == 2:
                    raw_list = raw_markers[1]
                else:
                    raw_list = raw_markers

                for m in raw_list:
                    if isinstance(m, (tuple, list)):
                        temp_markers.append(m[0])
                    else:
                        temp_markers.append(m)

                markers = temp_markers
                if markers:
                    break
        time.sleep(0.1)

    temp_client.Disconnect()
    print(f"[INFO] 获取到Markers: {markers}")
    return markers


# 动态获取ViconSegments和Markers（启动时获取一次）
print("[INFO] 正在初始化Vicon配置...")
VICON_SEGS = get_vicon_segs()
VICON_MARKERS = get_vicon_markers()


# ==================== CSV表头生成 ====================
def generate_csv_headers():
    """
    生成CSV文件的表头
    按照Whole_data_4格式，包含Vicon、IMU、Planter数据
    新增：IsDuplicate列标记重复帧
    """
    headers = []

    # 基础列
    headers.extend(['Timestamp', 'Vicon_Frame_Num', 'IsDuplicate'])

    # Vicon Segment数据
    for seg in VICON_SEGS:
        headers.extend([f'Vicon_{seg}_X', f'Vicon_{seg}_Y', f'Vicon_{seg}_Z'])

    # Vicon Marker数据
    for marker in VICON_MARKERS:
        headers.extend([f'Vicon_{marker}_X', f'Vicon_{marker}_Y', f'Vicon_{marker}_Z'])

    # IMU数据（Acc, Gyro, Euler, Quat）
    for name in IMU_NAMES:
        headers.extend([
            f'IMU_{name}_Acc_X', f'IMU_{name}_Acc_Y', f'IMU_{name}_Acc_Z',
            f'IMU_{name}_Gyro_X', f'IMU_{name}_Gyro_Y', f'IMU_{name}_Gyro_Z',
            f'IMU_{name}_Roll', f'IMU_{name}_Pitch', f'IMU_{name}_Yaw',
            f'IMU_{name}_Quat_x', f'IMU_{name}_Quat_y', f'IMU_{name}_Quat_z', f'IMU_{name}_Quat_w'
        ])

    # Planter数据：Left_0~17, Right_0~17
    for side in ['Left', 'Right']:
        for i in range(PLANTER_SENSOR_POINTS):
            headers.append(f'Planter_{side}_{i}')

    return headers