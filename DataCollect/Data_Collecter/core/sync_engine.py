# -*- coding: utf-8 -*-
"""
同步引擎（带有限补写 / 超时清零）
- 逐帧消费 Vicon 队列
- 以 Vicon 为主时基
- IMU / Planter / Vicon 均支持有限时间内上一帧补写
- 超过阈值后清零
- Planter 支持“连续全 0 包”判定真实抬脚
"""
import copy
import os
import queue
import sys
import time
from threading import Thread

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(CURRENT_DIR)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

try:
    from DataCollect.Data_Collecter import config
    from DataCollect.Data_Collecter.utils.data_models import SyncedRecord
except ImportError:
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

        self.last_valid_imu_data = {name: self._default_imu_sample_data() for name in config.IMU_NAMES}
        self.last_valid_imu_ts = {name: None for name in config.IMU_NAMES}

        self.last_valid_planter_data = {
            'Left': self._default_planter_side_data(),
            'Right': self._default_planter_side_data(),
        }
        self.last_valid_planter_ts = {'Left': None, 'Right': None}
        self.planter_zero_confirm_count = {'Left': 0, 'Right': 0}
        self.planter_zero_confirmed = {'Left': False, 'Right': False}

        self.last_valid_vicon_seg_data = {}
        self.last_valid_vicon_marker_data = {}
        self.last_valid_vicon_ts = None

    def stop(self):
        self.is_running = False

    def get_statistics(self):
        return {
            'frame_count': self.synced_count,
            'gap_count': self.gap_count,
        }

    @staticmethod
    def _default_imu_sample_data():
        return {
            'Acc': {'X': 0.0, 'Y': 0.0, 'Z': 0.0},
            'Gyro': {'X': 0.0, 'Y': 0.0, 'Z': 0.0},
            'Euler': {'Roll': 0.0, 'Pitch': 0.0, 'Yaw': 0.0},
            'Quat': {'x': 0.0, 'y': 0.0, 'z': 0.0, 'w': 1.0},
        }

    @staticmethod
    def _default_planter_side_data():
        return [0] * config.PLANTER_SENSOR_POINTS

    @staticmethod
    def _is_all_zero(values):
        return all(v == 0 for v in values)

    @staticmethod
    def _find_best_sample(buffer_snapshot, target_ts, max_lag_ms):
        if not buffer_snapshot:
            return None

        candidates = [sample for sample in buffer_snapshot if sample.recv_timestamp <= target_ts]
        if not candidates:
            return None

        sample = max(candidates, key=lambda x: x.recv_timestamp)
        lag_ms = (target_ts - sample.recv_timestamp) * 1000.0
        if lag_ms < 0:
            return None
        if lag_ms > max_lag_ms:
            return None
        return sample

    def _resolve_vicon_output(self, vicon_frame):
        current_has_nonzero = False
        for coords in vicon_frame.seg_data.values():
            if any(value != 0.0 for value in coords.values()):
                current_has_nonzero = True
                break
        if not current_has_nonzero:
            for coords in vicon_frame.marker_data.values():
                if any(value != 0.0 for value in coords.values()):
                    current_has_nonzero = True
                    break

        vicon_original_valid_flag = 1 if current_has_nonzero else 0
        vicon_held_flag = 0
        vicon_timeout_zero_flag = 0

        if current_has_nonzero:
            self.last_valid_vicon_seg_data = copy.deepcopy(vicon_frame.seg_data)
            self.last_valid_vicon_marker_data = copy.deepcopy(vicon_frame.marker_data)
            self.last_valid_vicon_ts = vicon_frame.recv_timestamp
            return (
                copy.deepcopy(vicon_frame.seg_data),
                copy.deepcopy(vicon_frame.marker_data),
                vicon_original_valid_flag,
                vicon_held_flag,
                vicon_timeout_zero_flag,
            )

        if self.last_valid_vicon_ts is not None:
            lag_ms = (vicon_frame.recv_timestamp - self.last_valid_vicon_ts) * 1000.0
            if lag_ms <= config.VICON_HOLD_MAX_MS:
                vicon_held_flag = 1
                return (
                    copy.deepcopy(self.last_valid_vicon_seg_data),
                    copy.deepcopy(self.last_valid_vicon_marker_data),
                    vicon_original_valid_flag,
                    vicon_held_flag,
                    vicon_timeout_zero_flag,
                )

        vicon_timeout_zero_flag = 1
        return (
            copy.deepcopy(vicon_frame.seg_data),
            copy.deepcopy(vicon_frame.marker_data),
            vicon_original_valid_flag,
            vicon_held_flag,
            vicon_timeout_zero_flag,
        )

    def run(self):
        self.is_running = True
        print('[SyncEngine] 同步线程启动')
        while self.is_running:
            try:
                vicon_frame = self.vicon_queue.get(timeout=config.SYNC_QUEUE_TIMEOUT)
            except queue.Empty:
                continue
            except Exception as e:
                print(f'[SyncEngine] Vicon队列异常: {e}')
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

                vicon_seg_data, vicon_marker_data, vicon_original_valid_flag, vicon_held_flag, vicon_timeout_zero_flag = self._resolve_vicon_output(vicon_frame)

                imu_data = {}
                imu_device_recv_timestamps = {}
                imu_device_stale_ms = {}
                imu_device_matched_flags = {}
                imu_device_held_flags = {}
                imu_device_timeout_zero_flags = {}

                for imu_name in config.IMU_NAMES:
                    imu_sample = self._find_best_sample(
                        self.imu_worker.get_buffer_snapshot(imu_name),
                        vicon_ts,
                        config.IMU_MAX_LAG_MS,
                    )
                    if imu_sample:
                        imu_data[imu_name] = imu_sample.data
                        imu_device_recv_timestamps[imu_name] = imu_sample.recv_timestamp
                        stale_ms = (vicon_ts - imu_sample.recv_timestamp) * 1000.0
                        imu_device_stale_ms[imu_name] = stale_ms
                        imu_device_matched_flags[imu_name] = 1
                        imu_device_held_flags[imu_name] = 0
                        imu_device_timeout_zero_flags[imu_name] = 0
                        self.last_valid_imu_data[imu_name] = copy.deepcopy(imu_sample.data)
                        self.last_valid_imu_ts[imu_name] = imu_sample.recv_timestamp
                    else:
                        last_ts = self.last_valid_imu_ts[imu_name]
                        if last_ts is not None and (vicon_ts - last_ts) * 1000.0 <= config.IMU_HOLD_MAX_MS:
                            imu_data[imu_name] = copy.deepcopy(self.last_valid_imu_data[imu_name])
                            imu_device_recv_timestamps[imu_name] = last_ts
                            imu_device_stale_ms[imu_name] = (vicon_ts - last_ts) * 1000.0
                            imu_device_matched_flags[imu_name] = 0
                            imu_device_held_flags[imu_name] = 1
                            imu_device_timeout_zero_flags[imu_name] = 0
                        else:
                            imu_data[imu_name] = self._default_imu_sample_data()
                            imu_device_recv_timestamps[imu_name] = None
                            imu_device_stale_ms[imu_name] = None
                            imu_device_matched_flags[imu_name] = 0
                            imu_device_held_flags[imu_name] = 0
                            imu_device_timeout_zero_flags[imu_name] = 1

                planter_data = {}
                planter_side_recv_timestamps = {}
                planter_side_stale_ms = {}
                planter_side_matched_flags = {}
                planter_side_held_flags = {}
                planter_side_zero_confirmed_flags = {}
                planter_side_timeout_zero_flags = {}

                for side in ['Left', 'Right']:
                    planter_sample = self._find_best_sample(
                        self.planter_worker.get_buffer_snapshot(side),
                        vicon_ts,
                        config.PLANTER_MAX_LAG_MS,
                    )
                    if planter_sample:
                        is_zero_packet = self._is_all_zero(planter_sample.values)
                        if is_zero_packet:
                            self.planter_zero_confirm_count[side] += 1
                        else:
                            self.planter_zero_confirm_count[side] = 0
                            self.planter_zero_confirmed[side] = False
                            self.last_valid_planter_data[side] = copy.copy(planter_sample.values)
                            self.last_valid_planter_ts[side] = planter_sample.recv_timestamp

                        if self.planter_zero_confirm_count[side] >= config.PLANTER_ZERO_CONFIRM_PACKETS:
                            self.planter_zero_confirmed[side] = True

                        planter_data[side] = copy.copy(planter_sample.values)
                        planter_side_recv_timestamps[side] = planter_sample.recv_timestamp
                        stale_ms = (vicon_ts - planter_sample.recv_timestamp) * 1000.0
                        planter_side_stale_ms[side] = stale_ms
                        planter_side_matched_flags[side] = 1
                        planter_side_held_flags[side] = 0
                        planter_side_zero_confirmed_flags[side] = 1 if (is_zero_packet and self.planter_zero_confirmed[side]) else 0
                        planter_side_timeout_zero_flags[side] = 0
                    else:
                        if self.planter_zero_confirmed[side]:
                            planter_data[side] = self._default_planter_side_data()
                            planter_side_recv_timestamps[side] = None
                            planter_side_stale_ms[side] = None
                            planter_side_matched_flags[side] = 0
                            planter_side_held_flags[side] = 0
                            planter_side_zero_confirmed_flags[side] = 1
                            planter_side_timeout_zero_flags[side] = 0
                        else:
                            last_ts = self.last_valid_planter_ts[side]
                            if last_ts is not None and (vicon_ts - last_ts) * 1000.0 <= config.PLANTER_HOLD_MAX_MS:
                                planter_data[side] = copy.copy(self.last_valid_planter_data[side])
                                planter_side_recv_timestamps[side] = last_ts
                                planter_side_stale_ms[side] = (vicon_ts - last_ts) * 1000.0
                                planter_side_matched_flags[side] = 0
                                planter_side_held_flags[side] = 1
                                planter_side_zero_confirmed_flags[side] = 0
                                planter_side_timeout_zero_flags[side] = 0
                            else:
                                planter_data[side] = self._default_planter_side_data()
                                planter_side_recv_timestamps[side] = None
                                planter_side_stale_ms[side] = None
                                planter_side_matched_flags[side] = 0
                                planter_side_held_flags[side] = 0
                                planter_side_zero_confirmed_flags[side] = 0
                                planter_side_timeout_zero_flags[side] = 1

                imu_matched_count = sum(imu_device_matched_flags.values())
                planter_matched_count = sum(planter_side_matched_flags.values())
                imu_all_matched_flag = 1 if imu_matched_count == len(config.IMU_NAMES) else 0
                planter_both_matched_flag = 1 if planter_matched_count == 2 else 0

                valid_imu_recv_timestamps = [ts for ts in imu_device_recv_timestamps.values() if ts is not None]
                valid_planter_recv_timestamps = [ts for ts in planter_side_recv_timestamps.values() if ts is not None]
                valid_imu_stales = [stale for stale in imu_device_stale_ms.values() if stale is not None]
                valid_planter_stales = [stale for stale in planter_side_stale_ms.values() if stale is not None]

                imu_recv_ts = max(valid_imu_recv_timestamps) if valid_imu_recv_timestamps else None
                planter_recv_ts = max(valid_planter_recv_timestamps) if valid_planter_recv_timestamps else None
                imu_stale_ms = max(valid_imu_stales) if valid_imu_stales else None
                planter_stale_ms = max(valid_planter_stales) if valid_planter_stales else None

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
                    imu_matched_flag=1 if imu_matched_count > 0 else 0,
                    planter_matched_flag=1 if planter_matched_count > 0 else 0,
                    imu_matched_count=imu_matched_count,
                    planter_matched_count=planter_matched_count,
                    imu_all_matched_flag=imu_all_matched_flag,
                    planter_both_matched_flag=planter_both_matched_flag,
                    vicon_original_valid_flag=vicon_original_valid_flag,
                    vicon_held_flag=vicon_held_flag,
                    vicon_timeout_zero_flag=vicon_timeout_zero_flag,
                    vicon_seg_data=vicon_seg_data,
                    vicon_marker_data=vicon_marker_data,
                    imu_data=imu_data,
                    planter_data=planter_data,
                    imu_device_recv_timestamps=imu_device_recv_timestamps,
                    imu_device_stale_ms=imu_device_stale_ms,
                    imu_device_matched_flags=imu_device_matched_flags,
                    imu_device_held_flags=imu_device_held_flags,
                    imu_device_timeout_zero_flags=imu_device_timeout_zero_flags,
                    planter_side_recv_timestamps=planter_side_recv_timestamps,
                    planter_side_stale_ms=planter_side_stale_ms,
                    planter_side_matched_flags=planter_side_matched_flags,
                    planter_side_held_flags=planter_side_held_flags,
                    planter_side_zero_confirmed_flags=planter_side_zero_confirmed_flags,
                    planter_side_timeout_zero_flags=planter_side_timeout_zero_flags,
                )

                self.write_queue.put(record, timeout=0.2)
                self.synced_count += 1
            except Exception as e:
                print(f'[SyncEngine] 同步异常: {e}')

        print('[SyncEngine] 同步线程已停止')
