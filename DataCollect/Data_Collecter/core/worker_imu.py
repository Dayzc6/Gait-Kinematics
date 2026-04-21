# 【IMU 进程】高频解析串口，刷新共享内存
import multiprocessing



IMU_DICT = {
    0x09: "Trunk",    0x0A: "L_Femur", 0x0B: "L_Tibia", 0x0C: "L_Foot",
    0x0D: "R_Femur",  0x0E: "R_Tibia", 0x0F: "R_Foot"
}
IMU_NAMES = list(IMU_DICT.values())

class IMU_Thread(Thread):
    def __init__(self, port, baudrate, timeout):
        super().__init__()
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.is_running = True
        self.ser = None
        self.data_lock = Lock()
        
        self.imu_data = {
            name: {
                "Acc": {"X": 0.0, "Y": 0.0, "Z": 0.0},
                "Gyro": {"X": 0.0, "Y": 0.0, "Z": 0.0},
                "Euler": {"Roll": 0.0, "Pitch": 0.0, "Yaw": 0.0},
                "Quat": {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0}
            } for name in IMU_NAMES
        }
        
    def to_signed_short(self, raw):
        return raw if raw <= 0x7FFF else raw - 0x10000

    def parse_frame(self, frame):
        dev_id = frame[0]
        flag = frame[2]
        
        if dev_id in IMU_DICT and flag == 0x61:
            name = IMU_DICT[dev_id]
            ax, ay, az = self.to_signed_short((frame[4]<<8)|frame[3]), self.to_signed_short((frame[6]<<8)|frame[5]), self.to_signed_short((frame[8]<<8)|frame[7])
            gx, gy, gz = self.to_signed_short((frame[10]<<8)|frame[9]), self.to_signed_short((frame[12]<<8)|frame[11]), self.to_signed_short((frame[14]<<8)|frame[13])
            r, p, y = self.to_signed_short((frame[22]<<8)|frame[21]), self.to_signed_short((frame[24]<<8)|frame[23]), self.to_signed_short((frame[26]<<8)|frame[25])

            roll_deg = round((r / 32768) * 180, 4)
            pitch_deg = round((p / 32768) * 180, 4)
            yaw_deg = round((y / 32768) * 180, 4)

            rot = R.from_euler('zyx', [yaw_deg, pitch_deg, roll_deg], degrees=True)
            quat = rot.as_quat()
            quat = quat / np.linalg.norm(quat)

            with self.data_lock:
                self.imu_data[name]["Acc"] = {"X": round((ax/32768)*16*9.8, 4), "Y": round((ay/32768)*16*9.8, 4), "Z": round((az/32768)*16*9.8, 4)}
                self.imu_data[name]["Gyro"] = {"X": round((gx/32768)*2000, 4), "Y": round((gy/32768)*2000, 4), "Z": round((gz/32768)*2000, 4)}
                self.imu_data[name]["Euler"] = {"Roll": roll_deg, "Pitch": pitch_deg, "Yaw": yaw_deg}
                self.imu_data[name]["Quat"] = {"x": round(quat[0], 4), "y": round(quat[1], 4), "z": round(quat[2], 4), "w": round(quat[3], 4)}

    def get_latest_data(self):
        with self.data_lock:
            return self.imu_data.copy()

    def run(self):
        try:
            self.ser = serial.Serial(self.port, self.baudrate, timeout=self.timeout)
            self.ser.set_buffer_size(rx_size=10240) 
            print(f'✅ IMU 串口已打开: {self.port}')
        except Exception as e:
            print(f'❌ IMU 串口打开失败: {e}')
            return

        raw_buffer = b""
        try:
            while self.is_running:
                if self.ser.in_waiting > 0:
                    raw_buffer += self.ser.read(self.ser.in_waiting)
                    if len(raw_buffer) > 5000:
                        raw_buffer = raw_buffer[-1000:]

                    while True:
                        head_idx = raw_buffer.find(FRAME_HEAD)
                        if head_idx == -1: break
                        if head_idx > 0:
                            start_idx = head_idx - 1
                            end_idx = start_idx + FRAME_TOTAL_LEN
                            if end_idx <= len(raw_buffer):
                                frame = raw_buffer[start_idx:end_idx]
                                if frame[1] == 0x55: 
                                    self.parse_frame(frame)
                                raw_buffer = raw_buffer[end_idx:]
                                continue
                            else: break
                        else: raw_buffer = raw_buffer[1:]
                time.sleep(0.001)
        finally:
            if self.ser and self.ser.is_open:
                self.ser.close()

    def stop(self):
        self.is_running = False