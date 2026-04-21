# 全局入口：初始化共享内存，启动所有进程，响应键盘开关
import core
import utils
import socket
from DataCollect.Data_Collecter.config import VICON_HOST_IP, VICON_SEGS, VICON_MARKERS, \
                    IMU_BAUDRATE, IMU_PORT, IMU_TIMEOUT, IMU_NAMES, \
                    
class MainApp:
    def __init__(self):
        # 1. 启动硬件监听线程（一直在后台跑，更新最新数据）
        self.vicon_thread = core.worker_vicon.Vicon_Thread(VICON_HOST_IP, VICON_SEGS, VICON_MARKERS)
        self.imu_thread = core.worker_imu.IMU_Thread(IMU_PORT, IMU_BAUDRATE, IMU_TIMEOUT)
        self.vicon_thread.start()
        self.imu_thread.start()

        # 2. 状态控制
        self.is_recording = False
        self.record_thread = None
        self.csv_writer = None

        # 3. 创建 GUI
        self.root = tk.Tk()
        self.root.title("Vicon+IMU 同步采集系统")
        self.root.geometry("300x150")

        self.status_label = tk.Label(self.root, text="状态: 待机中 (硬件已连接)", font=("Arial", 12), fg="blue")
        self.status_label.pack(pady=15)

        self.btn_start = tk.Button(self.root, text="▶ 开始记录", command=self.start_record, bg="green", fg="white", font=("Arial", 12, "bold"))
        self.btn_start.pack(side=tk.LEFT, padx=20)

        self.btn_stop = tk.Button(self.root, text="⏹ 停止记录", command=self.stop_record, bg="red", fg="white", font=("Arial", 12, "bold"), state=tk.DISABLED)
        self.btn_stop.pack(side=tk.RIGHT, padx=20)

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def start_record(self):
        self.is_recording = True
        self.btn_start.config(state=tk.DISABLED)
        self.btn_stop.config(state=tk.NORMAL)
        self.status_label.config(text="状态: 正在同步记录数据 (100Hz)...", fg="green")
        
        # 实例化 CSV 写入器，开始新文件
        self.csv_writer = core.data_writer.CSV_Writer(VICON_SEGS, VICON_MARKERS, IMU_NAMES)
        
        # 🚀【终极武器：UDP 遥控 Vicon 开始录制】
        try:
            udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            # 自动从 "192.168.137.33" 中提取纯 IP "192.168.137.33"
            vicon_ip = VICON_HOST_IP.split(':')[0] 
            
            # 去掉后缀，只保留纯文件名 (如 subject_trial_20260409)
            file_name_only = self.csv_writer.filename.replace('.csv', '')
            
            # 严格遵循 Vicon 官方的 XML 格式，且末尾必须加 \0 (Null terminated)
            start_xml = f'<CaptureStart><Name VALUE="{file_name_only}"/></CaptureStart>\0'
            
            # 向 Vicon 默认的 30 端口发送开机指令
            udp_sock.sendto(start_xml.encode('utf-8'), (vicon_ip, 30))
            print(f"✅ 已发送遥控指令：Vicon 将保存文件名为 [{file_name_only}]")
        except Exception as e:
            print(f"❌ 遥控 Vicon 失败: {e}")

        # 启动高精度定时拉取线程
        self.record_thread = Thread(target=self.precise_recording_loop)
        self.record_thread.start()

    def stop_record(self):
        self.is_recording = False
        if self.record_thread:
            self.record_thread.join()
            
        # 🚀【终极武器：UDP 遥控 Vicon 停止录制】
        try:
            udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            vicon_ip = VICON_HOST_IP.split(':')[0] 
            # 发送停止指令，同样以 \0 结尾
            stop_xml = '<CaptureStop></CaptureStop>\0'
            udp_sock.sendto(stop_xml.encode('utf-8'), (vicon_ip, 30))
            print("✅ 已发送遥控指令：命令 Vicon 停止 Capture！")
        except Exception as e:
            print(f"❌ 遥控 Vicon 失败: {e}")
        
        self.btn_start.config(state=tk.NORMAL)
        self.btn_stop.config(state=tk.DISABLED)
        self.status_label.config(text="状态: 记录已保存，待机中", fg="blue")
        print("✅ 数据已安全保存。")

    def precise_recording_loop(self):
        # 目标采集间隔 (5ms = 200Hz | 10ms = 100Hz)
        interval = 0.01 
        next_time = time.perf_counter()

        while self.is_recording:
            # 1. 抓取瞬时数据
            v_frame, v_seg_data, v_marker_data = self.vicon_thread.get_latest_data()
            i_data = self.imu_thread.get_latest_data()
            current_timestamp = time.time() # 记录绝对物理时间

            # 2. 写入数据
            self.csv_writer.append_row(current_timestamp, v_frame, v_seg_data, v_marker_data, i_data)

            # 3. 高精度对齐 (微秒级等待，补齐 5ms | 10ms)
            next_time += interval
            sleep_time = next_time - time.perf_counter()
            if sleep_time > 0:
                # 留出 1ms 给系统级 sleep，剩下极小时间用空循环自旋以确保极高精度
                if sleep_time > 0.001:
                    time.sleep(sleep_time - 0.001)
                while time.perf_counter() < next_time:
                    pass 

    def on_close(self):
        print("🛑 正在关闭所有硬件连接...")
        self.is_recording = False
        self.vicon_thread.stop()
        self.imu_thread.stop()
        self.vicon_thread.join()
        self.imu_thread.join()
        self.root.destroy()
        print("✅ 系统已完全退出。")

if __name__ == '__main__':
    app = MainApp()
    app.root.mainloop()
