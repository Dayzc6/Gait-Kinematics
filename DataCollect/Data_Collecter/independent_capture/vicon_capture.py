# -*- coding: utf-8 -*-
"""
独立 Vicon 实时采集模块
- 每成功获取一帧，就立即写入一行 vicon.csv
- 不进行跨模态同步，不做补写逻辑
"""
import copy
import os
import sys
import time
from threading import Event, Thread

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(CURRENT_DIR)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
try:
    import vicon_dssdk.ViconDataStream as VDS
except ImportError:
    VDS = None

try:

    from DataCollect.Data_Collecter.independent_capture import local_config as config
    from DataCollect.Data_Collecter.independent_capture.common import now_mono, now_wall
    from DataCollect.Data_Collecter.independent_capture.schema import generate_vicon_headers
except ImportError:
    from independent_capture import local_config as config
    from independent_capture.common import now_mono, now_wall
    from independent_capture.schema import generate_vicon_headers


class ViconCaptureWorker(Thread):
    def __init__(self, session_id, trial_id, subject_id, csv_writer=None, host_ip=None):
        super().__init__(daemon=True)
        self.session_id = session_id
        self.trial_id = trial_id
        self.subject_id = subject_id
        self.csv_writer = csv_writer
        self.host_ip = host_ip or config.VICON_HOST_IP
        self.client = None
        self.stop_event = Event()
        self.subject_name = None
        self.seg_ids = []
        self.marker_ids = []
        self.last_frame_num = None
        self.stats = {
            'captured_rows': 0,
            'frame_gaps': 0,
            'subject_found': 0,
            'marker_nonzero_frames': 0,
        }

    def stop(self):
        self.stop_event.set()

    def get_stats(self):
        return {
            **self.stats,
            'subject_name': self.subject_name,
            'segment_count': len(self.seg_ids),
            'marker_count': len(self.marker_ids),
        }

    def _connect(self):
        if VDS is None:
            raise RuntimeError('vicon_dssdk is not installed in current environment')
        self.client = VDS.Client()
        print(f'[ViconCapture] connect {self.host_ip}')
        self.client.Connect(self.host_ip)
        if not self.client.IsConnected():
            raise RuntimeError('Vicon connection failed')
        if config.VICON_ENABLE_SEGMENTS:
            self.client.EnableSegmentData()
        self.client.EnableMarkerData()
        try:
            self.client.SetStreamMode(config.VICON_STREAM_MODE)
        except Exception as e:
            print(f'[ViconCapture] SetStreamMode warning: {e}')

    def _discover_subject_and_layout(self):
        for _ in range(40):
            if self.client.GetFrame():
                subjects = self.client.GetSubjectNames()
                if subjects:
                    self.subject_name = subjects[0]
                    self.stats['subject_found'] = 1
                    if config.VICON_ENABLE_SEGMENTS:
                        try:
                            self.seg_ids = list(self.client.GetSegmentNames(self.subject_name))
                        except Exception:
                            self.seg_ids = []
                    try:
                        raw_markers = self.client.GetMarkerNames(self.subject_name)
                        if isinstance(raw_markers, tuple) and len(raw_markers) == 2:
                            raw_list = raw_markers[1]
                        else:
                            raw_list = raw_markers
                        self.marker_ids = [m[0] if isinstance(m, (tuple, list)) else m for m in raw_list]
                    except Exception:
                        self.marker_ids = []
                    return
            time.sleep(0.05)
        raise RuntimeError('No Vicon subject discovered')

    def get_headers(self):
        return generate_vicon_headers(self.seg_ids, self.marker_ids)

    def run(self):
        try:
            self._connect()
            self._discover_subject_and_layout()
            print(f'[ViconCapture] subject={self.subject_name}, segs={len(self.seg_ids)}, markers={len(self.marker_ids)}')
        except Exception as e:
            print(f'[ViconCapture] startup failed: {e}')
            return

        try:
            while not self.stop_event.is_set():
                if not self.client.GetFrame():
                    time.sleep(0.001)
                    continue

                recv_wall = now_wall()
                recv_mono = now_mono()
                frame_num = self.client.GetFrameNumber()

                gap_flag = 0
                gap_size = 0
                if self.last_frame_num is not None and frame_num != self.last_frame_num + 1:
                    gap_flag = 1
                    gap_size = max(0, frame_num - self.last_frame_num - 1)
                    self.stats['frame_gaps'] += 1
                self.last_frame_num = frame_num

                seg_data = {}
                seg_occluded = {}
                if config.VICON_ENABLE_SEGMENTS:
                    for seg in self.seg_ids:
                        try:
                            pos, occluded = self.client.GetSegmentGlobalTranslation(self.subject_name, seg)
                            seg_occluded[seg] = 1 if occluded else 0
                            if not occluded:
                                seg_data[seg] = {'X': pos[0], 'Y': pos[1], 'Z': pos[2]}
                            else:
                                seg_data[seg] = {'X': 0.0, 'Y': 0.0, 'Z': 0.0}
                        except Exception:
                            seg_occluded[seg] = 1
                            seg_data[seg] = {'X': 0.0, 'Y': 0.0, 'Z': 0.0}

                marker_data = {}
                marker_nonzero = False
                for marker in self.marker_ids:
                    try:
                        pos, occluded = self.client.GetMarkerGlobalTranslation(self.subject_name, marker)
                        if not occluded:
                            marker_data[marker] = {'X': pos[0], 'Y': pos[1], 'Z': pos[2]}
                            if pos[0] != 0.0 or pos[1] != 0.0 or pos[2] != 0.0:
                                marker_nonzero = True
                        else:
                            marker_data[marker] = {'X': 0.0, 'Y': 0.0, 'Z': 0.0}
                    except Exception:
                        marker_data[marker] = {'X': 0.0, 'Y': 0.0, 'Z': 0.0}

                if marker_nonzero:
                    self.stats['marker_nonzero_frames'] += 1

                original_valid = 1 if marker_nonzero or any(any(v != 0.0 for v in coords.values()) for coords in seg_data.values()) else 0

                row = [
                    self.session_id,
                    self.trial_id,
                    self.subject_id,
                    recv_wall,
                    recv_wall,
                    recv_mono,
                    frame_num,
                    self.subject_name,
                    gap_flag,
                    gap_size,
                    original_valid,
                ]

                for seg in self.seg_ids:
                    coords = seg_data.get(seg, {'X': 0.0, 'Y': 0.0, 'Z': 0.0})
                    row.extend([
                        seg_occluded.get(seg, 1),
                        coords['X'],
                        coords['Y'],
                        coords['Z'],
                    ])

                for marker in self.marker_ids:
                    coords = marker_data.get(marker, {'X': 0.0, 'Y': 0.0, 'Z': 0.0})
                    row.extend([coords['X'], coords['Y'], coords['Z']])

                if self.csv_writer is not None:
                    self.csv_writer.write_row(row)
                self.stats['captured_rows'] += 1
        except Exception as e:
            print(f'[ViconCapture] runtime error: {e}')
        finally:
            if self.client is not None:
                try:
                    self.client.Disconnect()
                except Exception:
                    pass
            if self.csv_writer is not None:
                self.csv_writer.flush()
            print('[ViconCapture] stopped')
