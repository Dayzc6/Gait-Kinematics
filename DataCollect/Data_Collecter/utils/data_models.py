# -*- coding: utf-8 -*-
"""
数据模型定义
用于线程间传递 Vicon / IMU / Planter / 同步记录对象
"""
from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass
class ViconFrame:
    frame_num: int
    recv_timestamp: float
    subject_name: str
    seg_data: Dict[str, Dict[str, float]]
    marker_data: Dict[str, Dict[str, float]]
    occluded_segs: Dict[str, bool]


@dataclass
class IMUSample:
    device_name: str
    recv_timestamp: float
    seq_index: int
    data: Dict[str, Dict[str, float]]


@dataclass
class PlanterSample:
    side: str
    recv_timestamp: float
    seq_index: int
    values: List[int]


@dataclass
class SyncedRecord:
    timestamp: float
    vicon_frame_num: int
    vicon_recv_timestamp: float
    imu_recv_timestamp: Optional[float]
    planter_recv_timestamp: Optional[float]
    vicon_gap_flag: int
    vicon_gap_size: int
    imu_stale_ms: Optional[float]
    planter_stale_ms: Optional[float]
    imu_matched_flag: int
    planter_matched_flag: int
    imu_matched_count: int
    planter_matched_count: int
    imu_all_matched_flag: int
    planter_both_matched_flag: int
    vicon_original_valid_flag: int
    vicon_held_flag: int
    vicon_timeout_zero_flag: int
    vicon_seg_data: Dict[str, Dict[str, float]]
    vicon_marker_data: Dict[str, Dict[str, float]]
    imu_data: Dict[str, Dict[str, Dict[str, float]]]
    planter_data: Dict[str, List[int]]
    imu_device_recv_timestamps: Dict[str, Optional[float]]
    imu_device_stale_ms: Dict[str, Optional[float]]
    imu_device_matched_flags: Dict[str, int]
    imu_device_held_flags: Dict[str, int]
    imu_device_timeout_zero_flags: Dict[str, int]
    planter_side_recv_timestamps: Dict[str, Optional[float]]
    planter_side_stale_ms: Dict[str, Optional[float]]
    planter_side_matched_flags: Dict[str, int]
    planter_side_held_flags: Dict[str, int]
    planter_side_zero_confirmed_flags: Dict[str, int]
    planter_side_timeout_zero_flags: Dict[str, int]
