# -*- coding: utf-8 -*-
"""
同步引擎
- 逐帧消费 Vicon 队列
- 以 Vicon 为主时基
- 从 IMU / Planter buffer 中匹配最近且不晚于 Vicon 时间的包
- 将同步结果送入写队列
"""
import queue
import time
from threading import Thread

import config
from utils.data_models import SyncedRecord


class SyncEngine(Thread):
    def __init__(self, vicon_queue, imu_worker, planter_worker, write_queue):
        super().__init__()
        self.daemon = True
        self.vicon_queue = vicon_queue
        self.imu_worker = imu_worker
        self.planter_worker = planter_worker
        self.write_queue = write_queue
        self.is_running = False
        self.last_frame_num = None
        self.synced_count = 0
        self.gap_count = 0

    def stop(self):
        self.is_running = False

    def get_statistics(self):
        return {
            "frame_count": self.synced_count,
            "gap_count": self.gap_count,
        }

    @staticmethod
    def _find_best_packet(buffer_snapshot, target_ts):
        if not buffer_snapshot:
            return None

        candidates = [pkt for pkt in buffer_snapshot if pkt.recv_timestamp <= target_ts]
        if candidates:
            return max(candidates, key=lambda x: x.recv_timestamp)
        return min(buffer_snapshot, key=lambda x: abs(x.recv_timestamp - target_ts))

    def run(self):
        self.is_running = True
        print("[SyncEngine] 同步线程启动")
        while self.is_running:
            try:
                vicon_frame = self.vicon_queue.get(timeout=config.SYNC_QUEUE_TIMEOUT)
            except queue.Empty:
                continue
            except Exception as e:
                print(f"[SyncEngine] Vicon队列异常: {e}")
                continue

            try:
                current_ts = time.time()
                vicon_ts = vicon_frame.recv_timestamp

                gap_flag = 0
                gap_size = 0
                if self.last_frame_num is not None and vicon_frame.frame_num != self.last_frame_num + 1:
                    gap_flag = 1
                    gap_size = max(0, vicon_frame.frame_num - self.last_frame_num - 1)
                    self.gap_count += 1
                self.last_frame_num = vicon_frame.frame_num

                imu_packet = self._find_best_packet(self.imu_worker.get_buffer_snapshot(), vicon_ts)
                planter_packet = self._find_best_packet(self.planter_worker.get_buffer_snapshot(), vicon_ts)

                imu_recv_ts = imu_packet.recv_timestamp if imu_packet else None
                planter_recv_ts = planter_packet.recv_timestamp if planter_packet else None

                imu_stale_ms = (vicon_ts - imu_recv_ts) * 1000.0 if imu_recv_ts is not None else None
                planter_stale_ms = (vicon_ts - planter_recv_ts) * 1000.0 if planter_recv_ts is not None else None

                imu_data = imu_packet.data if imu_packet else self.imu_worker.get_latest_data()
                planter_data = {
                    "Left": planter_packet.left,
                    "Right": planter_packet.right
                } if planter_packet else self.planter_worker.get_latest_data()

                record = SyncedRecord(
                    timestamp=current_ts,
                    vicon_frame_num=vicon_frame.frame_num,
                    vicon_recv_timestamp=vicon_ts,
                    imu_recv_timestamp=imu_recv_ts,
                    planter_recv_timestamp=planter_recv_ts,
                    vicon_gap_flag=gap_flag,
                    vicon_gap_size=gap_size,
                    imu_stale_ms=imu_stale_ms,
                    planter_stale_ms=planter_stale_ms,
                    imu_matched_flag=1 if imu_packet else 0,
                    planter_matched_flag=1 if planter_packet else 0,
                    vicon_seg_data=vicon_frame.seg_data,
                    vicon_marker_data=vicon_frame.marker_data,
                    imu_data=imu_data,
                    planter_data=planter_data,
                )

                self.write_queue.put(record, timeout=0.2)
                self.synced_count += 1

            except Exception as e:
                print(f"[SyncEngine] 同步异常: {e}")

        print("[SyncEngine] 同步线程已停止")
