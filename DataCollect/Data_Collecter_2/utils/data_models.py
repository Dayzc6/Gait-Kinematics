# -*- coding: utf-8 -*-
"""
数据模型定义
用于线程间传递 Vicon / IMU / Planter / 同步记录对象
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any


@dataclass
class ViconFrame:
    frame_num: int
    recv_timestamp: float
    subject_name: str
    seg_data: Dict[str, Dict[str, float]]
    marker_data: Dict[str, Dict[str, float]]
    occluded_segs: Dict[str, bool]


@dataclass
class IMUPacket:
    recv_timestamp: float
    data: Dict[str, Dict[str, Dict[str, float]]]


@dataclass
class PlanterPacket:
    recv_timestamp: float
    left: List[int]
    right: List[int]


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
    vicon_seg_data: Dict[str, Dict[str, float]]
    vicon_marker_data: Dict[str, Dict[str, float]]
    imu_data: Dict[str, Dict[str, Dict[str, float]]]
    planter_data: Dict[str, List[int]]
