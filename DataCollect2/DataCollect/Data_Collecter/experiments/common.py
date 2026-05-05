# -*- coding: utf-8 -*-
"""
Vicon 实验公共工具
用于四组实验共享：
- 连接 Vicon
- 获取 subject / seg / marker
- 统一写 CSV
- 统一统计
- 统一采集诊断信息
"""
import csv
import os
import sys
import time
from collections import Counter
from datetime import datetime

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

import config
import vicon_dssdk.ViconDataStream as VDS

EXPERIMENT_DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
os.makedirs(EXPERIMENT_DATA_DIR, exist_ok=True)


def connect_vicon(host_ip=None, enable_segment=True, enable_marker=True):
    host_ip = host_ip or config.VICON_HOST_IP
    client = VDS.Client()
    print(f"[Experiment] 正在连接 Vicon: {host_ip}")
    client.Connect(host_ip)
    if not client.IsConnected():
        raise RuntimeError("Vicon 连接失败")

    if enable_segment:
        client.EnableSegmentData()
    if enable_marker:
        client.EnableMarkerData()

    try:
        client.SetStreamMode(0)
    except Exception as e:
        print(f"[Experiment] SetStreamMode(0) 失败或不支持: {e}")

    return client


def safe_call(callable_obj, default=None):
    try:
        return callable_obj()
    except Exception:
        return default


def collect_runtime_diagnostics(client, subject_name=None):
    diagnostics = {
        "client_connected": safe_call(lambda: bool(client.IsConnected()), False),
        "frame_rate": safe_call(lambda: client.GetFrameRate(), None),
        "subject_name": subject_name,
        "subject_count": None,
        "segment_count": None,
        "marker_count": None,
        "sdk_result_notes": [],
    }

    subjects = safe_call(lambda: client.GetSubjectNames(), None)
    if subjects is not None:
        diagnostics["subject_count"] = len(subjects)
        if subject_name is None and subjects:
            diagnostics["subject_name"] = subjects[0]

    target_subject = diagnostics["subject_name"]
    if target_subject:
        segs = safe_call(lambda: client.GetSegmentNames(target_subject), None)
        markers = safe_call(lambda: client.GetMarkerNames(target_subject), None)

        if segs is not None:
            diagnostics["segment_count"] = len(segs)
        if markers is not None:
            if isinstance(markers, tuple) and len(markers) == 2:
                raw_markers = markers[1]
            else:
                raw_markers = markers
            diagnostics["marker_count"] = len(raw_markers)

    return diagnostics


def print_runtime_diagnostics(diagnostics, experiment_name):
    print("\n" + "-" * 60)
    print(f"诊断信息: {experiment_name}")
    print("-" * 60)
    for key, value in diagnostics.items():
        print(f"{key}: {value}")
    print("-" * 60 + "\n")


def get_first_subject_name(client):
    for _ in range(20):
        if client.GetFrame():
            subjects = client.GetSubjectNames()
            if subjects:
                return subjects[0]
        time.sleep(0.05)
    raise RuntimeError("未获取到 Subject")


def make_experiment_filename(experiment_name):
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return os.path.join(EXPERIMENT_DATA_DIR, f"{experiment_name}_{ts}.csv")


def write_rows(filename, headers, rows):
    with open(filename, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerows(rows)


def summarize_frame_quality(rows):
    if not rows:
        return {
            "rows": 0,
            "first_frame": None,
            "last_frame": None,
            "frame_span": 0,
            "gap_rows": 0,
            "gap_sum": 0,
            "diff_counter": {},
            "avg_recv_dt": None,
            "min_recv_dt": None,
            "max_recv_dt": None,
            "effective_hz": None,
        }

    frames = [int(r[0]) for r in rows]
    recv_ts = [float(r[1]) for r in rows]
    diffs = [b - a for a, b in zip(frames, frames[1:])]
    recv_diffs = [b - a for a, b in zip(recv_ts, recv_ts[1:])]

    gap_rows = sum(1 for d in diffs if d != 1)
    gap_sum = sum(max(0, d - 1) for d in diffs)
    avg_recv_dt = sum(recv_diffs) / len(recv_diffs) if recv_diffs else None

    return {
        "rows": len(rows),
        "first_frame": frames[0],
        "last_frame": frames[-1],
        "frame_span": frames[-1] - frames[0] + 1,
        "gap_rows": gap_rows,
        "gap_sum": gap_sum,
        "diff_counter": dict(Counter(diffs).most_common(20)),
        "avg_recv_dt": avg_recv_dt,
        "min_recv_dt": min(recv_diffs) if recv_diffs else None,
        "max_recv_dt": max(recv_diffs) if recv_diffs else None,
        "effective_hz": (1.0 / avg_recv_dt) if avg_recv_dt and avg_recv_dt > 0 else None,
    }


def print_summary(summary, experiment_name):
    print("\n" + "=" * 60)
    print(f"实验结果: {experiment_name}")
    print("=" * 60)
    for k, v in summary.items():
        print(f"{k}: {v}")
    print("=" * 60 + "\n")
