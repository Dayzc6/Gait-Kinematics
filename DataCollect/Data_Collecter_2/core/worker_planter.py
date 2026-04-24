# -*- coding: utf-8 -*-
"""
Planter 接收线程
保留原有串口接收与解析逻辑，同时增加：
1. latest 数据
2. 带时间戳的环形缓冲区
3. 原始流写队列
"""
import time
import serial
from collections import deque
from threading import Thread, Lock

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

        self.is_running = True
        self.ser = None
        self.data_lock = Lock()
        self.left_data = [0] * config.PLANTER_SENSOR_POINTS
        self.right_data = [0] * config.PLANTER_SENSOR_POINTS
        self.latest_packet = None
        self.packet_buffer = deque(maxlen=config.PLANTER_BUFFER_SIZE)

    def get_latest_data(self):
        with self.data_lock:
            return {
                "Left": self.left_data.copy(),
                "Right": self.right_data.copy()
            }

    def get_latest_packet(self):
        with self.data_lock:
            return self.latest_packet

    def get_buffer_snapshot(self):
        with self.data_lock:
            return list(self.packet_buffer)

    def is_connected(self):
        return self.ser is not None and self.ser.is_open

    def _init_sensor(self):
        try:
            self.ser.write(b'INIT_LEFT\n')
            time.sleep(0.5)
            self.ser.read_all()
            self.ser.write(b'INIT_RIGHT\n')
            time.sleep(0.5)
            self.ser.read_all()
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
            print(f"[PlanterWorker] 串口已打开: {self.port} @ {self.baudrate}")
            self._init_sensor()
        except Exception as e:
            print(f"[PlanterWorker] 串口打开失败: {e}")
            return

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
                    if result:
                        side, values = result
                        recv_ts = time.time()
                        with self.data_lock:
                            if side == "Left":
                                self.left_data = values
                            else:
                                self.right_data = values
                            packet = PlanterPacket(
                                recv_timestamp=recv_ts,
                                left=self.left_data.copy(),
                                right=self.right_data.copy()
                            )
                            self.latest_packet = packet
                            self.packet_buffer.append(packet)
                        if self.raw_queue is not None:
                            try:
                                self.raw_queue.put(packet, timeout=0.01)
                            except Exception:
                                pass

                time.sleep(0.002)
        finally:
            if self.ser and self.ser.is_open:
                self.ser.close()

    def stop(self):
        self.is_running = False
