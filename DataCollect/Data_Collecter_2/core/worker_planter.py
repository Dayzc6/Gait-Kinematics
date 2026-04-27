# -*- coding: utf-8 -*-
"""
Planter（足底压力）双串口接收模块
- 左右脚各一个独立接收器 / 串口
- 两个子线程分别读取 Left / Right
- 聚合器对外暴露统一接口：
  - start / stop / join
  - is_connected / get_connection_status
  - get_latest_data
  - get_buffer_snapshot
- 为 SyncEngine 提供统一的 PlanterPacket 缓冲视图
"""
import copy
import os
import sys
import time
from collections import deque
from threading import Thread, Lock

import serial

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(CURRENT_DIR)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

try:
    from DataCollect.Data_Collecter_2 import config
    from DataCollect.Data_Collecter_2.utils.protocol_planter import parse_planter_frame
    from DataCollect.Data_Collecter_2.utils.data_models import PlanterPacket
except ImportError:
    import config
    from utils.protocol_planter import parse_planter_frame
    from utils.data_models import PlanterPacket


class SingleFootPlanterWorker(Thread):
    def __init__(self, port, side, baudrate=115200, timeout=2):
        super().__init__()
        self.daemon = True

        self.port = port
        self.side = side
        self.baudrate = baudrate
        self.timeout = timeout

        self.is_running = False
        self.ser = None
        self.available = False
        self.data_lock = Lock()
        self.latest_data = [0] * config.PLANTER_SENSOR_POINTS
        self.sensor_initialized = False
        self.last_update_timestamp = None

    def get_latest_data(self):
        with self.data_lock:
            return list(self.latest_data)

    def get_latest_timestamp(self):
        with self.data_lock:
            return self.last_update_timestamp

    def is_connected(self):
        return self.available and self.ser is not None and self.ser.is_open

    def _init_sensor(self):
        if not self.ser or not self.ser.is_open:
            return False

        cmd = b'INIT_LEFT\n' if self.side == 'Left' else b'INIT_RIGHT\n'
        try:
            self.ser.write(cmd)
            time.sleep(0.5)
            ack = self.ser.read_all()
            print(f"[SingleFootPlanterWorker-{self.side}] 初始化响应: {ack.hex() if ack else 'None'}")
            self.sensor_initialized = True
            return True
        except Exception as e:
            print(f"[SingleFootPlanterWorker-{self.side}] 初始化命令失败: {e}")
            return False

    def run(self):
        try:
            self.ser = serial.Serial(
                self.port,
                self.baudrate,
                timeout=self.timeout,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
            )
            self.available = True
            print(f"[SingleFootPlanterWorker-{self.side}] 串口已打开: {self.port} @ {self.baudrate}")
            self._init_sensor()
        except Exception as e:
            self.available = False
            print(f"[SingleFootPlanterWorker-{self.side}] 串口打开失败，将以空数据模式运行: {e}")
            return

        self.is_running = True
        raw_buffer = bytearray()

        try:
            while self.is_running:
                chunk = self.ser.read(10)
                if chunk:
                    raw_buffer.extend(chunk)

                while True:
                    while raw_buffer and raw_buffer[0] != config.PLANTER_FRAME_HEADER:
                        raw_buffer.pop(0)

                    if len(raw_buffer) < 3:
                        break

                    foot_id = raw_buffer[1]
                    if foot_id not in (0x01, 0x02):
                        raw_buffer.pop(0)
                        continue

                    frame = None
                    for frame_len in config.PLANTER_FRAME_LENGTH_CANDIDATES:
                        if len(raw_buffer) >= frame_len:
                            frame = bytes(raw_buffer[:frame_len])
                            del raw_buffer[:frame_len]
                            break

                    if frame is None:
                        break

                    result = parse_planter_frame(frame)
                    if not result:
                        continue

                    _, values = result
                    with self.data_lock:
                        self.latest_data = values
                        self.last_update_timestamp = time.time()

                time.sleep(0.002)
        except Exception as e:
            print(f"[SingleFootPlanterWorker-{self.side}] 接收异常: {e}")
        finally:
            self.stop()

    def stop(self):
        self.is_running = False
        if self.ser and self.ser.is_open:
            try:
                self.ser.close()
            except Exception:
                pass
        print(f"[SingleFootPlanterWorker-{self.side}] 线程已停止")


class PlanterWorker:
    def __init__(self, left_port, right_port, baudrate=115200, timeout=2, raw_queue=None):
        self.left_worker = SingleFootPlanterWorker(left_port, 'Left', baudrate, timeout)
        self.right_worker = SingleFootPlanterWorker(right_port, 'Right', baudrate, timeout)
        self.raw_queue = raw_queue
        self.buffer_lock = Lock()
        self.packet_buffer = deque(maxlen=config.PLANTER_BUFFER_MAXLEN)
        self.is_running = False
        self.collector_thread = None

    def start(self):
        self.left_worker.start()
        self.right_worker.start()
        self.is_running = True
        self.collector_thread = Thread(target=self._collector_loop, daemon=True)
        self.collector_thread.start()

    def _collector_loop(self):
        last_emitted_ts = None
        while self.is_running:
            left_data = self.left_worker.get_latest_data()
            right_data = self.right_worker.get_latest_data()
            left_ts = self.left_worker.get_latest_timestamp()
            right_ts = self.right_worker.get_latest_timestamp()

            candidate_ts = max(ts for ts in (left_ts, right_ts) if ts is not None) if (left_ts is not None or right_ts is not None) else None
            if candidate_ts is not None and candidate_ts != last_emitted_ts:
                packet = PlanterPacket(
                    recv_timestamp=candidate_ts,
                    left=copy.copy(left_data),
                    right=copy.copy(right_data),
                )
                with self.buffer_lock:
                    self.packet_buffer.append(packet)
                if self.raw_queue is not None:
                    try:
                        self.raw_queue.put_nowait(packet)
                    except Exception:
                        pass
                last_emitted_ts = candidate_ts

            time.sleep(0.002)

    def stop(self):
        self.is_running = False
        self.left_worker.stop()
        self.right_worker.stop()
        if self.collector_thread and self.collector_thread.is_alive():
            self.collector_thread.join(timeout=2)

    def join(self, timeout=None):
        self.left_worker.join(timeout=timeout)
        self.right_worker.join(timeout=timeout)
        if self.collector_thread:
            self.collector_thread.join(timeout=timeout)

    def is_connected(self):
        return self.left_worker.is_connected() and self.right_worker.is_connected()

    def get_connection_status(self):
        return {
            'Left': self.left_worker.is_connected(),
            'Right': self.right_worker.is_connected(),
        }

    def get_latest_data(self):
        return {
            'Left': self.left_worker.get_latest_data(),
            'Right': self.right_worker.get_latest_data(),
        }

    def get_buffer_snapshot(self):
        with self.buffer_lock:
            return list(self.packet_buffer)


if __name__ == '__main__':
    print('[TEST] PlanterWorker 双串口单元测试')
    print('[TEST] 无串口设备，跳过实际测试')
    print('[TEST] 测试完成')
