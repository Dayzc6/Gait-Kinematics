# -*- coding: utf-8 -*-
"""
路线2：统一采集会话入口

目标：
- 同时启动 Vicon / IMU / Planter 三路采集
- 三者都按各自的绝对时间戳记录
- 不做实时跨设备同步
- 供后续离线解码、重建、重采样到 Vicon 时间轴使用
"""
import os
import sys
import threading
import time
from queue import Queue

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(CURRENT_DIR)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from common import JsonlWriter, make_session_prefix

try:
    from DataCollect.Data_Collecter import config
    from DataCollect.Data_Collecter.experiments.common import connect_vicon, collect_runtime_diagnostics, print_runtime_diagnostics
except ImportError:
    import config
    from experiments.common import connect_vicon, collect_runtime_diagnostics, print_runtime_diagnostics

import serial

DURATION_SECONDS = 20


class ViconCaptureThread(threading.Thread):
    def __init__(self, writer, duration_seconds):
        super().__init__(daemon=True)
        self.writer = writer
        self.duration_seconds = duration_seconds
        self.frame_count = 0
        self.error = None

    def run(self):
        client = connect_vicon(enable_segment=False, enable_marker=True)
        try:
            diagnostics = collect_runtime_diagnostics(client)
            print_runtime_diagnostics(diagnostics, 'route2_capture_session_vicon')
            end_time = time.time() + self.duration_seconds
            while time.time() < end_time:
                if client.GetFrame():
                    recv_ts = time.time()
                    frame_num = client.GetFrameNumber()
                    try:
                        frame_rate = client.GetFrameRate()
                    except Exception:
                        frame_rate = None
                    self.writer.write({
                        'recv_timestamp': recv_ts,
                        'frame_num': frame_num,
                        'frame_rate': frame_rate,
                    })
                    self.frame_count += 1
        except Exception as e:
            self.error = e
        finally:
            client.Disconnect()


class IMURawCaptureThread(threading.Thread):
    def __init__(self, writer, duration_seconds):
        super().__init__(daemon=True)
        self.writer = writer
        self.duration_seconds = duration_seconds
        self.chunk_count = 0
        self.error = None

    def run(self):
        ser = None
        try:
            ser = serial.Serial(config.IMU_PORT, config.IMU_BAUDRATE, timeout=config.IMU_TIMEOUT)
            try:
                ser.set_buffer_size(rx_size=10240)
            except Exception:
                pass
            print(f'[route2] IMU raw capture open: {config.IMU_PORT} @ {config.IMU_BAUDRATE}')
            end_time = time.time() + self.duration_seconds
            while time.time() < end_time:
                waiting = ser.in_waiting
                if waiting > 0:
                    data = ser.read(waiting)
                    if data:
                        self.writer.write({
                            'recv_timestamp': time.time(),
                            'raw_hex': data.hex(),
                        })
                        self.chunk_count += 1
                time.sleep(0.001)
        except Exception as e:
            self.error = e
            print(f'[route2] IMU raw capture failed: {e}')
        finally:
            if ser and ser.is_open:
                ser.close()


class PlanterPortCaptureThread(threading.Thread):
    def __init__(self, port, side, writer, duration_seconds):
        super().__init__(daemon=True)
        self.port = port
        self.side = side
        self.writer = writer
        self.duration_seconds = duration_seconds
        self.chunk_count = 0
        self.error = None

    def run(self):
        ser = None
        try:
            ser = serial.Serial(
                self.port,
                config.PLANTER_BAUD_RATE,
                timeout=config.PLANTER_TIMEOUT,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
            )
            print(f'[route2] Planter {self.side} open: {self.port} @ {config.PLANTER_BAUD_RATE}')
            end_time = time.time() + self.duration_seconds
            while time.time() < end_time:
                data = ser.read(10)
                if data:
                    self.writer.write({
                        'recv_timestamp': time.time(),
                        'side': self.side,
                        'raw_hex': data.hex(),
                    })
                    self.chunk_count += 1
                time.sleep(0.001)
        except Exception as e:
            self.error = e
            print(f'[route2] Planter {self.side} capture failed: {e}')
        finally:
            if ser and ser.is_open:
                ser.close()


def run_capture_session():
    session_prefix = make_session_prefix('session')
    vicon_writer = JsonlWriter(session_prefix + '_vicon.jsonl')
    imu_writer = JsonlWriter(session_prefix + '_imu.jsonl')
    planter_writer = JsonlWriter(session_prefix + '_planter.jsonl')

    vicon_thread = ViconCaptureThread(vicon_writer, DURATION_SECONDS)
    imu_thread = IMURawCaptureThread(imu_writer, DURATION_SECONDS)
    planter_left = PlanterPortCaptureThread(config.PLANTER_LEFT_PORT, 'Left', planter_writer, DURATION_SECONDS)
    planter_right = PlanterPortCaptureThread(config.PLANTER_RIGHT_PORT, 'Right', planter_writer, DURATION_SECONDS)

    try:
        vicon_thread.start()
        imu_thread.start()
        planter_left.start()
        planter_right.start()

        vicon_thread.join()
        imu_thread.join()
        planter_left.join()
        planter_right.join()

        print('[route2] capture_session done')
        print({'vicon_frames': vicon_thread.frame_count, 'vicon_error': str(vicon_thread.error) if vicon_thread.error else None})
        print({'imu_chunks': imu_thread.chunk_count, 'imu_error': str(imu_thread.error) if imu_thread.error else None})
        print({'planter_left_chunks': planter_left.chunk_count, 'planter_left_error': str(planter_left.error) if planter_left.error else None})
        print({'planter_right_chunks': planter_right.chunk_count, 'planter_right_error': str(planter_right.error) if planter_right.error else None})
        print({'session_prefix': session_prefix})
    finally:
        vicon_writer.close()
        imu_writer.close()
        planter_writer.close()


if __name__ == '__main__':
    run_capture_session()
