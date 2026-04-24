# -*- coding: utf-8 -*-
"""
主入口
采用方案2：
- Vicon 逐帧队列化
- IMU / Planter 带时间戳缓冲
- SyncEngine 逐帧同步
- WriterWorker 异步写盘
"""
import os
import sys
import socket
import time
import queue
import tkinter as tk
from tkinter import messagebox
from threading import Thread

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

import config
from core.worker_vicon import ViconWorker
from core.worker_imu import IMUWorker
from core.worker_planter import PlanterWorker
from core.sync_engine import SyncEngine
from core.writer_worker import WriterWorker


class MainApp:
    def __init__(self):
        print("[MainApp] 初始化组件...")
        self.vicon_queue = queue.Queue(maxsize=config.VICON_QUEUE_SIZE)
        self.write_queue = queue.Queue(maxsize=config.WRITE_QUEUE_SIZE)
        self.imu_raw_queue = queue.Queue(maxsize=config.WRITE_QUEUE_SIZE)
        self.planter_raw_queue = queue.Queue(maxsize=config.WRITE_QUEUE_SIZE)

        self.vicon_worker = None
        self.imu_worker = None
        self.planter_worker = None
        self.sync_engine = None
        self.writer_worker = None
        self.is_recording = False

        self._start_workers()
        self._create_gui()
        print("[MainApp] 初始化完成")

    def _start_workers(self):
        print("[MainApp] 启动数据接收线程...")

        self.vicon_worker = ViconWorker(
            config.VICON_HOST_IP,
            config.VICON_SEGS,
            config.VICON_MARKERS,
            self.vicon_queue
        )
        self.vicon_worker.start()

        self.imu_worker = IMUWorker(
            config.IMU_PORT,
            config.IMU_BAUDRATE,
            config.IMU_TIMEOUT,
            raw_queue=self.imu_raw_queue
        )
        self.imu_worker.start()

        self.planter_worker = PlanterWorker(
            config.PLANTER_PORT,
            config.PLANTER_BAUD_RATE,
            config.PLANTER_TIMEOUT,
            raw_queue=self.planter_raw_queue
        )
        self.planter_worker.start()

        time.sleep(1)
        print(f"[MainApp] Vicon连接: {self.vicon_worker.is_connected()}")
        print(f"[MainApp] IMU连接: {self.imu_worker.is_connected()}")
        print(f"[MainApp] Planter连接: {self.planter_worker.is_connected()}")

    def _create_gui(self):
        self.root = tk.Tk()
        self.root.title("Vicon+IMU+Planter 数据采集系统")
        self.root.geometry("480x220")
        self.root.resizable(False, False)

        self.status_label = tk.Label(self.root, text="状态: 待机中", font=("Arial", 14), fg="blue")
        self.status_label.pack(pady=20)

        self.stats_label = tk.Label(self.root, text="有效帧: 0 | Gap: 0", font=("Arial", 10))
        self.stats_label.pack(pady=5)

        btn_frame = tk.Frame(self.root)
        btn_frame.pack(pady=20)

        self.btn_start = tk.Button(btn_frame, text="开始采集", command=self.start_record, bg="green", fg="white", font=("Arial", 12, "bold"), width=10, height=2)
        self.btn_start.pack(side=tk.LEFT, padx=10)

        self.btn_stop = tk.Button(btn_frame, text="停止采集", command=self.stop_record, bg="red", fg="white", font=("Arial", 12, "bold"), width=10, height=2, state=tk.DISABLED)
        self.btn_stop.pack(side=tk.LEFT, padx=10)

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def start_record(self):
        if self.is_recording:
            return

        self.is_recording = True
        self.btn_start.config(state=tk.DISABLED)
        self.btn_stop.config(state=tk.NORMAL)
        self.status_label.config(text="状态: 正在采集...", fg="green")

        self.writer_worker = WriterWorker(self.write_queue, self.imu_raw_queue, self.planter_raw_queue)
        self.writer_worker.start()

        self._send_vicon_command("start")

        self.sync_engine = SyncEngine(
            self.vicon_queue,
            self.imu_worker,
            self.planter_worker,
            self.write_queue
        )
        self.sync_engine.start()

        self.stats_thread = Thread(target=self._update_stats, daemon=True)
        self.stats_thread.start()

        print(f"[MainApp] 开始采集: {self.writer_worker.get_main_filename()}")

    def stop_record(self):
        if not self.is_recording:
            return

        self.is_recording = False
        if self.sync_engine:
            self.sync_engine.stop()
            self.sync_engine.join(timeout=5)

        self._send_vicon_command("stop")

        if self.writer_worker:
            self.writer_worker.stop()
            self.writer_worker.join(timeout=10)

        self.btn_start.config(state=tk.NORMAL)
        self.btn_stop.config(state=tk.DISABLED)
        self.status_label.config(text="状态: 采集完成", fg="blue")

        if self.sync_engine:
            stats = self.sync_engine.get_statistics()
            print(f"[MainApp] 采集统计: {stats}")

        if self.writer_worker:
            messagebox.showinfo("采集完成", f"同步数据已保存:\n{self.writer_worker.get_main_filename()}")

    def _send_vicon_command(self, cmd_type):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            vicon_ip = config.VICON_HOST_IP.split(':')[0]
            if cmd_type == "start":
                filename = os.path.basename(self.writer_worker.get_main_filename()) if self.writer_worker else 'capture'
                xml = f'<CaptureStart><Name VALUE="{filename}"/></CaptureStart>\0'
            else:
                xml = '<CaptureStop></CaptureStop>\0'
            sock.sendto(xml.encode('utf-8'), (vicon_ip, 30))
            print(f"[MainApp] 已发送Vicon {cmd_type}指令")
            sock.close()
        except Exception as e:
            print(f"[MainApp] Vicon指令发送失败: {e}")

    def _update_stats(self):
        while self.is_recording and self.sync_engine:
            stats = self.sync_engine.get_statistics()
            self.stats_label.config(text=f"有效帧: {stats['frame_count']} | Gap: {stats['gap_count']}")
            time.sleep(0.5)

    def on_close(self):
        if self.is_recording:
            self.stop_record()

        print("[MainApp] 正在关闭...")
        if self.vicon_worker:
            self.vicon_worker.stop()
        if self.imu_worker:
            self.imu_worker.stop()
        if self.planter_worker:
            self.planter_worker.stop()

        time.sleep(0.5)
        self.root.destroy()
        print("[MainApp] 系统已退出")


if __name__ == '__main__':
    print("=" * 50)
    print("Vicon+IMU+Planter 数据采集系统")
    print("=" * 50)
    app = MainApp()
    app.root.mainloop()
