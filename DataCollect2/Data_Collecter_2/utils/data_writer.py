# -*- coding: utf-8 -*-
"""
CSV数据写入器模块
功能：将Vicon、IMU、Planter数据写入CSV文件
格式：按Whole_data_4格式输出
"""
import os
import csv
import time
from datetime import datetime

# 导入配置
try:
    from DataCollect.Data_Collecter_2 import config
except ImportError:
    import config


class CSVWriter:
    """
    CSV写入器
    
    CSV格式（按Whole_data_4结构）：
    1. Timestamp - 时间戳（秒）
    2. Vicon_Frame_Num - Vicon帧号
    3. IsDuplicate - 重复帧标记（0=新帧，1=重复帧）
    4. Vicon_Seg_XXX / Vicon_Marker_XXX - Vicon数据
    5. IMU数据 - Acc/Gyro/Euler/Quat
    6. Planter数据 - Left_0~17, Right_0~17
    
    使用方法：
    writer = CSVWriter()
    writer.append_row(timestamp, vicon_frame, is_dup, vicon_seg, vicon_marker, imu_data, planter_data)
    """

    def __init__(self, output_dir=None):
        """
        初始化CSV写入器
        
        Args:
            output_dir: 输出目录，默认使用config.DATA_DIR
        """
        # 设置输出目录
        if output_dir is None:
            self.output_dir = config.DATA_DIR
        else:
            self.output_dir = output_dir
        
        # 确保目录存在
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)
        
        # 生成文件名
        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.filename = os.path.join(self.output_dir, f"subject_trial_{timestamp_str}.csv")
        
        # 生成表头
        self.headers = config.generate_csv_headers()
        
        # 写入表头
        with open(self.filename, mode='w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(self.headers)
        
        print(f"[CSVWriter] CSV文件已创建: {self.filename}")
        print(f"[CSVWriter] 表头列数: {len(self.headers)}")

    def append_row(self, timestamp, vicon_frame, is_duplicate,
                 vicon_seg_data, vicon_marker_data,
                 imu_data, planter_data):
        """
        追加一行数据
        
        Args:
            timestamp: float, Unix时间戳
            vicon_frame: int, Vicon帧号
            is_duplicate: int, 0=新帧，1=重复帧
            vicon_seg_data: dict, {seg_name: {"X": float, "Y": float, "Z": float}}
            vicon_marker_data: dict, {marker_name: {"X": float, "Y": float, "Z": float}}
            imu_data: dict, {imu_name: {Acc/Gyro/Euler/Quat}}
            planter_data: dict, {"Left": [18个int], "Right": [18个int]}
        """
        row = []

        # 1. 基础列
        row.append(timestamp)
        row.append(vicon_frame)
        row.append(is_duplicate)

        # 2. Vicon Segment数据
        for seg in config.VICON_SEGS:
            coords = vicon_seg_data.get(seg, {"X": 0.0, "Y": 0.0, "Z": 0.0})
            row.extend([coords["X"], coords["Y"], coords["Z"]])

        # 3. Vicon Marker数据
        for marker in config.VICON_MARKERS:
            coords = vicon_marker_data.get(marker, {"X": 0.0, "Y": 0.0, "Z": 0.0})
            row.extend([coords["X"], coords["Y"], coords["Z"]])

        # 4. IMU数据
        for imu_name in config.IMU_NAMES:
            d = imu_data.get(imu_name, {
                "Acc": {"X": 0.0, "Y": 0.0, "Z": 0.0},
                "Gyro": {"X": 0.0, "Y": 0.0, "Z": 0.0},
                "Euler": {"Roll": 0.0, "Pitch": 0.0, "Yaw": 0.0},
                "Quat": {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0}
            })
            row.extend([
                d["Acc"]["X"], d["Acc"]["Y"], d["Acc"]["Z"],
                d["Gyro"]["X"], d["Gyro"]["Y"], d["Gyro"]["Z"],
                d["Euler"]["Roll"], d["Euler"]["Pitch"], d["Euler"]["Yaw"],
                d["Quat"]["x"], d["Quat"]["y"], d["Quat"]["z"], d["Quat"]["w"]
            ])

        # 5. Planter数据
        left_data = planter_data.get("Left", [0] * 18)
        right_data = planter_data.get("Right", [0] * 18)
        
        # 补齐到18个点
        if len(left_data) < 18:
            left_data = left_data + [0] * (18 - len(left_data))
        if len(right_data) < 18:
            right_data = right_data + [0] * (18 - len(right_data))
        
        row.extend(left_data[:18])
        row.extend(right_data[:18])

        # 写入文件
        with open(self.filename, mode='a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(row)

    def get_filename(self):
        """获取当前文件名"""
        return self.filename


# ==================== 测试代码 ====================
if __name__ == '__main__':
    print("[TEST] CSVWriter单元测试")
    
    # 创建写入器
    writer = CSVWriter()
    
    # 模拟数据
    import random
    timestamp = time.time()
    vicon_frame = 100
    is_dup = 0
    
    vicon_seg = {"Root": {"X": 100.0, "Y": 200.0, "Z": 300.0}}
    vicon_marker = {}
    
    imu_data = {
        "Trunk": {
            "Acc": {"X": 0.0, "Y": 0.0, "Z": 9.8},
            "Gyro": {"X": 0.0, "Y": 0.0, "Z": 0.0},
            "Euler": {"Roll": 0.0, "Pitch": 0.0, "Yaw": 0.0},
            "Quat": {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0}
        }
    }
    
    planter_data = {
        "Left": [random.randint(0, 1000) for _ in range(18)],
        "Right": [random.randint(0, 1000) for _ in range(18)]
    }
    
    # 写入测试
    writer.append_row(timestamp, vicon_frame, is_dup, vicon_seg, vicon_marker, imu_data, planter_data)
    
    print(f"[TEST] 写入完成: {writer.get_filename()}")
    print("[TEST] 测试完成")