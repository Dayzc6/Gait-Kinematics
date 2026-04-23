# -*- coding: utf-8 -*-
"""
Vicon数据接收线程模块
功能：持续从Vicon SDK拉取最新帧数据，供主记录线程使用
特性：使用帧号驱动，避免丢帧和重复帧问题
"""
import sys
import os
import time
import threading
from threading import Thread, Lock

# 导入Vicon SDK
import vicon_dssdk.ViconDataStream as VDS

# 导入配置
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    from DataCollect.Data_Collecter_2 import config
except ImportError:
    import config


class ViconWorker(Thread):
    """
    Vicon接收线程
    
    工作原理：
    1. 以1ms间隔极速轮询Vicon SDK的GetFrame()
    2. 每次获取到新帧后立即更新共享数据（seg_data, marker_data, frame_number）
    3. 使用threading.Lock保护共享数据，确保一致性
    
    数据一致性保证：
    - 只有在成功获取到一帧完整数据后才更新锁内的数据
    - get_latest_frame()方法返回数据快照（深拷贝）
    
    丢帧/重复帧解决方案：
    - 接收线程只负责"拉取最新数据"，以最快速度更新共享变量
    - 记录逻辑由sync_master的帧号驱动方式处理
    """

    def __init__(self, host_ip, seg_ids, marker_ids):
        """
        初始化Vicon连接
        
        Args:
            host_ip: Vicon主机IP地址
            seg_ids: Segment名称列表
            marker_ids: Marker名称列表
        """
        super().__init__()
        self.daemon = True  # 设为守护线程，主程序结束时自动结束

        self.host_ip = host_ip
        self.seg_ids = seg_ids
        self.marker_ids = marker_ids

        # 共享数据容器
        self.seg_data = {seg: {"X": 0.0, "Y": 0.0, "Z": 0.0} for seg in self.seg_ids}
        self.marker_data = {marker: {"X": 0.0, "Y": 0.0, "Z": 0.0} for marker in self.marker_ids}
        self.current_frame_num = 0  # 当前帧号
        self.occluded_segs = {seg: False for seg in self.seg_ids}  # 遮挡标志

        # 线程控制
        self.data_lock = Lock()  # 保护共享数据的锁
        self.is_running = False
        self._connected = False

        # Vicon客户端
        self.client = None

    def connect(self):
        """
        连接Vicon并启用数据流
        """
        try:
            self.client = VDS.Client()
            print(f"[ViconWorker] 正在连接 {self.host_ip} ...")
            self.client.Connect(self.host_ip)

            if not self.client.IsConnected():
                print(f"[ViconWorker] 连接失败!")
                return False

            print(f"[ViconWorker] Vicon连接成功!")

            # 启用数据
            self.client.EnableSegmentData()
            self.client.EnableMarkerData()

            # 设置为Pull模式（客户端主动拉取）
            try:
                self.client.SetStreamMode(0)  # 0 = Pull模式
            except Exception as e:
                print(f"[ViconWorker] 设置Pull模式警告: {e}")

            self._connected = True
            return True

        except Exception as e:
            print(f"[ViconWorker] 连接异常: {e}")
            return False

    def get_latest_frame(self):
        """
        获取最新一帧数据的快照
        
        Returns:
            tuple: (frame_number, seg_data, marker_data, occluded_segs)
                - frame_number: int, Vicon帧号
                - seg_data: dict, Segment坐标 {name: {"X": float, "Y": float, "Z": float}}
                - marker_data: dict, Marker坐标
                - occluded_segs: dict, 各Segment遮挡标志
        """
        with self.data_lock:
            return (
                self.current_frame_num,
                self.seg_data.copy(),
                self.marker_data.copy(),
                self.occluded_segs.copy()
            )

    def is_connected(self):
        """检查连接状态"""
        return self._connected and self.client and self.client.IsConnected()

    def run(self):
        """
        主循环：持续获取Vicon帧数据
        以1ms间隔极速轮询，发现新帧立即更新共享数据
        """
        if not self.connect():
            print("[ViconWorker] 连接失败，线程退出")
            return

        self.is_running = True
        print("[ViconWorker] 接收线程启动")

        try:
            while self.is_running:
                # GetFrame()会阻塞直到新帧到达（或超时）
                if self.client.GetFrame():
                    # 获取帧号
                    frame_num = self.client.GetFrameNumber()
                    
                    # 获取Subject名称
                    subjects = self.client.GetSubjectNames()
                    if not subjects:
                        time.sleep(0.001)
                        continue
                    
                    subject_name = subjects[0]

                    # 临时数据容器
                    temp_seg_data = {}
                    temp_marker_data = {}
                    temp_occluded = {}

                    # 获取Segment数据
                    for seg in self.seg_ids:
                        try:
                            pos, occluded = self.client.GetSegmentGlobalTranslation(subject_name, seg)
                            temp_occluded[seg] = occluded
                            
                            if not occluded:
                                temp_seg_data[seg] = {
                                    "X": pos[0],
                                    "Y": pos[1],
                                    "Z": pos[2]
                                }
                            else:
                                # 如果当前帧被遮挡，保留上一帧数据
                                temp_seg_data[seg] = self.seg_data.get(seg, 
                                    {"X": 0.0, "Y": 0.0, "Z": 0.0})
                        except Exception as e:
                            print(f"[ViconWorker] 获取Segment {seg}失败: {e}")
                            temp_seg_data[seg] = {"X": 0.0, "Y": 0.0, "Z": 0.0}
                            temp_occluded[seg] = True

                    # 获取Marker数据
                    for marker in self.marker_ids:
                        try:
                            pos, occluded = self.client.GetMarkerGlobalTranslation(subject_name, marker)
                            
                            if not occluded:
                                temp_marker_data[marker] = {
                                    "X": pos[0],
                                    "Y": pos[1],
                                    "Z": pos[2]
                                }
                            else:
                                temp_marker_data[marker] = self.marker_data.get(marker,
                                    {"X": 0.0, "Y": 0.0, "Z": 0.0})
                        except Exception:
                            temp_marker_data[marker] = {"X": 0.0, "Y": 0.0, "Z": 0.0}

                    # 更新共享数据（加锁保护）
                    with self.data_lock:
                        self.current_frame_num = frame_num
                        self.seg_data.update(temp_seg_data)
                        self.marker_data.update(temp_marker_data)
                        self.occluded_segs.update(temp_occluded)

                # 极短休眠，避免CPU满载
                time.sleep(0.001)

        except Exception as e:
            print(f"[ViconWorker] 运行异常: {e}")
        finally:
            self.stop()

    def stop(self):
        """
        停止接收线程并断开连接
        """
        self.is_running = False
        if self.client:
            try:
                self.client.Disconnect()
            except:
                pass
        print("[ViconWorker] 线程已停止")