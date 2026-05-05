# -*- coding: utf-8 -*-
"""
独立 Planter 实时采集模块
- 完全对标 reference/two_plant_2.py (mainwindow 绑定的 planter 接收逻辑)
- 左右脚分别独立接收与实时解析
- 左右脚分别写入各自 CSV
- 保留接收层可观测统计
"""
import os
import sys
import time
import struct
from threading import Event, Thread, Lock

import serial

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(CURRENT_DIR)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

try:
    from DataCollect.Data_Collecter.independent_capture import local_config as config
    from DataCollect.Data_Collecter.independent_capture.common import now_mono, now_wall
    from DataCollect.Data_Collecter.independent_capture.schema import PLANTER_HEADERS
except ImportError:
    from independent_capture import local_config as config
    from independent_capture.common import now_mono, now_wall
    from independent_capture.schema import PLANTER_HEADERS


SENSOR_POINTS = 18
BAUD_RATE = 115200
FRAME_HEADER = 0xAA
FRAME_LEN_CANDIDATES = (39, 38)


class FootSensor(Thread):
    """
    完全对标 reference/two_plant_2.py 的 FootSensor 类
    - QThread 改为普通 Thread（不依赖 PyQt5）
    - 保留所有帧解析和数据结构
    """
    def __init__(self, port, is_left, callback=None, ser=None, parent=None):
        super().__init__(daemon=True)
        self.ser = None
        self.port = None
        self.is_left = is_left
        self.callback = callback
        self.data = [0] * SENSOR_POINTS
        self.lock = Lock()
        self.raw_buffer = bytearray()
        self.running = Event()
        self.running.set()
        self.latest_packet = None
        self.frame_id = 0

        if ser is not None:
            self.ser = ser
            self.port = ser.port
            print(f"{'左足' if self.is_left else '右足'}传感器使用外部串口: {self.port}")
        else:
            self.port = port
            self.ser = None
            try:
                self.ser = serial.Serial(
                    port=port,
                    baudrate=BAUD_RATE,
                    timeout=2,
                    parity=serial.PARITY_NONE,
                    stopbits=serial.STOPBITS_ONE
                )
                print(f"{'左足' if self.is_left else '右足'}传感器已连接: {port}")

                if self.is_left:
                    self._send_command(b'INIT_LEFT\n')
                else:
                    self._send_command(b'INIT_RIGHT\n')

            except Exception as e:
                raise RuntimeError(f"{port} 初始化失败: {str(e)}")

    def _send_command(self, cmd, retries=3):
        for _ in range(retries):
            self.ser.write(cmd)
            time.sleep(0.5)
            ack = self.ser.read_all()
            if ack:
                print(f"命令 {cmd} 响应: {ack.hex()}")
                return True
        print(f"警告: {self.port} 未收到响应")
        return False

    def _parse_packet(self, packet: bytes):
        """
        对标 reference/two_plant_2.py 的 _parse_packet 方法
        - 不做 side 强约束过滤
        - 使用兜底逻辑
        """
        if not packet or len(packet) < 2 or packet[0] != FRAME_HEADER:
            return False

        data_bytes_needed = 2 + 2 * SENSOR_POINTS
        if len(packet) < data_bytes_needed:
            return False

        sensor_id = packet[1]
        if sensor_id not in (0x01, 0x02):
            return False

        values = []
        for i in range(SENSOR_POINTS):
            offset = 2 + i * 2
            low = packet[offset]
            high = packet[offset + 1]
            value = low | (high << 8)
            values.append(value)

        side = "left" if sensor_id == 0x01 else "right"

        if self.callback is not None:
            try:
                self.callback(side, values, time.time())
            except TypeError:
                self.callback(side, values)
        else:
            with self.lock:
                self.data = values

        return True

    def stop(self):
        try:
            self.running.clear()
        except Exception:
            pass
        try:
            if getattr(self, "ser", None) and self.ser.is_open:
                self.ser.close()
        except Exception:
            pass

    def run(self, callback=None, bytes_per_read: int = 10):
        """
        对标 reference/two_plant_2.py 的 run 方法
        - 帧长候选顺序: (39, 38)
        - 使用 struct.unpack 解析
        - 兜底 side 逻辑
        """
        if callback is not None:
            self.callback = callback

        while self.running.is_set():
            try:
                chunk = self.ser.read(bytes_per_read)
                if chunk:
                    self.raw_buffer.extend(chunk)

                while True:
                    while self.raw_buffer and self.raw_buffer[0] != FRAME_HEADER:
                        self.raw_buffer.pop(0)
                    if len(self.raw_buffer) < 3:
                        break

                    foot_id = self.raw_buffer[1]
                    if foot_id not in (0x01, 0x02):
                        self.raw_buffer.pop(0)
                        continue

                    frame = None
                    frame_len = None
                    for L in FRAME_LEN_CANDIDATES:
                        if len(self.raw_buffer) >= L:
                            frame = bytes(self.raw_buffer[:L])
                            frame_len = L
                            del self.raw_buffer[:L]
                            break

                    if frame is None:
                        break

                    data_bytes = frame[2:2 + SENSOR_POINTS * 2]
                    if len(data_bytes) < SENSOR_POINTS * 2:
                        continue

                    values = list(struct.unpack("<" + "H" * SENSOR_POINTS, data_bytes))

                    side = "left" if foot_id == 0x01 else "right"
                    if self.is_left and side != "left":
                        side = "left"
                    if (not self.is_left) and side != "right":
                        side = "right"

                    with self.lock:
                        self.data = values
                        self.frame_id = getattr(self, "frame_id", 0) + 1
                        ts = time.time()
                        self.latest_packet = {"side": side, "values": values, "ts": ts, "frame_id": self.frame_id}

                    if self.callback is not None:
                        try:
                            self.callback(side, values, ts)
                        except TypeError:
                            self.callback(side, values)

                time.sleep(0.002)

            except Exception as e:
                print(f"[FootSensor] 读取异常: {e}")
                time.sleep(0.05)
                continue

        return


class SinglePlanterCaptureWorker(Thread):
    """
    独立 Planter 采集worker
    - 基于 FootSensor (reference 逻辑)
    - 保留 CSV 写入和可观测统计
    - 支持左右脚独立运行
    """
    SENSOR_POINTS = config.PLANTER_SENSOR_POINTS

    def __init__(self, session_id, trial_id, subject_id, side, port, csv_writer, baudrate=None, timeout=None, bytes_per_read=10):
        super().__init__(daemon=True)
        self.session_id = session_id
        self.trial_id = trial_id
        self.subject_id = subject_id
        self.side = side
        self.port = port
        self.csv_writer = csv_writer
        self.baudrate = baudrate or config.PLANTER_BAUD_RATE
        self.timeout = config.PLANTER_TIMEOUT if timeout is None else timeout
        self.bytes_per_read = bytes_per_read
        self.stop_event = Event()
        self.foot_sensor = None
        self.seq = 0
        self.init_ok = 0
        self.stats = {
            'decoded_rows': 0,
            'parse_failures': 0,
            'init_ok': 0,
            'read_calls': 0,
            'nonempty_reads': 0,
            'empty_reads': 0,
            'raw_bytes_received': 0,
            'max_chunk_size': 0,
            'max_buffer_len': 0,
            'raw_bytes_left_in_buffer_on_stop': 0,
            'resync_events': 0,
            'bytes_dropped_resync': 0,
            'invalid_foot_id_events': 0,
            'candidate_frames_total': 0,
            'candidate_frames_38': 0,
            'candidate_frames_39': 0,
            'side_mismatch_rows': 0,
            'all_zero_rows': 0,
            'review_rows': 0,
        }

    def stop(self):
        self.stop_event.set()

    def get_stats(self):
        return dict(self.stats)

    def _on_packet(self, side: str, values: list, ts: float = None):
        """
        FootSensor 回调：每解析出一帧即触发
        - 对标 reference 的 _on_plantar_packet
        - 保留 CSV 写入
        """
        if ts is None:
            ts = time.perf_counter()

        self.seq += 1
        all_zero_flag = 1 if all(v == 0 for v in values) else 0

        recv_wall = now_wall()
        recv_mono = now_mono()

        row = [
            self.session_id,
            self.trial_id,
            self.subject_id,
            recv_wall,
            recv_wall,
            recv_mono,
            self.side,
            self.seq,
            0,
            0,
            1,
            self.init_ok,
            39,
            'reference_style',
            all_zero_flag,
            0,
        ] + list(values)

        self.csv_writer.write_row(row)
        self.stats['decoded_rows'] += 1

        if all_zero_flag:
            self.stats['all_zero_rows'] += 1

    def run(self):
        is_left = (self.side == 'Left')
        try:
            self.foot_sensor = FootSensor(
                port=self.port,
                is_left=is_left,
                callback=self._on_packet,
                ser=None
            )
            self.init_ok = 1
            self.stats['init_ok'] = 1
            print(f'[PlanterCapture-{self.side}] started with reference logic')
        except Exception as e:
            print(f'[PlanterCapture-{self.side}] init failed: {e}')
            return

        last_flush = now_mono()
        try:
            self.foot_sensor.run(callback=self._on_packet, bytes_per_read=self.bytes_per_read)
        except Exception as e:
            print(f'[PlanterCapture-{self.side}] runtime error: {e}')
        finally:
            if hasattr(self.foot_sensor, 'raw_buffer'):
                self.stats['raw_bytes_left_in_buffer_on_stop'] = len(self.foot_sensor.raw_buffer)
            if self.foot_sensor and hasattr(self.foot_sensor, 'ser') and self.foot_sensor.ser and self.foot_sensor.ser.is_open:
                try:
                    self.foot_sensor.ser.close()
                except Exception:
                    pass
            self.csv_writer.flush()
            print(f'[PlanterCapture-{self.side}] stopped')