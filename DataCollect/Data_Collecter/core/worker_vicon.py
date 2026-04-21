# 【Vicon 进程】持续 Pull SDK，刷新共享内存
import time
import vicon_dssdk.ViconDataStream as VDS
from DataCollect.Data_Collecter.config import VICON_HOST_IP

class Vicon_Thread(Thread):
    def __init__(self, host_ip, seg_ids, marker_ids):
        super().__init__()
        self.host_ip = host_ip
        self.seg_ids = seg_ids
        self.marker_ids = marker_ids
        self.seg_data = {seg: {"X": 0.0, "Y": 0.0, "Z": 0.0} for seg in self.seg_ids}
        self.marker_data = {marker: {"X":0.0, "Y":0.0, "Z":0.0} for marker in self.marker_ids}
        self.current_frame_num = 0
        self.data_lock = Lock()
        self.is_running = True
        
        self.client = VDS.Client()
        self.client.Connect(host_ip)
        self.client.EnableSegmentData()
        self.client.EnableMarkerData()
        
        if self.client.IsConnected():
            print('Vicon 连接成功')
        try:
            self.client.SetStreamMode(0)
        except:
            pass

    def get_latest_data(self):
        with self.data_lock:
            return self.current_frame_num, self.seg_data.copy(), self.marker_data.copy()

    def run(self):
        try:
            while self.is_running:
                if self.client.GetFrame():
                    frame_num = self.client.GetFrameNumber()
                    subjects = self.client.GetSubjectNames()
                    if subjects:
                        subject_name = subjects[0]
                        temp_seg_data = {}
                        temp_marker_data={}

                        for seg in self.seg_ids:
                            pos,occluded = self.client.GetSegmentGlobalTranslation(subject_name, seg)
                            if not occluded:
                                temp_seg_data[seg]={"X": pos[0], "Y": pos[1], "Z": pos[2]}
                            else:
                                temp_seg_data[seg] = self.seg_data[seg]
                        
                        for marker in self.marker_ids:
                            pos,occluded = self.client.GetMarkerGlobalTranslation(subject_name,marker)
                            if not occluded:
                                temp_marker_data[marker]={"X": pos[0], "Y": pos[1], "Z": pos[2]}
                            else:
                                temp_marker_data[marker]=self.marker_data[marker]

                        with self.data_lock:
                            self.current_frame_num = frame_num
                            self.seg_data.update(temp_seg_data)
                            self.marker_data.update(temp_marker_data)

                time.sleep(0.001) # Vicon 线程极速轮询
        finally:
            self.client.Disconnect()

    def stop(self):
        self.is_running = False