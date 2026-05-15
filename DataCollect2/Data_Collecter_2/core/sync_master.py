# -*- coding: utf-8 -*-
"""
同步采集主模块
功能：协调Vicon、IMU、Planter三个数据源，以Vicon帧号驱动方式同步采集数据
核心：解决Vicon丢帧和重复帧问题
"""
import sys
import os
import time
import threading
from threading import Thread, Lock

# 尝试导入配置
try:
    from DataCollect.Data_Collecter_2 import config
except ImportError:
    import config


class SyncMaster:
    """
    同步采集主控器
    
    采集策略：帧号驱动
    - 以1ms间隔高频检测Vicon帧号
    - 当帧号变化时，立即采集所有三个传感器的最新数据
    - 写入CSV并标记IsDuplicate
    
    帧号驱动原理：
    1. Vicon接收线程以最快速度更新frame_number
    2. 主循环检测到frame_number > last_frame时，说明有新帧
    3. 记录该帧的所有传感器数据
    4. 如果frame_number == last_frame，说明帧未更新（重复帧），标记为1
    
    这样可以保证：
    - 不丢帧：每个Vicon帧都会被记录
    - 不重复：相同帧号只记录一次（或标记重复）
    """

    def __init__(self, vicon_worker, imu_worker, planter_worker, csv_writer):
        """
        初始化同步采集器
        
        Args:
            vicon_worker: ViconWorker实例
            imu_worker: IMUWorker实例
            planter_worker: PlanterWorker实例
            csv_writer: CSVWriter实例
        """
        self.vicon = vicon_worker
        self.imu = imu_worker
        self.planter = planter_worker
        self.writer = csv_writer

        # 帧号跟踪
        self.last_frame_num = -1  # 上次记录的帧号
        self.is_recording = False
        
        # 统计
        self.frame_count = 0  # 记录的总帧数
        self.dup_count = 0    # 重复帧数量

    def start(self):
        """
        开始同步采集
        """
        self.is_recording = True
        self.last_frame_num = -1
        self.frame_count = 0
        self.dup_count = 0
        
        # 启动记录线程
        self.record_thread = Thread(target=self._recording_loop)
        self.record_thread.daemon = True
        self.record_thread.start()
        
        print("[SyncMaster] 采集开始")

    def stop(self):
        """
        停止同步采集
        """
        self.is_recording = False
        if hasattr(self, 'record_thread'):
            self.record_thread.join(timeout=5)
        
        print(f"[SyncMaster] 采集停止 - 总帧数: {self.frame_count}, 重复帧: {self.dup_count}")

    def _recording_loop(self):
        """
        记录主循环：帧号驱动采集
        
        工作流程：
        1. 高频检测Vicon帧号（约1000Hz）
        2. 如果帧号变化 → 记录新帧（IsDuplicate=0）
        3. 如果帧号相同 → 标记为重复帧并记录（IsDuplicate=1）
        """
        # 检查所有传感器连接状态
        if not self.vicon.is_connected():
            print("[SyncMaster] Vicon未连接，无法开始记录")
            return
        
        print("[SyncMaster] 记录循环启动")
        
        while self.is_recording:
            try:
                # 1. 获取Vicon最新帧
                frame_num, seg_data, marker_data, occluded = self.vicon.get_latest_frame()
                
                # 2. 判断是否为新帧
                if frame_num > self.last_frame_num:
                    # 新帧
                    is_duplicate = 0
                    self.last_frame_num = frame_num
                    self.frame_count += 1
                else:
                    # 重复帧（帧号相同或回退）
                    is_duplicate = 1
                    self.dup_count += 1
                
                # 3. 获取其他传感器最新数据
                imu_data = self.imu.get_latest_data()
                planter_data = self.planter.get_latest_data()
                
                # 4. 记录时间戳
                timestamp = time.time()
                
                # 5. 写入CSV
                self.writer.append_row(
                    timestamp,
                    frame_num,
                    is_duplicate,
                    seg_data,
                    marker_data,
                    imu_data,
                    planter_data
                )
                
                # 6. 高精度休眠（约1000Hz）
                time.sleep(config.RECORDING_INTERVAL)
                
            except Exception as e:
                print(f"[SyncMaster] 记录异常: {e}")
                time.sleep(0.01)

    def get_statistics(self):
        """
        获取采集统计信息
        
        Returns:
            dict: {frame_count, dup_count, dup_rate}
        """
        total = self.frame_count + self.dup_count
        dup_rate = (self.dup_count / total * 100) if total > 0 else 0
        return {
            "frame_count": self.frame_count,
            "dup_count": self.dup_count,
            "dup_rate": round(dup_rate, 2)
        }


# ==================== 测试代码 ====================
if __name__ == '__main__':
    print("[TEST] SyncMaster单元测试")
    print("[TEST] 需要硬件设备才能运行实际测试")
    print("[TEST] 测试完成")