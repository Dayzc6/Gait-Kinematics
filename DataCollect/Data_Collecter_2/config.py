# -*- coding: utf-8 -*-
"""
全局配置模块 - DataCollecter_2
包含 Vicon、IMU、Planter 的配置参数，以及新架构所需的 CSV 表头与队列配置。
"""
import os
import sys
import time

# 添加项目根目录到路径，以便导入Vicon SDK
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ==================== 目录配置 ====================
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

# ==================== IMU 配置 ====================
IMU_PORT = 'COM12'
IMU_BAUDRATE = 460800
IMU_TIMEOUT = 0.1
IMU_FRAME_HEAD = b'\x55'
IMU_FRAME_TOTAL_LEN = 29
IMU_BUFFER_MAXLEN = 512

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
PLANTER_BUFFER_MAXLEN = 512

# ==================== Vicon 配置 ====================
VICON_HOST_IP = "192.168.10.1"
VICON_STREAM_MODE = 0
VICON_BUFFERED_PULL_WAIT = 0.0

# ==================== 队列/写盘配置 ====================
VICON_QUEUE_MAXSIZE = 4096
WRITE_QUEUE_MAXSIZE = 4096
RAW_QUEUE_MAXSIZE = 4096
SYNC_QUEUE_TIMEOUT = 0.2
WRITER_BATCH_SIZE = 128
WRITER_FLUSH_INTERVAL = 0.5

# ==================== 匹配阈值配置 ====================
IMU_STALE_THRESHOLD_MS = 200.0
PLANTER_STALE_THRESHOLD_MS = 200.0

# ==================== 旧架构兼容配置 ====================
RECORDING_INTERVAL = 0.001


# ==================== Vicon动态获取函数 ====================
def get_vicon_segs():
    """连接 Vicon 并获取 Subject 的 Segment 列表。"""
    try:
        import vicon_dssdk.ViconDataStream as VDS
    except ImportError:
        print("[ERROR] 无法导入Vicon SDK，请确保已安装 vicon-dssdk")
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
        temp_client.SetStreamMode(VICON_STREAM_MODE)
    except Exception:
        pass

    segs = []
    try:
        for _ in range(10):
            if temp_client.GetFrame():
                subjects = temp_client.GetSubjectNames()
                if subjects:
                    s_name = subjects[0]
                    print(f"[INFO] Subject名称: {s_name}")
                    segs = temp_client.GetSegmentNames(s_name)
                    break
            time.sleep(0.1)
    finally:
        temp_client.Disconnect()

    print(f"[INFO] 获取到Segments: {segs}")
    return segs


def get_vicon_markers():
    """连接 Vicon 并获取 Subject 的 Marker 列表。"""
    try:
        import vicon_dssdk.ViconDataStream as VDS
    except ImportError:
        print("[ERROR] 无法导入Vicon SDK")
        return []

    temp_client = VDS.Client()
    temp_client.Connect(VICON_HOST_IP)
    temp_client.EnableMarkerData()

    try:
        temp_client.SetStreamMode(VICON_STREAM_MODE)
    except Exception:
        pass

    markers = []
    try:
        for _ in range(10):
            if temp_client.GetFrame():
                subjects = temp_client.GetSubjectNames()
                if subjects:
                    s_name = subjects[0]
                    raw_markers = temp_client.GetMarkerNames(s_name)
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
    finally:
        temp_client.Disconnect()

    print(f"[INFO] 获取到Markers: {markers}")
    return markers


print("[INFO] 正在初始化Vicon配置...")
VICON_SEGS = get_vicon_segs()
VICON_MARKERS = get_vicon_markers()


# ==================== CSV表头生成 ====================
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
        'Planter_Matched_Flag',
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
    return [
        'Recv_Timestamp', 'Device_Name',
        'Acc_X', 'Acc_Y', 'Acc_Z',
        'Gyro_X', 'Gyro_Y', 'Gyro_Z',
        'Roll', 'Pitch', 'Yaw',
        'Quat_x', 'Quat_y', 'Quat_z', 'Quat_w'
    ]


def generate_planter_raw_headers():
    headers = ['Recv_Timestamp', 'Side']
    for i in range(PLANTER_SENSOR_POINTS):
        headers.append(f'Point_{i}')
    return headers


def generate_csv_headers():
    """旧接口兼容：返回新 synced 文件表头。"""
    return generate_synced_headers()


if __name__ == '__main__':
    print("[INFO] 测试配置加载...")
    headers = generate_synced_headers()
    print(f"[INFO] CSV表头列数: {len(headers)}")
    print(f"[INFO] 前10列表头: {headers[:10]}")
    print("[INFO] 配置测试完成")
