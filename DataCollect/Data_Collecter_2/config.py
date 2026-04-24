# -*- coding: utf-8 -*-
"""
全局配置模块
- 保留 Vicon / IMU / Planter 原始接收逻辑所需参数
- 增加队列、缓冲区、同步质量诊断参数
"""
import os
import sys
import time

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

DATA_DIR = os.path.join(PROJECT_ROOT, "data")
os.makedirs(DATA_DIR, exist_ok=True)

# ==================== IMU 配置 ====================
IMU_PORT = 'COM12'
IMU_BAUDRATE = 460800
IMU_TIMEOUT = 0.1
IMU_FRAME_HEAD = b'\x55'
IMU_FRAME_TOTAL_LEN = 29

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

# ==================== 并发/缓冲配置 ====================
VICON_QUEUE_SIZE = 1000
WRITE_QUEUE_SIZE = 2000
IMU_BUFFER_SIZE = 300          # 约 10 秒 @ 30Hz
PLANTER_BUFFER_SIZE = 200      # 约 10 秒 @ 20Hz
WRITER_BATCH_SIZE = 20
WRITER_FLUSH_INTERVAL = 0.5
SYNC_QUEUE_TIMEOUT = 0.5

# ==================== 质量阈值 ====================
IMU_STALE_WARN_MS = 100.0
PLANTER_STALE_WARN_MS = 150.0


def get_vicon_segs():
    try:
        import vicon_dssdk.ViconDataStream as VDS
    except ImportError:
        print("[ERROR] 无法导入Vicon SDK，请确保已在正确环境中运行")
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
        temp_client.SetStreamMode(0)
    except Exception:
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
    try:
        import vicon_dssdk.ViconDataStream as VDS
    except ImportError:
        print("[ERROR] 无法导入Vicon SDK，请确保已在正确环境中运行")
        return []

    temp_client = VDS.Client()
    temp_client.Connect(VICON_HOST_IP)
    temp_client.EnableMarkerData()
    try:
        temp_client.SetStreamMode(0)
    except Exception:
        pass

    markers = []
    for _ in range(10):
        if temp_client.GetFrame():
            subjects = temp_client.GetSubjectNames()
            if subjects:
                s_name = subjects[0]
                raw_markers = temp_client.GetMarkerNames(s_name)
                temp_markers = []
                raw_list = raw_markers[1] if isinstance(raw_markers, tuple) and len(raw_markers) == 2 else raw_markers
                for m in raw_list:
                    temp_markers.append(m[0] if isinstance(m, (tuple, list)) else m)
                markers = temp_markers
                if markers:
                    break
        time.sleep(0.1)

    temp_client.Disconnect()
    print(f"[INFO] 获取到Markers: {markers}")
    return markers


print("[INFO] 正在初始化Vicon配置...")
VICON_SEGS = get_vicon_segs()
VICON_MARKERS = get_vicon_markers()


def generate_synced_headers():
    headers = [
        'Timestamp',
        'Vicon_Frame_Num',
        'Vicon_Recv_Timestamp',
        'IMU_Recv_Timestamp',
        'Planter_Recv_Timestamp',
        'Vicon_Gap_Flag',
        'Vicon_Gap_Size',
        'IMU_Stale_ms',
        'Planter_Stale_ms',
        'IMU_Matched_Flag',
        'Planter_Matched_Flag'
    ]

    for seg in VICON_SEGS:
        headers.extend([f'Vicon_{seg}_X', f'Vicon_{seg}_Y', f'Vicon_{seg}_Z'])

    for marker in VICON_MARKERS:
        headers.extend([f'Vicon_{marker}_X', f'Vicon_{marker}_Y', f'Vicon_{marker}_Z'])

    for name in IMU_NAMES:
        headers.extend([
            f'IMU_{name}_Acc_X', f'IMU_{name}_Acc_Y', f'IMU_{name}_Acc_Z',
            f'IMU_{name}_Gyro_X', f'IMU_{name}_Gyro_Y', f'IMU_{name}_Gyro_Z',
            f'IMU_{name}_Roll', f'IMU_{name}_Pitch', f'IMU_{name}_Yaw',
            f'IMU_{name}_Quat_x', f'IMU_{name}_Quat_y', f'IMU_{name}_Quat_z', f'IMU_{name}_Quat_w'
        ])

    for side in ['Left', 'Right']:
        for i in range(PLANTER_SENSOR_POINTS):
            headers.append(f'Planter_{side}_{i}')

    return headers


def generate_imu_raw_headers():
    headers = ['Recv_Timestamp', 'Device_Name']
    headers.extend([
        'Acc_X', 'Acc_Y', 'Acc_Z',
        'Gyro_X', 'Gyro_Y', 'Gyro_Z',
        'Roll', 'Pitch', 'Yaw',
        'Quat_x', 'Quat_y', 'Quat_z', 'Quat_w'
    ])
    return headers


def generate_planter_raw_headers():
    headers = ['Recv_Timestamp', 'Side']
    for i in range(PLANTER_SENSOR_POINTS):
        headers.append(f'Point_{i}')
    return headers
