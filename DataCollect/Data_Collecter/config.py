# -*- coding: utf-8 -*-
"""
全局配置模块 - DataCollecter
面向正式采集新架构：
- ViconWorker 逐帧入队
- SyncEngine 逐帧消费
- WriterWorker 批量写盘
并保留 experiments 中已验证成功的 Vicon 接收方式所需配置。
"""
import os
import sys
import time

# 保证既支持模块方式启动，也支持直接脚本导入
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(CURRENT_DIR))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# ==================== 目录配置 ====================
MODULE_ROOT = CURRENT_DIR
DATA_DIR = os.path.join(MODULE_ROOT, "data")
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

# ==================== IMU 配置 ====================
IMU_PORT = 'COM9'
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
PLANTER_LEFT_PORT = 'COM10'
PLANTER_RIGHT_PORT = 'COM13'
PLANTER_BAUD_RATE = 115200
PLANTER_TIMEOUT = 2
PLANTER_SENSOR_POINTS = 18
PLANTER_FRAME_HEADER = 0xAA
PLANTER_FRAME_LENGTH_CANDIDATES = (39, 38)
PLANTER_BUFFER_MAXLEN = 512

# ==================== Vicon 配置 ====================
VICON_HOST_IP = "192.168.10.1"
VICON_STREAM_MODE = 0  # 与 experiments/common.py 中的 SetStreamMode(0) 保持一致
VICON_ENABLE_SEGMENTS = False  # 当前正式链路先关闭 segment 接收，保留代码结构以便后续恢复
VICON_RATE_PRINT_INTERVAL = 5.0  # 定期打印 frame rate / process rate（秒）

# ==================== IMU 严格快照配置（毫秒） ====================
# 只有当 7 个设备都已更新，且最早/最晚更新时间差不超过该窗口时，才生成一次完整 IMU snapshot。
# IMU 标称 30Hz（周期约 33.3ms），这里先保守设置为 20ms，尽量减少跨周期错配。
IMU_SNAPSHOT_WINDOW_MS = 20.0

# ==================== Planter 严格成对配置（毫秒） ====================
# 只有当左右脚最近更新时间差不超过该窗口时，才生成一次完整 Planter packet。
# Planter 标称 20Hz（周期约 50ms），这里先保守设置为 10ms，尽量保证左右脚接近同一采样时刻。
PLANTER_PAIR_WINDOW_MS = 10.0

# ==================== 队列/写盘配置 ====================
VICON_QUEUE_MAXSIZE = 4096
WRITE_QUEUE_MAXSIZE = 4096
SYNC_QUEUE_TIMEOUT = 0.2
WRITER_BATCH_SIZE = 128
WRITER_FLUSH_INTERVAL = 0.5

# ==================== 严格时间匹配阈值（毫秒） ====================
# 规则：只允许匹配 recv_timestamp <= vicon_timestamp 的历史包，且延迟不得超过以下阈值。
# 当前统一先按 20ms 保守设置，后续根据实际采样成功率与训练需求再微调。
IMU_MAX_LAG_MS = 20.0
PLANTER_MAX_LAG_MS = 20.0

# ==================== 有限补写 / 超时清零配置（毫秒） ====================
# 当当前 Vicon 帧没有新的 IMU / Planter / Vicon 数据可用时，
# 允许在以下时间窗口内重复写入上一帧有效值；超过窗口则清零。
IMU_HOLD_MAX_MS = 80.0
PLANTER_HOLD_MAX_MS = 120.0
VICON_HOLD_MAX_MS = 50.0

# Planter 连续若干个“真实接收到且全 0”的包后，判定为真实抬脚 0。
PLANTER_ZERO_CONFIRM_PACKETS = 2

# 兼容旧字段，尽量减少外部引用报错
RECORDING_INTERVAL = 0.001


# ==================== Vicon 动态获取函数 ====================
def get_vicon_segs():
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
        try:
            temp_client.Disconnect()
        except Exception:
            pass

    print(f"[INFO] 获取到Segments: {segs}")
    return segs


def get_vicon_markers():
    try:
        import vicon_dssdk.ViconDataStream as VDS
    except ImportError:
        print("[ERROR] 无法导入Vicon SDK")
        return []

    temp_client = VDS.Client()
    try:
        temp_client.Connect(VICON_HOST_IP)
        temp_client.EnableMarkerData()
        try:
            temp_client.SetStreamMode(VICON_STREAM_MODE)
        except Exception:
            pass

        markers = []
        for _ in range(10):
            if temp_client.GetFrame():
                subjects = temp_client.GetSubjectNames()
                if subjects:
                    s_name = subjects[0]
                    raw_markers = temp_client.GetMarkerNames(s_name)

                    if isinstance(raw_markers, tuple) and len(raw_markers) == 2:
                        raw_list = raw_markers[1]
                    else:
                        raw_list = raw_markers

                    temp_markers = []
                    for m in raw_list:
                        if isinstance(m, (tuple, list)):
                            temp_markers.append(m[0])
                        else:
                            temp_markers.append(m)

                    markers = temp_markers
                    if markers:
                        print(f"[INFO] 获取到Markers: {markers}")
                        return markers
            time.sleep(0.1)
    finally:
        try:
            temp_client.Disconnect()
        except Exception:
            pass

    print("[INFO] 获取到Markers: []")
    return []


print("[INFO] 正在初始化Vicon配置...")
VICON_SEGS = get_vicon_segs()
VICON_MARKERS = get_vicon_markers()


# ==================== CSV 表头生成 ====================
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
        'IMU_Matched_Count',
        'Planter_Matched_Count',
        'IMU_All_Matched_Flag',
        'Planter_Both_Matched_Flag',
        'Vicon_Original_Valid_Flag',
        'Vicon_Held_Flag',
        'Vicon_Timeout_Zero_Flag',
    ]

    for seg in VICON_SEGS:
        headers.extend([f'Vicon_{seg}_X', f'Vicon_{seg}_Y', f'Vicon_{seg}_Z'])

    for marker in VICON_MARKERS:
        headers.extend([f'Vicon_{marker}_X', f'Vicon_{marker}_Y', f'Vicon_{marker}_Z'])

    for name in IMU_NAMES:
        headers.extend([
            f'IMU_{name}_Matched_Flag',
            f'IMU_{name}_Held_Flag',
            f'IMU_{name}_Timeout_Zero_Flag',
            f'IMU_{name}_Recv_Timestamp',
            f'IMU_{name}_Stale_ms',
            f'IMU_{name}_Acc_X', f'IMU_{name}_Acc_Y', f'IMU_{name}_Acc_Z',
            f'IMU_{name}_Gyro_X', f'IMU_{name}_Gyro_Y', f'IMU_{name}_Gyro_Z',
            f'IMU_{name}_Roll', f'IMU_{name}_Pitch', f'IMU_{name}_Yaw',
            f'IMU_{name}_Quat_x', f'IMU_{name}_Quat_y', f'IMU_{name}_Quat_z', f'IMU_{name}_Quat_w'
        ])

    for side in ['Left', 'Right']:
        headers.extend([
            f'Planter_{side}_Matched_Flag',
            f'Planter_{side}_Held_Flag',
            f'Planter_{side}_Zero_Confirmed_Flag',
            f'Planter_{side}_Timeout_Zero_Flag',
            f'Planter_{side}_Recv_Timestamp',
            f'Planter_{side}_Stale_ms',
        ])
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
    """兼容旧接口。"""
    return generate_synced_headers()


if __name__ == '__main__':
    print("[INFO] 测试配置加载...")
    headers = generate_synced_headers()
    print(f"[INFO] CSV表头列数: {len(headers)}")
    print(f"[INFO] 前10列表头: {headers[:10]}")
    print("[INFO] 配置测试完成")
