# -*- coding: utf-8 -*-
"""
Planter（足底压力传感器）接收线程模块
功能：从串口读取左/右脚压力数据帧，并保留原始包缓冲供同步线程匹配。
"""
import copy
import time
from collections import deque
from threading import Thread, Lock

import serial

try:
    from DataCollect.Data_Collecter_2 import config
    from DataCollect.Data_Collecter_2.utils.protocol_planter import parse_planter_frame
    from DataCollect.Data_Collecter_2.utils.data_models import PlanterPacket
except ImportError:
    import config
    from utils.protocol_planter import parse_planter_frame
    from utils.data_models import PlanterPacket


class PlanterWorker(Thread):
    def __init__(self, port, baudrate=115200, timeout=2, raw_queue=None):
        super().__init__()
        self.daemon = True

        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.raw_queue = raw_queue

        self.is_running = False
        self.ser = None
        self.available = False

        self.data_lock = Lock()
        self.buffer_lock = Lock()
        self.left_data = [0] * config.PLANTER_SENSOR_POINTS
        self.right_data = [0] * config.PLANTER_SENSOR_POINTS
        self.packet_buffer = deque(maxlen=config.PLANTER_BUFFER_MAXLEN)
        self.sensor_initialized = False

    def get_latest_data(self):
        with self.data_lock:
            return {
                "Left": copy.copy(self.left_data),
                "Right": copy.copy(self.right_data)
            }

    def get_buffer_snapshot(self):
        with self.buffer_lock:
            return list(self.packet_buffer)

    def is_connected(self):
        return self.available and self.ser is not None and self.ser.is_open

    def _init_sensor(self):
        if not self.ser or not self.ser.is_open:
            return False

        try:
            self.ser.write(b'INIT_LEFT\n')
            time.sleep(0.5)
            self.ser.read_all()
            self.ser.write(b'INIT_RIGHT\n')
            time.sleep(0.5)
            self.ser.read_all()
            self.sensor_initialized = True
            return True
        except Exception as e:
            print(f"[PlanterWorker] 初始化命令失败: {e}")
            return False

    def run(self):
        try:
            self.ser = serial.Serial(
                self.port,
                self.baudrate,
                timeout=self.timeout,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE
            )
            self.available = True
            print(f"[PlanterWorker] 串口已打开: {self.port} @ {self.baudrate}")
            self._init_sensor()
        except Exception as e:
            self.available = False
            print(f"[PlanterWorker] 串口打开失败，将以空数据模式运行: {e}")
            return

        self.is_running = True
        raw_buffer = bytearray()

        try:
            while self.is_running:
                chunk = self.ser.read(10)
                if chunk:
                    raw_buffer.extend(chunk)

                while True:
                    while raw_buffer and raw_buffer[0] != 0xAA:
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

                    side, values = result
                    packet = None
                    with self.data_lock:
                        if side == "Left":
                            self.left_data = values
                        else:
                            self.right_data = values
                        packet = PlanterPacket(
                            recv_timestamp=time.time(),
                            left=copy.copy(self.left_data),
                            right=copy.copy(self.right_data)
                        )

                    with self.buffer_lock:
                        self.packet_buffer.append(packet)

                    if self.raw_queue is not None:
                        try:
                            self.raw_queue.put_nowait(packet)
                        except Exception:
                            pass

                time.sleep(0.002)
        except Exception as e:
            print(f"[PlanterWorker] 接收异常: {e}")
        finally:
            self.stop()

    def stop(self):
        self.is_running = False
        if self.ser and self.ser.is_open:
            try:
                self.ser.close()
            except Exception:
                pass
        print("[PlanterWorker] 线程已停止")


if __name__ == '__main__':
    print("[TEST] PlanterWorker单元测试")
    print("[TEST] 无串口设备，跳过实际测试")
    print("[TEST] 测试完成")
