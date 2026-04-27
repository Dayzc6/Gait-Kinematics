# -*- coding: utf-8 -*-
"""
数据采集系统正式主入口（新架构）
目标：尽量贴近 experiments 中已验证成功的 Vicon 接收效果
架构：
- ViconWorker：逐帧入队
- SyncEngine：逐帧消费并做 IMU/Planter 时间匹配
- WriterWorker：批量写盘
控制方式：命令行 start / stop / status / quit
"""
import os
import queue
import sys
import time

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(CURRENT_DIR))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

try:
    from DataCollect.Data_Collecter_2 import config
    from DataCollect.Data_Collecter_2.core.worker_vicon import ViconWorker
    from DataCollect.Data_Collecter_2.core.worker_imu import IMUWorker
    from DataCollect.Data_Collecter_2.core.worker_planter import PlanterWorker
    from DataCollect.Data_Collecter_2.core.sync_engine import SyncEngine
    from DataCollect.Data_Collecter_2.core.writer_worker import WriterWorker
except ImportError as e:
    print(f"[ERROR] 导入错误: {e}")
    print("[ERROR] 请确认当前工作目录在项目根目录下，或使用 -m 方式启动")
    sys.exit(1)


class AppController:
    def __init__(self):
        self.vicon_queue = queue.Queue(maxsize=config.VICON_QUEUE_MAXSIZE)
        self.write_queue = queue.Queue(maxsize=config.WRITE_QUEUE_MAXSIZE)
        self.imu_raw_queue = queue.Queue(maxsize=config.RAW_QUEUE_MAXSIZE)
        self.planter_raw_queue = queue.Queue(maxsize=config.RAW_QUEUE_MAXSIZE)

        self.vicon_worker = ViconWorker(
            config.VICON_HOST_IP,
            config.VICON_SEGS,
            config.VICON_MARKERS,
            output_queue=self.vicon_queue,
        )
        self.imu_worker = IMUWorker(
            config.IMU_PORT,
            config.IMU_BAUDRATE,
            config.IMU_TIMEOUT,
            raw_queue=self.imu_raw_queue,
        )
        self.planter_worker = PlanterWorker(
            config.PLANTER_LEFT_PORT,
            config.PLANTER_RIGHT_PORT,
            config.PLANTER_BAUD_RATE,
            config.PLANTER_TIMEOUT,
            raw_queue=self.planter_raw_queue,
        )

        self.sync_engine = None
        self.writer_worker = None
        self.is_recording = False

    def start_workers(self):
        print('[App] 启动采集线程...')
        self.vicon_worker.start()
        self.imu_worker.start()
        self.planter_worker.start()
        time.sleep(1.0)
        self.print_status()

    def start_recording(self):
        if self.is_recording:
            print('[App] 已在采集中')
            return
        if not self.vicon_worker.is_connected():
            print('[App] Vicon 未连接，无法开始记录')
            return

        self.writer_worker = WriterWorker(
            self.write_queue,
            self.imu_raw_queue,
            self.planter_raw_queue,
            output_dir=config.DATA_DIR,
        )
        self.writer_worker.start()

        self.sync_engine = SyncEngine(
            self.vicon_queue,
            self.imu_worker,
            self.planter_worker,
            self.write_queue,
        )
        self.sync_engine.start()

        self.is_recording = True
        print(f'[App] 开始采集: {self.writer_worker.get_main_filename()}')

    def stop_recording(self):
        if not self.is_recording:
            print('[App] 当前未采集')
            return

        if self.sync_engine:
            self.sync_engine.stop()
            self.sync_engine.join(timeout=5)
        if self.writer_worker:
            self.writer_worker.stop()
            self.writer_worker.join(timeout=5)

        self.is_recording = False
        stats = self.sync_engine.get_statistics() if self.sync_engine else {}
        print(f'[App] 采集停止，统计: {stats}')
        if self.writer_worker:
            print(f'[App] 数据文件: {self.writer_worker.get_main_filename()}')

    def print_status(self):
        vicon_state = 'connected' if self.vicon_worker.is_connected() else 'disconnected'
        imu_state = 'connected' if self.imu_worker.is_connected() else 'unavailable'
        planter_state = self.planter_worker.get_connection_status()
        latest = self.vicon_worker.get_latest_frame()
        print('-' * 60)
        print(f'Vicon: {vicon_state}')
        print(f'IMU: {imu_state}')
        print(f"Planter: {'connected' if self.planter_worker.is_connected() else 'partial/unavailable'} | Left={planter_state['Left']} Right={planter_state['Right']}")
        print(f'Recording: {self.is_recording}')
        print(f"Latest Frame: {latest['frame_num']}")
        print(f"Subject: {latest['subject_name']}")
        print(f"Process Rate: {latest['process_rate']}")
        print('-' * 60)

    def shutdown(self):
        if self.is_recording:
            self.stop_recording()

        print('[App] 正在关闭线程...')
        self.vicon_worker.stop()
        self.imu_worker.stop()
        self.planter_worker.stop()
        for worker in (self.vicon_worker, self.imu_worker, self.planter_worker):
            worker.join(timeout=2)
        print('[App] 已退出')


def main():
    print('=' * 50)
    print('Vicon+IMU+Planter 数据采集系统（新架构）')
    print('=' * 50)
    app = AppController()
    app.start_workers()

    print('输入命令: start / stop / status / quit')
    try:
        while True:
            cmd = input('> ').strip().lower()
            if cmd == 'start':
                app.start_recording()
            elif cmd == 'stop':
                app.stop_recording()
            elif cmd == 'status':
                app.print_status()
            elif cmd in {'quit', 'exit'}:
                break
            elif cmd == '':
                continue
            else:
                print('未知命令，请输入: start / stop / status / quit')
    finally:
        app.shutdown()


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(f'[FATAL] 程序异常: {e}')
        import traceback
        traceback.print_exc()
        sys.exit(1)
