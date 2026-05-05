import struct
import time
import threading
import serial
from PyQt5.QtCore import QThread, pyqtSignal
# 放在类外或类上方的常量（如已有，可不用重复定义）
SENSOR_POINTS = 18
BAUD_RATE=115200
class FootSensor(QThread):
    foot_data_ready = pyqtSignal(dict)
    def __init__(self, port, is_left,ser=None,parent=None):
        super().__init__(parent)
        self.ser = None
        self.port = None
        self.is_left = is_left  # 明确标记传感器位置
        self.data = [0] * SENSOR_POINTS
        self.lock = threading.Lock()
        self.raw_buffer = bytearray()
        self.running = threading.Event()
        self.running.set()
        self.latest_packet=None

        # 初始化硬件
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
                    
                # 关键修复：发送正确的初始化命令
                if self.is_left:
                    self._send_command(b'INIT_LEFT\n')  # 左足专用命令
                else:
                    self._send_command(b'INIT_RIGHT\n')  # 右足专用命令

            except Exception as e:
                raise RuntimeError(f"{port} 初始化失败: {str(e)}")

    def _send_command(self, cmd, retries=3):
        """可靠发送命令"""
        for _ in range(retries):
            self.ser.write(cmd)
            time.sleep(0.5)
            ack = self.ser.read_all()
            if ack:
                print(f"命令 {cmd} 响应: {ack.hex()}")
                return True
        print(f"警告: {self.port} 未收到响应")
        return False

    def _parse_packet(self, packet: bytes, callback=None) -> bool:
        """
        解析一帧 AA 协议数据：
        - 校验头、长度、左右ID
        - 解析 18×uint16（小端）
        - 若提供 callback：callback(side, values, ts) （兼容 callback(side, values)）
        - 否则写入 self.data
        返回：是否解析成功
        """
        FRAME_HEADER = 0xAA
        if not packet or len(packet) < 2 or packet[0] != FRAME_HEADER:
            return False

        # 2字节头部后应至少有 18*2 字节数据
        data_bytes_needed = 2 + 2 * SENSOR_POINTS
        if len(packet) < data_bytes_needed:
            return False

        # 第2字节：左右脚 ID（0x01=左，0x02=右）
        sensor_id = packet[1]
        if sensor_id not in (0x01, 0x02):
            return False

        # 若你希望强约束“实例侧”和“帧内ID”一致：
        if (self.is_left and sensor_id != 0x01) or ((not self.is_left) and sensor_id != 0x02):
            # 可改成仅告警不返回 False（避免偶发ID错位导致丢帧）
            # print(f"ID冲突: 预期{'左足' if self.is_left else '右足'}, 收到ID 0x{sensor_id:02X}")
            return False

        # 解析 18×uint16（小端）：注意你原来这句是反了（小端应：low | (high<<8)）
        values = []
        for i in range(SENSOR_POINTS):
            offset = 2 + i * 2
            low  = packet[offset]
            high = packet[offset + 1]
            value = low | (high << 8)   # ✅ 小端正确写法（原来写成 (low<<8)|high 是大端）
            values.append(value)

        side = "left" if sensor_id == 0x01 else "right"

        if callback is not None:
            try:
                callback(side, values, time.time())
            except TypeError:
                # 兼容旧签名 callback(side, values)
                callback(side, values)
        else:
            # 无回调：把最新一帧写进 self.data，供外部轮询
            with self.lock:
                self.data = values

        # 如需调试可打开，但不建议每帧都 print 以免阻塞
        # print(f"[{ '左足' if self.is_left else '右足' }] 数据: {values[:3]} ...")
        return True
  
    def stop(self):
        """安全停止读取线程；如 ser 为内部创建则尝试关闭串口。"""
        try:
            self.running.clear()
        except Exception:
            pass
        # 如果你有“外部串口”标记，可加判断：if not self._external_ser:
        try:
            if getattr(self, "ser", None) and self.ser.is_open:
                self.ser.close()
        except Exception:
            pass

    def run(self, callback=None, bytes_per_read: int = 10):
        """
        持续读取串口并解析 AA 帧。
        - 若提供 callback，则每解析出一帧即回调：
            callback(side:str, values:List[int], ts:float)   # 推荐
          或兼容旧签名：
            callback(side:str, values:List[int])
        - 若未提供 callback，则把最新一帧写入 self.data（供外部轮询）

        :param callback: 可选回调；签名见上
        :param bytes_per_read: 每次串口读取的最大字节数
        """
        FRAME_HEADER = 0xAA
        FRAME_LEN_CANDIDATES = (39, 38)  # 先尝试 39, 不够再等下一轮；也兼容 38

        # 防抖：确保串口可用
        if not getattr(self, "ser", None):
            raise RuntimeError("FootSensor.read_data: 串口未初始化 self.ser is None")
        if not self.ser.is_open:
            # 尝试打开（若 __init__ 已打开，这里通常不会触发）
            try:
                self.ser.open()
            except Exception as e:
                raise RuntimeError(f"串口未打开且打开失败: {e}")

        # 主循环
        while self.running.is_set():
            try:
                chunk = self.ser.read(bytes_per_read)
                if chunk:
                    self.raw_buffer.extend(chunk)

                # 解析：尽量把缓冲区内的完整帧都吃掉
                while True:
                    # 1) 丢弃帧头前的噪声
                    while self.raw_buffer and self.raw_buffer[0] != FRAME_HEADER:
                        self.raw_buffer.pop(0)
                    if len(self.raw_buffer) < 3:
                        # 不足以判断 foot_id，继续读
                        break

                    foot_id = self.raw_buffer[1]
                    if foot_id not in (0x01, 0x02):
                        # 第二字节不合规，滑动一字节重找帧头
                        self.raw_buffer.pop(0)
                        continue

                    # 2) 尝试两种长度（优先 39，再 38）
                    frame = None
                    frame_len = None
                    for L in FRAME_LEN_CANDIDATES:
                        if len(self.raw_buffer) >= L:
                            frame = bytes(self.raw_buffer[:L])
                            frame_len = L
                            # 这里可做校验位/保留位的合法性判断（若有文档），目前跳过
                            del self.raw_buffer[:L]
                            break

                    if frame is None:
                        # 数据还不够一帧，跳出内层等待下一批字节
                        break

                    # 3) 解析内容：18 × uint16（小端）
                    data_bytes = frame[2:2 + SENSOR_POINTS * 2]
                    if len(data_bytes) < SENSOR_POINTS * 2:
                        # 长度异常，跳过
                        continue
                    values = list(struct.unpack("<" + "H" * SENSOR_POINTS, data_bytes))
                    #print(f"[DEBUG][{'左' if self.is_left else '右'}] 解析值: {values[:17]}...")  # 调试输出
                    # 4) 判定左右脚
                    #    以帧内 foot_id 为准；若你的硬件 foot_id 不稳定，也可用 is_left 兜底。
                    side = "left" if foot_id == 0x01 else "right"
                    # 兜底（可选）：若明确本对象就是左/右足，可强制覆盖
                    if self.is_left and side != "left":
                        side = "left"
                    if (not self.is_left) and side != "right":
                        side = "right"

                    # 5) 输出：callback 或写入 self.data
                    with self.lock:
                            self.data = values
                            self.frame_id = getattr(self, "frame_id", 0) + 1
                            ts = time.time()
                            self.latest_packet={"side":side,"values":values,"ts":ts,"frame_id":self.frame_id}
                            self.foot_data_ready.emit(self.latest_packet)
                    if callback is not None:
                        try:
                            callback(side, values, ts)
                        except TypeError:
                            # 兼容旧签名 callback(side, values)
                            callback(side, values)   
                # 小憩，避免抢占 CPU，且让串口缓冲再积点数据
                time.sleep(0.002)

            except Exception as e:
                # 串口超时 / 读写异常都不中断采集，稍作等待重试
                print(f"[FootSensor] 读取异常: {e}")
                time.sleep(0.05)
                continue

        # 退出循环（running 被清掉）
        # 这里不强制关串口，交给 stop() 统一处理
        return
