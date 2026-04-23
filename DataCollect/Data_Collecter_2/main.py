# -*- coding: utf-8 -*-
"""
数据采集系统主入口
功能：启动Vicon/IMU/Planter三个接收线程，提供GUI控制界面
"""
import sys
import os

# 添加项目根目录到路径
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import socket
import time
import tkinter as tk
from tkinter import messagebox
from threading import Thread

# 导入配置和模块
from DataCollect.Data_Collecter_2 import config
from DataCollect.Data_Collecter_2.core.worker_vicon import ViconWorker
from DataCollect.Data_Collecter_2.core.worker_imu import IMUWorker
from DataCollect.Data_Collecter_2.core.worker_planter import PlanterWorker
from DataCollect.Data_Collecter_2.core.sync_master import SyncMaster
from DataCollect.Data_Collecter_2.utils.data_writer import CSVWriter


class MainApp:
    """
    主应用程序
    
    工作流程：
    1. 初始化时启动三个数据接收线程（Vicon/IMU/Planter）
    2. 用户点击"开始记录"按钮后：
       - 创建CSVWriter
       - 发送UDP指令让Vicon开始录制
       - 启动SyncMaster进行帧号驱动采集
    3. 用户点击"停止记录"按钮后：
       - 停止SyncMaster
       - 发送UDP指令让Vicon停止录制
    4. 窗口关闭时：停止所有线程
    """

    def __init__(self):
        # ========== 1. 初始化组件 ==========
        print("[MainApp] 初始化组件...")
        
        # 创建三个数据接收线程（尚未启动）
        self.vicon_worker = None
        self.imu_worker = None
        self.planter_worker = None
        
        # 同步采集器
        self.sync_master = None
        
        # CSV写入器
        self.csv_writer = None
        
        # 记录状态
        self.is_recording = False
        
        # ========== 2. 启动数据接收线程 ==========
        self._start_workers()
        
        # ========== 3. 创建GUI ==========
        self._create_gui()
        
        print("[MainApp] 初始化完成")

    def _start_workers(self):
        """
        启动三个数据接收线程
        """
        print("[MainApp] 启动数据接收线程...")
        
        # Vicon线程
        self.vicon_worker = ViconWorker(
            config.VICON_HOST_IP,
            config.VICON_SEGS,
            config.VICON_MARKERS
        )
        self.vicon_worker.start()
        
        # IMU线程
        self.imu_worker = IMUWorker(
            config.IMU_PORT,
            config.IMU_BAUDRATE,
            config.IMU_TIMEOUT
        )
        self.imu_worker.start()
        
        # Planter线程
        self.planter_worker = PlanterWorker(
            config.PLANTER_PORT,
            config.PLANTER_BAUD_RATE,
            config.PLANTER_TIMEOUT
        )
        self.planter_worker.start()
        
        # 等待连接确认
        time.sleep(1)
        
        # 检查连接状态
        print(f"[MainApp] Vicon连接: {self.vicon_worker.is_connected()}")
        print(f"[MainApp] IMU连接: {self.imu_worker.is_connected()}")
        print(f"[MainApp] Planter连接: {self.planter_worker.is_connected()}")

    def _create_gui(self):
        """
        创建GUI界面
        """
        self.root = tk.Tk()
        self.root.title("Vicon+IMU+Planter 数据采集系统")
        self.root.geometry("400x200")
        self.root.resizable(False, False)
        
        # 状态显示
        self.status_label = tk.Label(
            self.root,
            text="状态: 待机中",
            font=("Arial", 14),
            fg="blue"
        )
        self.status_label.pack(pady=20)
        
        # 统计显示
        self.stats_label = tk.Label(
            self.root,
            text="帧数: 0 | 重复: 0",
            font=("Arial", 10)
        )
        self.stats_label.pack(pady=5)
        
        # 控制按钮
        btn_frame = tk.Frame(self.root)
        btn_frame.pack(pady=20)
        
        self.btn_start = tk.Button(
            btn_frame,
            text="开始采集",
            command=self.start_record,
            bg="green",
            fg="white",
            font=("Arial", 12, "bold"),
            width=10,
            height=2
        )
        self.btn_start.pack(side=tk.LEFT, padx=10)
        
        self.btn_stop = tk.Button(
            btn_frame,
            text="停止采集",
            command=self.stop_record,
            bg="red",
            fg="white",
            font=("Arial", 12, "bold"),
            width=10,
            height=2,
            state=tk.DISABLED
        )
        self.btn_stop.pack(side=tk.LEFT, padx=10)
        
        # 窗口关闭事件
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def start_record(self):
        """
        开始记录数据
        """
        if self.is_recording:
            return
        
        self.is_recording = True
        
        # 更新按钮状态
        self.btn_start.config(state=tk.DISABLED)
        self.btn_stop.config(state=tk.NORMAL)
        self.status_label.config(text="状态: 正在采集...", fg="green")
        
        # 1. 创建CSVWriter
        self.csv_writer = CSVWriter()
        
        # 2. 发送Vicon录制指令
        self._send_vicon_command("start")
        
        # 3. 启动SyncMaster
        self.sync_master = SyncMaster(
            self.vicon_worker,
            self.imu_worker,
            self.planter_worker,
            self.csv_writer
        )
        self.sync_master.start()
        
        # 4. 启动统计更新线程
        self.stats_thread = Thread(target=self._update_stats)
        self.stats_thread.daemon = True
        self.stats_thread.start()
        
        print(f"[MainApp] 开始采集: {self.csv_writer.get_filename()}")

    def stop_record(self):
        """
        停止记录数据
        """
        if not self.is_recording:
            return
        
        self.is_recording = False
        
        # 1. 停止SyncMaster
        if self.sync_master:
            self.sync_master.stop()
        
        # 2. 发送Vicon停止指令
        self._send_vicon_command("stop")
        
        # 更新按钮状态
        self.btn_start.config(state=tk.NORMAL)
        self.btn_stop.config(state=tk.DISABLED)
        self.status_label.config(text="状态: 采集完成", fg="blue")
        
        # 显示统计
        if self.sync_master:
            stats = self.sync_master.get_statistics()
            print(f"[MainApp] 采集统计: {stats}")
        
        messagebox.showinfo("采集完成", f"数据已保存:\n{self.csv_writer.get_filename()}")

    def _send_vicon_command(self, cmd_type):
        """
        发送Vicon录制指令
        
        Args:
            cmd_type: "start" 或 "stop"
        """
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            vicon_ip = config.VICON_HOST_IP.split(':')[0]
            
            if cmd_type == "start":
                # 开启录制
                filename = os.path.basename(self.csv_writer.get_filename())
                xml = f'<CaptureStart><Name VALUE="{filename}"/></CaptureStart>\0'
            else:
                # 停止录制
                xml = '<CaptureStop></CaptureStop>\0'
            
            sock.sendto(xml.encode('utf-8'), (vicon_ip, 30))
            print(f"[MainApp] 已发送Vicon {cmd_type}指令")
            sock.close()
            
        except Exception as e:
            print(f"[MainApp] Vicon指令发送失败: {e}")

    def _update_stats(self):
        """
        更新统计显示
        """
        while self.is_recording and self.sync_master:
            stats = self.sync_master.get_statistics()
            self.stats_label.config(
                text=f"帧数: {stats['frame_count']} | 重复: {stats['dup_count']}"
            )
            time.sleep(0.5)

    def on_close(self):
        """
        窗口关闭事件
        """
        # 停止记录
        if self.is_recording:
            self.stop_record()
        
        print("[MainApp] 正在关闭...")
        
        # 停止所有线程
        if self.vicon_worker:
            self.vicon_worker.stop()
        if self.imu_worker:
            self.imu_worker.stop()
        if self.planter_worker:
            self.planter_worker.stop()
        
        # 等待线程结束
        time.sleep(0.5)
        
        self.root.destroy()
        print("[MainApp] 系统已退出")


# ==================== 主程序入口 ====================
if __name__ == '__main__':
    print("=" * 50)
    print("Vicon+IMU+Planter 数据采集系统")
    print("=" * 50)
    
    try:
        app = MainApp()
        app.root.mainloop()
    except Exception as e:
        print(f"[FATAL] 程序异常: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)