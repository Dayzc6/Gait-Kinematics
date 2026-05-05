# -*- coding: utf-8 -*-
"""
独立实时采集统一入口（CLI）
- 控制方式：start / stop / status / quit
- 启动 Vicon / IMU / Planter 独立实时采集
- 分别输出 vicon.csv / imu.csv / planter_left.csv / planter_right.csv
- 写入 session metadata
- 不影响主链路 main.py
"""
import os
import sys
import time

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(CURRENT_DIR)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

try:
    from DataCollect.Data_Collecter.independent_capture import local_config as config
    from DataCollect.Data_Collecter.independent_capture.common import CsvStreamWriter, create_session_dir, make_session_id, now_wall, write_metadata
    from DataCollect.Data_Collecter.independent_capture.imu_capture import IMUCaptureWorker
    from DataCollect.Data_Collecter.independent_capture.planter_capture import SinglePlanterCaptureWorker
    from DataCollect.Data_Collecter.independent_capture.schema import IMU_HEADERS, PLANTER_HEADERS
    from DataCollect.Data_Collecter.independent_capture.vicon_capture import ViconCaptureWorker
except ImportError as e:
    print(f'[ERROR] 导入错误: {e}')
    print('[ERROR] 请确认当前工作目录在项目根目录下，或使用 -m 方式启动')
    sys.exit(1)


class IndependentAppController:
    def __init__(self, trial_id='trial_001', subject_id='subject_001'):
        self.trial_id = trial_id
        self.subject_id = subject_id

        self.session_id = None
        self.session_dir = None
        self.metadata_path = None
        self.metadata = None

        self.vicon_writer = None
        self.imu_writer = None
        self.planter_left_writer = None
        self.planter_right_writer = None

        self.vicon_worker = None
        self.imu_worker = None
        self.planter_left_worker = None
        self.planter_right_worker = None

        self.workers_started = False
        self.is_recording = False

    def _build_metadata(self):
        return {
            'session_id': self.session_id,
            'trial_id': self.trial_id,
            'subject_id': self.subject_id,
            'start_wall_time': now_wall(),
            'schema_version': 'independent_capture_v2',
            'vicon': {
                'host_ip': config.VICON_HOST_IP,
                'stream_mode': config.VICON_STREAM_MODE,
                'enable_segments': config.VICON_ENABLE_SEGMENTS,
            },
            'imu': {
                'port': config.IMU_PORT,
                'baudrate': config.IMU_BAUDRATE,
                'timeout': config.IMU_TIMEOUT,
                'target_rate_hz': 30,
            },
            'planter': {
                'left_port': config.PLANTER_LEFT_PORT,
                'right_port': config.PLANTER_RIGHT_PORT,
                'baudrate': config.PLANTER_BAUD_RATE,
                'timeout': config.PLANTER_TIMEOUT,
                'target_rate_hz': 20,
                'split_files': True,
            },
            'notes': 'Independent realtime capture datasets, no cross-modal sync.',
        }

    def start_recording(self):
        if self.is_recording:
            print('[IndependentCapture] 已在采集中')
            return

        self.session_id = make_session_id('independent')
        self.session_dir = create_session_dir(self.session_id)
        self.metadata_path = os.path.join(self.session_dir, 'session_meta.json')
        self.metadata = self._build_metadata()
        write_metadata(self.metadata_path, self.metadata)

        vicon_path = os.path.join(self.session_dir, 'vicon.csv')
        imu_path = os.path.join(self.session_dir, 'imu.csv')
        planter_left_path = os.path.join(self.session_dir, 'planter_left.csv')
        planter_right_path = os.path.join(self.session_dir, 'planter_right.csv')

        self.vicon_worker = ViconCaptureWorker(self.session_id, self.trial_id, self.subject_id, csv_writer=None)
        try:
            self.vicon_worker._connect()
            self.vicon_worker._discover_subject_and_layout()
        except Exception as e:
            print(f'[IndependentCapture] Vicon 启动失败: {e}')
            try:
                if self.vicon_worker.client is not None:
                    self.vicon_worker.client.Disconnect()
            except Exception:
                pass
            self.vicon_worker = None
            return

        self.vicon_writer = CsvStreamWriter(vicon_path, self.vicon_worker.get_headers())
        self.vicon_worker.csv_writer = self.vicon_writer
        self.imu_writer = CsvStreamWriter(imu_path, IMU_HEADERS)
        self.planter_left_writer = CsvStreamWriter(planter_left_path, PLANTER_HEADERS)
        self.planter_right_writer = CsvStreamWriter(planter_right_path, PLANTER_HEADERS)

        self.imu_worker = IMUCaptureWorker(self.session_id, self.trial_id, self.subject_id, self.imu_writer)
        self.planter_left_worker = SinglePlanterCaptureWorker(self.session_id, self.trial_id, self.subject_id, 'Left', config.PLANTER_LEFT_PORT, self.planter_left_writer)
        self.planter_right_worker = SinglePlanterCaptureWorker(self.session_id, self.trial_id, self.subject_id, 'Right', config.PLANTER_RIGHT_PORT, self.planter_right_writer)

        self.vicon_worker.start()
        self.imu_worker.start()
        self.planter_left_worker.start()
        self.planter_right_worker.start()
        self.workers_started = True
        self.is_recording = True

        print('=' * 60)
        print('Independent Vicon + IMU + Planter capture')
        print(f'session_id: {self.session_id}')
        print(f'session_dir: {self.session_dir}')
        print('=' * 60)

    def stop_recording(self):
        if not self.is_recording:
            print('[IndependentCapture] 当前未采集')
            return

        for worker in (self.vicon_worker, self.imu_worker, self.planter_left_worker, self.planter_right_worker):
            if worker is not None:
                try:
                    worker.stop()
                except Exception:
                    pass

        for worker in (self.vicon_worker, self.imu_worker, self.planter_left_worker, self.planter_right_worker):
            if worker is not None:
                worker.join(timeout=3)

        for writer in (self.vicon_writer, self.imu_writer, self.planter_left_writer, self.planter_right_writer):
            if writer is not None:
                writer.close()

        if self.metadata is not None:
            self.metadata['end_wall_time'] = now_wall()
            self.metadata['vicon_stats'] = self.vicon_worker.get_stats() if self.vicon_worker else {}
            self.metadata['imu_stats'] = self.imu_worker.get_stats() if self.imu_worker else {}
            self.metadata['planter_left_stats'] = self.planter_left_worker.get_stats() if self.planter_left_worker else {}
            self.metadata['planter_right_stats'] = self.planter_right_worker.get_stats() if self.planter_right_worker else {}
            write_metadata(self.metadata_path, self.metadata)

        print('[IndependentCapture] 采集停止')
        print({'vicon': self.vicon_worker.get_stats() if self.vicon_worker else {}})
        print({'imu': self.imu_worker.get_stats() if self.imu_worker else {}})
        print({'planter_left': self.planter_left_worker.get_stats() if self.planter_left_worker else {}})
        print({'planter_right': self.planter_right_worker.get_stats() if self.planter_right_worker else {}})
        print({'session_dir': self.session_dir})

        self.vicon_writer = None
        self.imu_writer = None
        self.planter_left_writer = None
        self.planter_right_writer = None
        self.vicon_worker = None
        self.imu_worker = None
        self.planter_left_worker = None
        self.planter_right_worker = None
        self.metadata = None
        self.metadata_path = None
        self.session_id = None
        self.session_dir = None
        self.workers_started = False
        self.is_recording = False

    def print_status(self):
        vicon_state = 'connected' if self.vicon_worker and self.vicon_worker.client and self.vicon_worker.client.IsConnected() else 'disconnected'
        imu_state = 'connected' if self.imu_worker and self.imu_worker.is_alive() else 'unavailable'
        planter_left_state = 'connected' if self.planter_left_worker and self.planter_left_worker.is_alive() else 'unavailable'
        planter_right_state = 'connected' if self.planter_right_worker and self.planter_right_worker.is_alive() else 'unavailable'
        print('-' * 60)
        print(f'Vicon: {vicon_state}')
        print(f'IMU: {imu_state}')
        print(f'Planter: Left={planter_left_state} Right={planter_right_state}')
        print(f'Recording: {self.is_recording}')
        print(f'Session ID: {self.session_id}')
        print(f'Session Dir: {self.session_dir}')
        if self.vicon_worker is not None:
            print(f"Vicon Subject: {self.vicon_worker.subject_name}")
            print(f"Vicon Stats: {self.vicon_worker.get_stats()}")
        if self.imu_worker is not None:
            print(f"IMU Stats: {self.imu_worker.get_stats()}")
        if self.planter_left_worker is not None and self.planter_right_worker is not None:
            print(f"Planter Left Stats: {self.planter_left_worker.get_stats()}")
            print(f"Planter Right Stats: {self.planter_right_worker.get_stats()}")
        print('-' * 60)

    def shutdown(self):
        if self.is_recording:
            self.stop_recording()
        print('[IndependentCapture] 已退出')


def main():
    print('=' * 60)
    print('Independent Vicon + IMU + Planter 数据采集系统')
    print('=' * 60)
    app = IndependentAppController()
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
