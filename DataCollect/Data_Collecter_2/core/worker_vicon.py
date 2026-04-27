# -*- coding: utf-8 -*-
"""
Vicon 数据接收线程
目标：尽量贴近 experiments 中已验证成功的接收方式
- 每次 GetFrame 成功即视作一帧
- 逐帧封装为 ViconFrame 放入队列
- 同时保留最新快照供状态查看
"""
import copy
import os
import sys
import time
from queue import Full
from threading import Thread, Lock

import vicon_dssdk.ViconDataStream as VDS

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(CURRENT_DIR)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

try:
    from DataCollect.Data_Collecter_2 import config
    from DataCollect.Data_Collecter_2.utils.data_models import ViconFrame
except ImportError:
    import config
    from utils.data_models import ViconFrame


class ViconWorker(Thread):
    def __init__(self, host_ip, seg_ids, marker_ids, output_queue=None):
        super().__init__()
        self.daemon = True

        self.host_ip = host_ip
        self.seg_ids = list(seg_ids)
        self.marker_ids = list(marker_ids)
        self.output_queue = output_queue

        self.client = None
        self.is_running = False
        self._connected = False

        self.data_lock = Lock()
        self.current_frame_num = 0
        self.subject_name = None
        self.process_rate = None
        self.seg_data = {seg: {"X": 0.0, "Y": 0.0, "Z": 0.0} for seg in self.seg_ids}
        self.marker_data = {marker: {"X": 0.0, "Y": 0.0, "Z": 0.0} for marker in self.marker_ids}
        self.occluded_segs = {seg: False for seg in self.seg_ids}
        self.last_error = None

    def connect(self):
        try:
            self.client = VDS.Client()
            print(f"[ViconWorker] 正在连接 {self.host_ip} ...")
            self.client.Connect(self.host_ip)
            if not self.client.IsConnected():
                print("[ViconWorker] 连接失败!")
                return False

            print("[ViconWorker] Vicon连接成功!")
            self.client.EnableSegmentData()
            self.client.EnableMarkerData()

            try:
                self.client.SetStreamMode(config.VICON_STREAM_MODE)
            except Exception as e:
                print(f"[ViconWorker] 设置Pull模式警告: {e}")

            self._connected = True
            return True
        except Exception as e:
            self.last_error = e
            print(f"[ViconWorker] 连接异常: {e}")
            return False

    def is_connected(self):
        return self._connected and self.client is not None and self.client.IsConnected()

    def _get_subject_name(self):
        if self.subject_name:
            return self.subject_name
        subjects = self.client.GetSubjectNames()
        if subjects:
            self.subject_name = subjects[0]
        return self.subject_name

    def get_latest_frame(self):
        with self.data_lock:
            return {
                'frame_num': self.current_frame_num,
                'subject_name': self.subject_name,
                'process_rate': self.process_rate,
                'seg_data': copy.deepcopy(self.seg_data),
                'marker_data': copy.deepcopy(self.marker_data),
                'occluded_segs': copy.deepcopy(self.occluded_segs),
            }

    def _capture_one_frame(self):
        if not self.client.GetFrame():
            return None

        recv_ts = time.time()
        frame_num = self.client.GetFrameNumber()
        subject_name = self._get_subject_name()
        if not subject_name:
            return None

        try:
            self.process_rate = self.client.GetFrameRate()
        except Exception:
            pass

        temp_seg_data = {}
        temp_marker_data = {}
        temp_occluded = {}

        for seg in self.seg_ids:
            try:
                pos, occluded = self.client.GetSegmentGlobalTranslation(subject_name, seg)
                temp_occluded[seg] = bool(occluded)
                if not occluded:
                    temp_seg_data[seg] = {"X": pos[0], "Y": pos[1], "Z": pos[2]}
                else:
                    temp_seg_data[seg] = copy.deepcopy(self.seg_data.get(seg, {"X": 0.0, "Y": 0.0, "Z": 0.0}))
            except Exception:
                temp_occluded[seg] = True
                temp_seg_data[seg] = copy.deepcopy(self.seg_data.get(seg, {"X": 0.0, "Y": 0.0, "Z": 0.0}))

        for marker in self.marker_ids:
            try:
                pos, occluded = self.client.GetMarkerGlobalTranslation(subject_name, marker)
                if not occluded:
                    temp_marker_data[marker] = {"X": pos[0], "Y": pos[1], "Z": pos[2]}
                else:
                    temp_marker_data[marker] = copy.deepcopy(self.marker_data.get(marker, {"X": 0.0, "Y": 0.0, "Z": 0.0}))
            except Exception:
                temp_marker_data[marker] = copy.deepcopy(self.marker_data.get(marker, {"X": 0.0, "Y": 0.0, "Z": 0.0}))

        with self.data_lock:
            self.current_frame_num = frame_num
            self.seg_data.update(temp_seg_data)
            self.marker_data.update(temp_marker_data)
            self.occluded_segs.update(temp_occluded)

        return ViconFrame(
            frame_num=frame_num,
            recv_timestamp=recv_ts,
            subject_name=subject_name,
            seg_data=copy.deepcopy(temp_seg_data),
            marker_data=copy.deepcopy(temp_marker_data),
            occluded_segs=copy.deepcopy(temp_occluded),
        )

    def run(self):
        if not self.connect():
            print("[ViconWorker] 连接失败，线程退出")
            return

        self.is_running = True
        print("[ViconWorker] 接收线程启动")
        try:
            while self.is_running:
                frame = self._capture_one_frame()
                if frame is None:
                    continue

                if self.output_queue is not None:
                    try:
                        self.output_queue.put(frame, timeout=0.2)
                    except Full:
                        print("[ViconWorker] Vicon队列已满，丢弃当前帧")
        except Exception as e:
            self.last_error = e
            print(f"[ViconWorker] 运行异常: {e}")
        finally:
            self.stop()

    def stop(self):
        self.is_running = False
        if self.client:
            try:
                self.client.Disconnect()
            except Exception:
                pass
        print("[ViconWorker] 线程已停止")


if __name__ == '__main__':
    print("[TEST] ViconWorker单元测试")
    worker = ViconWorker(config.VICON_HOST_IP, config.VICON_SEGS, config.VICON_MARKERS)
    worker.start()
    time.sleep(2)
    print(worker.get_latest_frame())
    worker.stop()
    worker.join(timeout=2)
    print("[TEST] 测试完成")
