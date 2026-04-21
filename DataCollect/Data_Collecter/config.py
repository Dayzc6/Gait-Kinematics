# 静态配置：串口号、IP、采样率、CSV 表头定义
import time
import csv
import vicon_dssdk.ViconDataStream as VDS

# IMU配置
IMU_PORT = 'COM12'                      # IMU接收串口      
IMU_BAUDRATE = 460800                  
IMU_TIMEOUT = 0.1
IMU_FRAME_HEAD = b'\x55'               
IMU_FRAME_TOTAL_LEN = 29               

IMU_DICT = {
    0x09: "Trunk",    0x0A: "L_Femur", 0x0B: "L_Tibia", 0x0C: "L_Foot",
    0x0D: "R_Femur",  0x0E: "R_Tibia", 0x0F: "R_Foot"
}
IMU_NAMES = list(IMU_DICT.values())

# Planter配置
PLANTER_SENSOR_POINTS = 18
PLANTER_BAUD_RATE=115200
PLANTER_PORT='COM11'


# Vicon配置
VICON_HOST_IP = "192.168.137.157"   # Vicon主机IP

# 获取各个传感器的表头
def get_vicon_segs():
    
    temp_client=VDS.Client()
    print("Connect...")
    temp_client.Connect(VICON_HOST_IP)
    print(f"Connect: {temp_client.IsConnected()}")
    temp_client.EnableSegmentData()

    try:
        temp_client.SetStreamMode(0)
    except:
        pass
    
    segs=[]
    for _ in range(10):
        if temp_client.GetFrame():
            subjects=temp_client.GetSubjectNames()
            if subjects:
                s_name=subjects[0]
                print(s_name)
                segs=temp_client.GetSegmentNames(s_name)
                seg_1=segs[1]
                
                pos, occluded = temp_client.GetSegmentGlobalTranslation(s_name,seg_1)
                print(f"{seg_1}")
                print((pos, occluded))
                
                if not occluded:
                    print(f"{seg_1}: X:{pos[0]:.2f}, Y: {pos[1]:.2f}, Z: {pos[2]:.2f}")
                
        time.sleep(0.1)

    temp_client.Disconnect()
    print("segs: ", segs)
    return segs
VICON_SEGS=get_vicon_segs()

def get_vicon_markers():
    temp_client = VDS.Client()
    temp_client.Connect(VICON_HOST_IP)
    temp_client.EnableMarkerData()

    try:
        temp_client.SetStreamMode(0)
    except:
        pass

    markers = []
    for _ in range(10):
        if temp_client.GetFrame():
            subjects = temp_client.GetSubjectNames()
            if subjects:
                s_name = subjects[0]
                raw_markers = temp_client.GetMarkerNames(s_name)
            
                temp_markers = []
                # 情况 A: 如果返回的是 (Result, [markers_list])
                if isinstance(raw_markers, tuple) and len(raw_markers) == 2 and isinstance(raw_markers[1], list):
                    raw_list = raw_markers[1]
                else:
                    raw_list = raw_markers

                # 情况 B: 如果列表里包含的是元组，如 [('Marker1', 'Parent'), ...]
                for m in raw_list:
                    if isinstance(m, tuple) or isinstance(m, list):
                        temp_markers.append(m[0]) # 提取真正的 marker 名字
                    else:
                        temp_markers.append(m)    # 本身就是纯字符串
                
                markers = temp_markers
                
                if markers:
                    marker_1 = markers[0]
                    pos, occluded = temp_client.GetMarkerGlobalTranslation(s_name, marker_1)
                    print(f"{marker_1}")
                    print((pos, occluded))
                    
                    if not occluded:
                        print(f"{marker_1}: X:{pos[0]:.2f}, Y: {pos[1]:.2f}, Z: {pos[2]:.2f}")
                
        time.sleep(0.1)

    temp_client.Disconnect()
    print("markers: ", markers)
    return markers
VICON_MARKERS=get_vicon_markers()

PLANTER=['Planter_Left','Planter_Right']

# 创建csv文件以及表头
class CSV_Writer:
    def __init__(self, vicon_segs, vicon_markers, imu_names):    
        current_time = time.strftime("%Y%m%d_%H%M%S")
        self.filename = f"subject_trial_{current_time}.csv"
        
        self.headers = ['Timestamp', 'Vicon_Frame_Num']
        for seg in vicon_segs:
            self.headers.extend([f"Vicon_{seg}_X", f"Vicon_{seg}_Y", f"Vicon_{seg}_Z"])

        for marker in vicon_markers:
            self.headers.extend([f"Vicon_{marker}_X",f"Vicon_{marker}_Y",f"Vicon_{marker}_Z"])

        for name in imu_names:
            self.headers.extend([f"IMU_{name}_Acc_X", f"IMU_{name}_Acc_Y", f"IMU_{name}_Acc_Z"])
            self.headers.extend([f"IMU_{name}_Gyro_X", f"IMU_{name}_Gyro_Y", f"IMU_{name}_Gyro_Z"])
            self.headers.extend([f"IMU_{name}_Roll", f"IMU_{name}_Pitch", f"IMU_{name}_Yaw"])
            self.headers.extend([f"IMU_{name}_Quat_x", f"IMU_{name}_Quat_y", f"IMU_{name}_Quat_z", f"IMU_{name}_Quat_w"])

        with open(self.filename, mode='w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(self.headers)
        print(f'✅CSV 文件已创建: {self.filename}')

    def append_row(self, current_time, vicon_frame, vicon_seg_data, vicon_marker_data, imu_data):
        row_data = [current_time, vicon_frame]

        for seg in VICON_SEGS:
            coords = vicon_seg_data.get(seg, {"X": 0.0, "Y": 0.0, "Z": 0.0})
            row_data.extend([coords['X'], coords['Y'], coords['Z']])

        for marker in VICON_MARKERS:
            coords = vicon_marker_data.get(marker, {"X": 0.0, "Y": 0.0, "Z": 0.0})
            row_data.extend([coords['X'], coords['Y'], coords['Z']])            

        for imu in IMU_NAMES:
            d = imu_data[imu]
            row_data.extend([
                d["Acc"]["X"], d["Acc"]["Y"], d["Acc"]["Z"],
                d["Gyro"]["X"], d["Gyro"]["Y"], d["Gyro"]["Z"],
                d["Euler"]["Roll"], d["Euler"]["Pitch"], d["Euler"]["Yaw"],
                d["Quat"]["x"], d["Quat"]["y"], d["Quat"]["z"], d["Quat"]["w"]
            ])

        with open(self.filename, mode='a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(row_data)

if __name__=="__main__":
    CSV_Writer.__init__()
