# 专门存放 IMU 的 0x55 协议解析函数
from config import IMU_DICT,IMU_NAMES,IMU_FRAME_HEAD,\
    IMU_FRAME_TOTAL_LEN, IMU_PORT, IMU_TIMEOUT, IMU_BAUDRATE
from scipy.spatial.transform import Rotation as R
import numpy as np

def to_signed_short(raw):
    return raw if raw <= 0x7FFF else raw - 0x10000

def parse_frame(frame):
    dev_id = frame[0]
    flag = frame[2]
        
    # if dev_id in IMU_DICT and flag == 0x61:
    if flag == 0x61:
        # name = IMU_DICT[dev_id]
        ax, ay, az = to_signed_short((frame[4]<<8)|frame[3]), to_signed_short((frame[6]<<8)|frame[5]), to_signed_short((frame[8]<<8)|frame[7])
        gx, gy, gz = to_signed_short((frame[10]<<8)|frame[9]), to_signed_short((frame[12]<<8)|frame[11]), to_signed_short((frame[14]<<8)|frame[13])
        r, p, y = to_signed_short((frame[22]<<8)|frame[21]), to_signed_short((frame[24]<<8)|frame[23]), to_signed_short((frame[26]<<8)|frame[25])

        roll_deg = round((r / 32768) * 180, 4)
        pitch_deg = round((p / 32768) * 180, 4)
        yaw_deg = round((y / 32768) * 180, 4)

        rot = R.from_euler('zyx', [yaw_deg, pitch_deg, roll_deg], degrees=True)
        quat = rot.as_quat()
        quat = quat / np.linalg.norm(quat)

    """    
    with data_lock:
            imu_data[name]["Acc"] = {"X": round((ax/32768)*16*9.8, 4), "Y": round((ay/32768)*16*9.8, 4), "Z": round((az/32768)*16*9.8, 4)}
            imu_data[name]["Gyro"] = {"X": round((gx/32768)*2000, 4), "Y": round((gy/32768)*2000, 4), "Z": round((gz/32768)*2000, 4)}
            imu_data[name]["Euler"] = {"Roll": roll_deg, "Pitch": pitch_deg, "Yaw": yaw_deg}
            imu_data[name]["Quat"] = {"x": round(quat[0], 4), "y": round(quat[1], 4), "z": round(quat[2], 4), "w": round(quat[3], 4)}
    """

    return dev_id, {
        "Acc": {"X": round((ax/32768)*16*9.8, 4), "Y": round((ay/32768)*16*9.8, 4), "Z": round((az/32768)*16*9.8, 4)},
        "Gyro": {"X": round((gx/32768)*2000, 4), "Y": round((gy/32768)*2000, 4), "Z": round((gz/32768)*2000, 4)},
        "Euler": {"Roll": roll_deg, "Pitch": pitch_deg, "Yaw": yaw_deg},
        "Quat": {"x": round(quat[0], 4), "y": round(quat[1], 4), "z": round(quat[2], 4), "w": round(quat[3], 4)}
        }


"""
def run(self):
    try:
        self.ser = serial.Serial(self.port, self.baudrate, timeout=self.timeout)
        self.ser.set_buffer_size(rx_size=10240) 

    except Exception as e:

        return

    raw_buffer = b""
    try:
        while self.is_running:
            if self.ser.in_waiting > 0:
                raw_buffer += self.ser.read(self.ser.in_waiting)
                if len(raw_buffer) > 5000:
                    raw_buffer = raw_buffer[-1000:]

                while True:
                    head_idx = raw_buffer.find(IMU_FRAME_HEAD)
                    if head_idx == -1: break
                    if head_idx > 0:
                        start_idx = head_idx - 1
                        end_idx = start_idx + IMU_FRAME_TOTAL_LEN
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

"""
