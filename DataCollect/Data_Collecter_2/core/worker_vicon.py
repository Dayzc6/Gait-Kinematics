# -*- coding: utf-8 -*-
"""
Vicon 逐帧采集线程
核心改动：不再只保存 latest，而是将每个 Vicon 帧逐帧放入队列。
保留 Vicon SDK 的原始调用语法与逻辑。
"""
import time
import queue
from threading import Thread, Lock
import vicon_dssdk.ViconDataStream as VDS

import config
from utils.data_models import ViconFrame


class ViconWorker(Thread):
    def __init__(self, host_ip, seg_ids, marker_ids, frame_queue):
        super().__init__()
        self.daemon = True
        self.host_ip = host_ip
        self.seg_ids = seg_ids
        self.marker_ids = marker_ids
        self.frame_queue = frame_queue

        self.latest_frame = None
        self.data_lock = Lock()
        self.is_running = False
        self._connected = False
        self.client = None

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
                self.client.SetStreamMode(0)
            except Exception as e:
                print(f"[ViconWorker] 设置Pull模式警告: {e}")

            self._connected = True
            return True
        except Exception as e:
            print(f"[ViconWorker] 连接异常: {e}")
            return False

    def is_connected(self):
        return self._connected and self.client and self.client.IsConnected()

    def get_latest_frame(self):
        with self.data_lock:
            return self.latest_frame

    def run(self):
        if not self.connect():
            print("[ViconWorker] 连接失败，线程退出")
            return

        self.is_running = True
        print("[ViconWorker] 接收线程启动")

        try:
            while self.is_running:
                if self.client.GetFrame():
                    recv_timestamp = time.time()
                    frame_num = self.client.GetFrameNumber()
                    subjects = self.client.GetSubjectNames()
                    if not subjects:
                        continue

                    subject_name = subjects[0]
                    temp_seg_data = {}
                    temp_marker_data = {}
                    temp_occluded = {}

                    for seg in self.seg_ids:
                        try:
                            pos, occluded = self.client.GetSegmentGlobalTranslation(subject_name, seg)
                            temp_occluded[seg] = occluded
                            if not occluded:
                                temp_seg_data[seg] = {"X": pos[0], "Y": pos[1], "Z": pos[2]}
                            else:
                                previous = self.latest_frame.seg_data.get(seg, {"X": 0.0, "Y": 0.0, "Z": 0.0}) if self.latest_frame else {"X": 0.0, "Y": 0.0, "Z": 0.0}
                                temp_seg_data[seg] = previous
                        except Exception as e:
                            print(f"[ViconWorker] 获取Segment {seg}失败: {e}")
                            temp_seg_data[seg] = {"X": 0.0, "Y": 0.0, "Z": 0.0}
                            temp_occluded[seg] = True

                    for marker in self.marker_ids:
                        try:
                            pos, occluded = self.client.GetMarkerGlobalTranslation(subject_name, marker)
                            if not occluded:
                                temp_marker_data[marker] = {"X": pos[0], "Y": pos[1], "Z": pos[2]}
                            else:
                                previous = self.latest_frame.marker_data.get(marker, {"X": 0.0, "Y": 0.0, "Z": 0.0}) if self.latest_frame else {"X": 0.0, "Y": 0.0, "Z": 0.0}
                                temp_marker_data[marker] = previous
                        except Exception:
                            temp_marker_data[marker] = {"X": 0.0, "Y": 0.0, "Z": 0.0}

                    frame = ViconFrame(
                        frame_num=frame_num,
                        recv_timestamp=recv_timestamp,
                        subject_name=subject_name,
                        seg_data=temp_seg_data,
                        marker_data=temp_marker_data,
                        occluded_segs=temp_occluded
                    )

                    with self.data_lock:
                        self.latest_frame = frame

                    try:
                        self.frame_queue.put(frame, timeout=0.2)
                    except queue.Full:
                        print(f"[ViconWorker] 警告：Vicon队列已满，帧 {frame_num} 未能及时入队")

        except Exception as e:
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
