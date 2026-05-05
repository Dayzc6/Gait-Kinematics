import csv
import os
from collections import deque
from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtCore import QThread, pyqtSignal, QTimer
import BlueTeethIMU
import data_pre
from ui import Ui_MainWindow
from button import connect_button_actions
import draw_pic
import datetime
import time
import pyqtgraph as pg
import numpy as np
from collections import deque
from scipy.signal import butter, filtfilt
from two_plant_2 import FootSensor
import threading
import traceback
class MainWindow(QtWidgets.QMainWindow, Ui_MainWindow):
    def __init__(self, parent=None):
        super(MainWindow, self).__init__(parent)
        # 设置窗口图标
        # 获取当前脚本所在目录
        base_dir = os.path.dirname(os.path.abspath(__file__))
        # 构建图标路径
        icon_path = os.path.join(base_dir, 'images', 'logo_transpar.ico')
        self.setWindowIcon(QtGui.QIcon(icon_path))
        # 界面初始化
        self.setupUi(self)
        # 设置窗口标题为"下肢步态评估系统"
        self.setWindowTitle("下肢步态评估系统")
        # ==== 新增：初始化保存路径 ====
        # 获取当前程序所在目录
        self.default_save_path = os.path.abspath(os.path.dirname(__file__))
        # 设置初始保存路径为程序所在目录
        self.lineEdit_save_path.setText(self.default_save_path)
        # 连接选择路径按钮信号
        self.pushButton_select_path.clicked.connect(self.select_save_path)
        # 添加按钮函数(与线程无关的)
        connect_button_actions(self)
        #足底压力显示函数
        self.pushButton_begin_read2.clicked.connect(self.on_show_left_clicked)
        self.pushButton_begin_read3.clicked.connect(self.on_show_right_clicked)
        self.pushButton_end_read2.clicked.connect(self.end_read_thread_action_left) 
        self.pushButton_end_read3.clicked.connect(self.end_read_thread_action_right)    
        # ==== 提前定义 upperbody_angle ====
        self.upperbody_angle = 0.0
        # 定义线程相关变量
        self.serial_port = None
        self.serial_port2 = None
        self.serial_port3= None
        self.imu_thread = None
        self.start_time = time.perf_counter()
        self.now_time = time.perf_counter()
        self.time_count = 0
        self.pushButton_begin_read.clicked.connect(self.begin_read_thread_action)
        self.pushButton_end_read.clicked.connect(self.end_read_thread_action)
        # --- 足底压力线程与共享缓冲区 ---
        self._plantar_lock = threading.Lock()
        self.plantar_left_latest  = [0]*18
        self.plantar_right_latest = [0]*18
        self._plantar_left_ts  = 0.0
        self._plantar_right_ts = 0.0
        # 足底事件队列：左右合并，逐帧入队，record_data 排空写盘
        self._plantar_q = deque(maxlen=5000)
        self._plantar_q_lock = threading.Lock()
        self._writer_running = False
        # 缓存 QLabel 列表，避免每次 getattr
        self._labels_left  = [getattr(self, f"label_left{i}")  for i in range(1, 19)]
        self._labels_right = [getattr(self, f"label_right{i}") for i in range(1, 19)]

        # 保护上面两个数组的锁
        self.foot_lock = threading.Lock()
        # 大腿长范围：0.01-2米
        self.doubleSpinBox_thigh_length_data.setMinimum(0.01)
        self.doubleSpinBox_thigh_length_data.setMaximum(2.0)
        self.doubleSpinBox_thigh_length_data.setDecimals(2)  # 3位小数

        # 小腿长范围：0.01-2米
        self.doubleSpinBox_shank_length_data.setMinimum(0.01)
        self.doubleSpinBox_shank_length_data.setMaximum(2.0)
        self.doubleSpinBox_shank_length_data.setDecimals(2)  # 3位小数

        #步宽范围
        self.doubleSpinBox_leg_width.setMinimum(0.01)
        self.doubleSpinBox_leg_width.setMaximum(2.0)
        self.doubleSpinBox_leg_width.setDecimals(2)
        # ==== 新增：连接标定按钮信号 ====
        self.pushButton_standard.clicked.connect(self.calibration_action)

        # 定义标签更新相关变量
        self.comp_data = [0.0] * 7

        # 定义绘图相关变量
        self.points = []
        self.scene, self.graphicsView, self.timer = draw_pic.init_graphics_view(self)
        # 在__init__中初始化时使用固定长度的deque
        max_points = 1000  # 限制每个关节最多存储1000个数据点
        self.joint_time_data = [deque(maxlen=max_points) for _ in range(6)]
        self.joint_angle_data = [deque(maxlen=max_points) for _ in range(6)]
        # ==== 为graphicsView_2初始化关节角度实时曲线图 ====
        self.joint_curves, self.joint_time_data, self.joint_angle_data, self.joint_timer = draw_pic.init_joint_angle_plot(
            self)

        # 配置定时器更新曲线
        self.joint_timer.timeout.connect(self.update_joint_angle_plot)
        self.joint_timer.start(100)  # 10Hz更新频率
        # ==== 关键添加：在初始化后立即调用适应窗口大小的函数 ====

        # ==== 新增：设备号到关节索引的映射 ====
        self.device_to_joint = {
            3: 0,  # 左髋角度
            4: 1,  # 左膝角度
            5: 2,  # 左踝角度
            6: 3,  # 右髋角度
            7: 4,  # 右膝角度
            8: 5  # 右踝角度
        }

        # 在 __init__ 方法中添加设备名称映射
        self.device_names = {
            2: "背部IMU模块",
            3: "左大腿IMU模块",
            4: "左小腿IMU模块",
            5: "左脚IMU模块",
            6: "右大腿IMU模块",
            7: "右小腿IMU模块",
            8: "右脚IMU模块"
        }
        # 定义数据记录相关变量(决定频率)
        self.refresh = 10
        # 创建定时器
        self.timer_record = QTimer()
        self.timer_record.setTimerType(QtCore.Qt.PreciseTimer)
        # 将定时器的超时信号连接到更新标签的槽函数
        self.timer_record.timeout.connect(self.record_data)

        self.csv_file = None
        self.csv_writer = None
        self.filename = ''
        self.fieldnames = ['时间',
                           '上身角度', '左髋角度', '左膝角度', '左踝角度', '右髋角度', '右膝角度', '右踝角度',
                           'imu1ang_x', 'imu1vel_x', 'imu1acc_x',
                           'imu1ang_y', 'imu1vel_y', 'imu1acc_y',
                           'imu1ang_z', 'imu1vel_z', 'imu1acc_z',
                           'imu2ang_x', 'imu2vel_x', 'imu2acc_x',
                           'imu2ang_y', 'imu2vel_y', 'imu2acc_y',
                           'imu2ang_z', 'imu2vel_z', 'imu2acc_z',
                           'imu3ang_x', 'imu3vel_x', 'imu3acc_x',
                           'imu3ang_y', 'imu3vel_y', 'imu3acc_y',
                           'imu3ang_z', 'imu3vel_z', 'imu3acc_z',
                           'imu4ang_x', 'imu4vel_x', 'imu4acc_x',
                           'imu4ang_y', 'imu4vel_y', 'imu4acc_y',
                           'imu4ang_z', 'imu4vel_z', 'imu4acc_z',
                           'imu5ang_x', 'imu5vel_x', 'imu5acc_x',
                           'imu5ang_y', 'imu5vel_y', 'imu5acc_y',
                           'imu5ang_z', 'imu5vel_z', 'imu5acc_z',
                           'imu6ang_x', 'imu6vel_x', 'imu6acc_x',
                           'imu6ang_y', 'imu6vel_y', 'imu6acc_y',
                           'imu6ang_z', 'imu6vel_z', 'imu6acc_z',
                           'imu7ang_x', 'imu7vel_x', 'imu7acc_x',
                           'imu7ang_y', 'imu7vel_y', 'imu7acc_y',
                           'imu7ang_z', 'imu7vel_z', 'imu7acc_z'
                           ]
        #加上足底压力数据
        self.fieldnames += [f'L_{i+1}' for i in range(18)] + [f'R_{i+1}' for i in range(18)]
        self.fieldnames += ['frame_id_left','frame_id_right']
        self.data_save = [0.0] * (71+38)  # 71个IMU数据+时间+7个关节角度+36个足底压力
        self.gait_parameters = [0.0] * 20

        self.mapping1 = {'battery': 0, 'x': 1, 'y': 2, 'z': 3}
        self.mapping2 = {'bat': 0, 'ang': 1, 'vel': 2, 'acc': 3}
        self.pushButton_begin_record.clicked.connect(self.begin_record)
        self.pushButton_end_record.clicked.connect(self.stop_record_save)

        # ==== 新增部分：设备状态管理 ====
        # 设备状态字典：device_id (2-8) -> 最后接收时间
        self.device_last_seen = {i: 0 for i in range(2, 9)}
        # 初始化时所有设备都标记为未连接
        self.device_status = {i: "disconnected" for i in range(2, 9)}
        # 电池数据平滑处理：每个设备的电池值队列
        self.battery_history = {i: deque(maxlen=10000) for i in range(2, 9)}  # 保留最近值

        # 设备当前电池值（原始值，用于实时警告）
        self.current_battery = {i: 0 for i in range(2, 9)}
        self.last_displayed_battery = {i: 0 for i in range(2, 9)}  # 记录上次显示的电量值
        # 设备状态样式表
        self.status_styles = {
            "connected": "background-color: rgb(0, 255, 0);",  # 绿色
            "disconnected": "background-color: rgb(200, 200, 200);",  # 灰色
            "low_battery": "background-color: rgb(255, 0, 0);"  # 红色
        }

        # 状态检查定时器
        self.status_timer = QTimer()
        #self.status_timer.timeout.connect(self.check_device_status)
        #self.status_timer.start(1000)  # 每秒检查一次
        # 新建子线程绘图
        self.plot_worker = PlotWorker(self.joint_time_data,
                                      self.joint_angle_data,
                                      parent=self)
        # 信号槽连接：子线程 -> 主线程
        self.plot_worker.plot_data_ready.connect(self.refresh_curves_slot)
        self.plot_worker.start()

        # ==== 新增：标定相关变量 ====
        self.calibration_samples = {i: [] for i in range(2, 9)}  # 每个设备的标定样本
        self.calibration_data_timer = None  # 标定数据采集定时器
        self.calibration_end_timer = None  # 标定结束定时器
        # —— 收集左右 18 个 QLabel 引用（如果某个名字没放在UI里，会给出警告）——
        self.labels_left  = []
        self.labels_right = []
        for i in range(1, 19):
            labL = self.findChild(QtWidgets.QLabel, f"label_left{i}")
            labR = self.findChild(QtWidgets.QLabel, f"label_right{i}")
            if labL is None:
                print(f"[UI] 警告：未找到 QLabel: label_left{i}")
                # 用一个占位的 QLabel，避免后续 setText 报错
                labL = QtWidgets.QLabel(self)
            if labR is None:
                print(f"[UI] 警告：未找到 QLabel: label_right{i}")
                labR = QtWidgets.QLabel(self)
            # 初始样式（可选）
            labL.setAlignment(QtCore.Qt.AlignCenter)
            labR.setAlignment(QtCore.Qt.AlignCenter)
            self.labels_left.append(labL)
            self.labels_right.append(labR)

    def select_save_path(self):
        """选择数据保存路径"""
        # 弹出文件夹选择对话框
        selected_path = QtWidgets.QFileDialog.getExistingDirectory(
            self,
            "选择数据保存路径",
            self.lineEdit_save_path.text(),
            QtWidgets.QFileDialog.ShowDirsOnly
        )

        if selected_path:  # 确保用户选择了路径而不是取消
            self.lineEdit_save_path.setText(selected_path)
# ==== 新增：足底压力线程相关方法 ====
# ==== 新增：左脚线程读取函数 ====
    # 其他原有方法保持不变...
    def calibration_action(self):
        """标定按钮点击事件处理"""
        # 检查是否已经开始读取数据
        if self.imu_thread is None or not self.imu_thread.isRunning():
            QtWidgets.QMessageBox.warning(
                self,
                "无法标定",
                "请先开始读取IMU数据！\n\n操作步骤：\n1. 点击'开始读取'\n"
                "2. 等待设备连接并开始接收数据\n3. 点击'标定'按钮"
            )
            return

        # 重置标定样本存储
        self.calibration_samples = {i: [] for i in range(2, 9)}

        # 创建"正在标定中"对话框
        self.calibration_dialog = QtWidgets.QDialog(self)
        self.calibration_dialog.setWindowTitle("标定中")
        self.calibration_dialog.setWindowFlags(
            QtCore.Qt.Window |
            QtCore.Qt.CustomizeWindowHint |
            QtCore.Qt.WindowTitleHint
        )

        # 添加标签
        layout = QtWidgets.QVBoxLayout()
        label = QtWidgets.QLabel("正在标定中，请保持姿势不动...\n（约3秒）")
        label.setAlignment(QtCore.Qt.AlignCenter)
        layout.addWidget(label)
        self.calibration_dialog.setLayout(layout)

        # 设置对话框大小
        self.calibration_dialog.resize(300, 100)

        # 启动数据采集定时器
        self.calibration_data_timer = QTimer()
        self.calibration_data_timer.timeout.connect(self.collect_calibration_data)
        self.calibration_data_timer.start(100)  # 每100ms采集一次数据

        # 设置3秒后结束标定
        self.calibration_end_timer = QTimer()
        self.calibration_end_timer.setSingleShot(True)
        self.calibration_end_timer.timeout.connect(self.finish_calibration)
        self.calibration_end_timer.start(3000)

        # 显示对话框
        self.calibration_dialog.exec_()

    def collect_calibration_data(self):
        """采集标定数据"""
        # 采集所有设备(2-8)的X轴角度数据
        for device_id in range(2, 9):
            label_name = f"label_origin_data_imu{device_id - 1}x_data"
            try:
                # 获取标签文本
                text = getattr(self, label_name).text()
                if text:  # 确保文本不为空
                    value = float(text)
                    self.calibration_samples[device_id].append(value)
            except (ValueError, AttributeError):
                # 处理可能的转换错误或属性不存在
                pass

    def finish_calibration(self):
        """完成标定并计算补偿值"""
        # 停止采集定时器
        if self.calibration_data_timer:
            self.calibration_data_timer.stop()

        # 关闭对话框
        if self.calibration_dialog:
            self.calibration_dialog.accept()
            self.calibration_dialog = None

        # 计算每个设备的补偿值
        for device_id, samples in self.calibration_samples.items():
            if samples:  # 确保有样本
                avg_value = sum(samples) / len(samples)
                # 存储补偿值（当前位置设为0度）
                self.comp_data[device_id - 2] = -avg_value

        # 显示完成提示
        QtWidgets.QMessageBox.information(
            self,
            "标定完成",
            "标定已完成",
            QtWidgets.QMessageBox.Ok
        )

        # 打印调试信息（可选）
        print("标定补偿值:")
        for i, val in enumerate(self.comp_data):
            print(f"设备 {i + 2}: {val:.3f}")

    def check_device_status(self):
        """检查设备连接状态，更新断开设备的状态"""
        current_time = time.time()
        for device_id in range(2, 9):  # 设备ID 2-8
            last_seen = self.device_last_seen.get(device_id, 0)

            # 如果超过10秒没有收到数据，认为设备已断开
            if current_time - last_seen > 10 and last_seen > 0:
                # 只有之前不是断开状态时才弹出提示
                if self.device_status[device_id] != "disconnected":
                    # 获取设备名称
                    device_name = self.device_names.get(device_id, f"IMU{device_id}")
                    # 弹出设备断开提示弹窗
                    QtWidgets.QMessageBox.warning(
                        self,
                        "设备连接中断",
                        f"{device_name}已断开连接！请检查设备供电和蓝牙连接。",
                        QtWidgets.QMessageBox.Ok
                    )

                # 更新设备状态
                self.update_device_status(device_id, "disconnected")

                # 清空历史电量数据并将电量显示置为0
                self.battery_history[device_id].clear()
                self.current_battery[device_id] = 0
                label_name = f"label_imu{device_id}_battery_data"
                getattr(self, label_name).setText("0")

    def update_device_status(self, device_id, status_type):
        """更新设备状态显示"""
        # 更新设备状态字典
        self.device_status[device_id] = status_type
        if status_type == "connected":
            status_text = "已连接"
            style = self.status_styles["connected"]
        elif status_type == "disconnected":
            status_text = "未连接"
            style = self.status_styles["disconnected"]
        else:  # low_battery
            status_text = "电量低"
            style = self.status_styles["low_battery"]

        # 更新状态文本
        label_name = f"label_imu{device_id}_status_text"
        getattr(self, label_name).setText(status_text)

        # 更新状态指示灯
        label_name = f"label_imu{device_id}_status_color"
        getattr(self, label_name).setStyleSheet(style)
    
    def begin_read_thread_action(self):
        """
        事件函数，打开数据读取的线程
        """

        # ==== 新增：串口状态检查 ====
        if self.serial_port is None:
            QtWidgets.QMessageBox.warning(
                self,
                "设备未连接",
                "请先搜索并打开蓝牙串口！\n\n操作步骤：\n1. 点击'搜索串口'\n"
                "2. 选择正确的COM端口\n3. 点击'打开'"
            )
            return
        self.imu_thread = imuThread(self.serial_port)
        self.imu_thread.update_label.connect(self.update_label_origin_angle_data)

        # 在开始线程时重置所有设备状态
        for device_id in range(2, 9):
            self.device_status[device_id] = "disconnected"  # 重置状态
            self.update_device_status(device_id, "disconnected")
            self.battery_history[device_id].clear()  # 清空历史电量数据
            self.current_battery[device_id] = 0  # 重置当前电池值

        self.imu_thread.start()
        # ==== 新增：启动状态检查定时器 ====
        self.pushButton_begin_read.setEnabled(False)
        self.pushButton_imu_close.setEnabled(False)
        self.pushButton_end_read.setEnabled(True)
    # 其他方法保持不变...
    def end_read_thread_action(self):
        """
        事件函数，关闭数据读取的线程
        """
        # 停止IMU线程
        self.imu_thread.stop()

        # ==== 新增：重置计时器 ====
        self.start_time = time.perf_counter()  # 重置计时起点
        self.label_current_time_data.setText("0.0")  # 重置UI显示为0
        self.data_save[0] = 0.0  # 重置数据保存位置的时间值
        # 清空绘图数据
        if hasattr(self, 'joint_time_data'):
            for data in self.joint_time_data:
                data.clear()
        if hasattr(self, 'joint_angle_data'):
            for data in self.joint_angle_data:
                data.clear()
        if hasattr(self, 'plot_worker'):
            self.plot_worker.stop()

        # 立即将所有设备状态设为断开（灰色）
        for device_id in range(2, 9):
            self.device_status[device_id] = "disconnected"
            # 获取标签名
            status_text_label = f"label_imu{device_id}_status_text"
            status_color_label = f"label_imu{device_id}_status_color"
            battery_label = f"label_imu{device_id}_battery_data"

            # 更新为未连接状态（灰色）
            getattr(self, status_text_label).setText("未连接")
            getattr(self, status_color_label).setStyleSheet("background-color: rgb(200, 200, 200);")

            # 重置电池显示
            getattr(self, battery_label).setText("0")

            # 清空历史电量数据
            self.battery_history[device_id].clear()
            self.current_battery[device_id] = 0

        # 更新按钮状态
        self.pushButton_begin_read.setEnabled(True)
        self.pushButton_imu_close.setEnabled(True)
        self.pushButton_end_read.setEnabled(False)

    def update_label_origin_angle_data(self, data_list):
        """
        批量处理IMU数据，减少UI更新频率，提高性能
        :param data_list: 包含多个IMU数据包的列表
        """
        # 记录处理开始时间
        process_start = time.perf_counter()

        # 遍历所有数据包
        for data in data_list:
            device_number = data['device']
            ang_data = data['ang']
            vel_data = data['vel']
            acc_data = data['acc']
            battery_value = data['battery']

            # 更新设备最后接收时间
            self.device_last_seen[device_number] = time.time()

            # 处理角度数据
            for i, axis in enumerate(['x', 'y', 'z']):
                # 获取角度值
                ang_value = ang_data[i]

                # 更新显示标签
                label_name = f"label_origin_data_imu{device_number - 1}{axis}_data"
                getattr(self, label_name).setText(f"{ang_value:.3f}")

                # 使用第一段代码的索引计算方法
                data_type = axis
                # 角度值
                value_type = 'ang'
                i_index = self.mapping1[data_type]  # 1,2,3
                j_index = self.mapping2[value_type]  # 1
                index = 9 * (device_number - 2) + 3 * (i_index - 1) + j_index + 7
                self.data_save[index] = round(ang_value, 6)

                # 角速度值
                vel_value = vel_data[i]
                value_type = 'vel'
                j_index = self.mapping2[value_type]  # 2
                index = 9 * (device_number - 2) + 3 * (i_index - 1) + j_index + 7
                self.data_save[index] = round(vel_value, 6)

                # 加速度值
                acc_value = acc_data[i]
                value_type = 'acc'
                j_index = self.mapping2[value_type]  # 3
                index = 9 * (device_number - 2) + 3 * (i_index - 1) + j_index + 7
                self.data_save[index] = round(acc_value, 6)

                # 如果是X轴角度，更新关节角度数据
                if axis == 'x':
                    self.update_label_joint_angle_data(axis, device_number)

            # 处理电池数据
            # 首次收到数据时强制更新显示
            if self.current_battery[device_number] == 0:
                label_name = f"label_imu{device_number}_battery_data"
                getattr(self, label_name).setText(f"{int(round(battery_value))}%")
                self.last_displayed_battery[device_number] = battery_value

            # 保存原始电池值
            self.current_battery[device_number] = battery_value

            # 添加新的电池值到历史队列
            self.battery_history[device_number].append(battery_value)

            # 计算平滑后的电池值
            if self.battery_history[device_number]:
                avg_battery = sum(self.battery_history[device_number]) / len(self.battery_history[device_number])
                battery_value = int(round(avg_battery))

                # 仅当电量变化超过±3%时才更新显示
                if abs(battery_value - self.last_displayed_battery[device_number]) >= 3:
                    # 更新电池电量显示
                    label_name = f"label_imu{device_number}_battery_data"
                    getattr(self, label_name).setText(f"{battery_value}%")
                    # 更新上次显示的电量值
                    self.last_displayed_battery[device_number] = battery_value

                # 检查低电量警告
                if battery_value < 20:
                    self.update_device_status(device_number, "low_battery")
                else:
                    self.update_device_status(device_number, "connected")

        # 批量处理结束后更新一次时间显示
        time_data = round(time.perf_counter() - self.start_time, 3)
        self.label_current_time_data.setText(f"{time_data:.3f}")
        self.data_save[0] = time_data

        # 调试信息：显示处理耗时
        process_time = (time.perf_counter() - process_start) * 1000
        if process_time > 10:  # 如果处理时间超过10ms，打印警告
            print(f"警告：处理{len(data_list)}个数据包耗时{process_time:.2f}ms")

    def update_label_joint_angle_data(self, data_type, device_number):
        """
        根据不同 IMU 的数据变化更新关节角度数据到 UI 标签
        :param data_type: 数据类型，可能是 'x', 'y', 'z' 或 'battery'
        :param device_number: IMU 设备编号
        """
        # 初始化 joint_data 变量
        joint_data = 0.0

        if data_type == 'x':
            if device_number in [2, 3, 6]:
                label_name1 = f"label_origin_data_imu{device_number - 1}{data_type}_data"
                imu_data1 = float(getattr(self, label_name1).text())
                joint_data = imu_data1 + self.comp_data[device_number - 2]
                if device_number == 2:
                    # self.label_angle_upperbody_data.setText(f"{joint_data:.3f}")  # 上身角度
                    self.upperbody_angle = joint_data  # 保存到属性
                    self.data_save[1] = joint_data
                elif device_number == 3:
                    self.label_angle_left_hip_data.setText(f"{-joint_data:.3f}")  # 左髋角度
                    self.data_save[2] = -joint_data
                elif device_number == 6:
                    self.label_angle_right_hip_data.setText(f"{-joint_data:.3f}")  # 右髋角度
                    self.data_save[5] = -joint_data

            elif device_number in [4, 5, 7, 8]:
                label_name1 = f"label_origin_data_imu{device_number - 2}{data_type}_data"
                imu_data1 = float(getattr(self, label_name1).text())
                label_name2 = f"label_origin_data_imu{device_number - 1}{data_type}_data"
                imu_data2 = float(getattr(self, label_name2).text())
                joint_data = -(imu_data1 + self.comp_data[device_number - 3]) + (
                        imu_data2 + self.comp_data[device_number - 2])
                if device_number == 4:
                    self.label_angle_left_knee_data.setText(f"{joint_data:.3f}")  # 左膝角度
                    self.data_save[3] = round(joint_data, 6)
                elif device_number == 5:
                    self.label_angle_left_ankle_data.setText(f"{joint_data:.3f}")  # 左踝角度
                    self.data_save[4] = round(joint_data, 6)
                elif device_number == 7:
                    self.label_angle_right_knee_data.setText(f"{joint_data:.3f}")  # 右膝角度
                    self.data_save[6] = round(joint_data, 6)
                elif device_number == 8:
                    self.label_angle_right_ankle_data.setText(f"{joint_data:.3f}")  # 右踝角度
                    self.data_save[7] = round(joint_data, 6)

        # 只处理x数据类型的设备2-8
        if data_type == 'x' and device_number in range(2, 9):
            self.update_joint_angle_data(device_number, joint_data)

    def calculate_step_width(self, data, peaks_left, peaks_right):
        """
        计算步宽（step width）
        :param data: np.ndarray, 输入数据
        :param peaks_left: list, 左髋关节峰值索引列表
        :param peaks_right: list, 右髋关节峰值索引列表
        :return: list, 每个步态周期的步宽列表
        """
        # 定义IMU列的索引（根据您的数据结构调整）
        imu4_y_col = 29  # 左脚Y方向角度列索引
        imu7_y_col = 56  # 右脚Y方向角度列索引

        step_widths = []
        # 合并所有步态周期起点
        all_peaks = sorted(peaks_left + peaks_right)

        # 遍历每个步态周期
        for i in range(len(all_peaks) - 1):
            start = all_peaks[i]
            end = all_peaks[i + 1]

            # 提取该周期内左右脚的Y方向角度
            left_foot_y = np.max(np.abs(data[start:end, imu4_y_col]))
            right_foot_y = np.max(np.abs(data[start:end, imu7_y_col]))

            # 计算步宽（角度差值）
            step_width = abs(left_foot_y - right_foot_y)
            step_widths.append(step_width)

        return step_widths

    #绘图槽函数
    def refresh_curves_slot(self, packet):
        """
        packet: list of (times, angles, joint_index)
        运行在主线程，但只做 setData，不处理复杂逻辑
        """
        for times, angles, idx in packet:
            if idx < len(self.joint_curves):
                self.joint_curves[idx].setData(times, angles, _callSync='off')

        # 如需要自动滚动 X 轴，可在主线程简单处理
        if packet:
            last_time = packet[-1][0][-1] if packet[-1][0] else 0
            if last_time:
                for curve in self.joint_curves:
                    vb = curve.getViewBox()
                    if vb:
                        vb.setXRange(max(0, last_time - 8), last_time, padding=0)
    # 计算真实步宽的函数
    def step_width_from_ndarray(
            self,
            data: np.ndarray,
            peaks_left,
            peaks_right,
            L_thigh: float,
            L_shank: float,
            offset_thigh_left=0.0,
            offset_shank_left=0.0,
            offset_thigh_right=0.0,
            offset_shank_right=0.0,
            fs=50.0
    ):
        """
        基于 ndarray 计算真实步宽（米）

        data 形状: (N, 80)   # N 行，80 列（与原始 CSV 列数一致）
        列索引按原顺序：
          0:time, 1:上身, 2:左髋, 3:左膝, 4:左踝, 5:右髋, 6:右膝, 7:右踝,
          8~16: imu1 (ang_x,vel_x,acc_x,ang_y,vel_y,acc_y,ang_z,vel_z,acc_z),
          17~25: imu2, 26~34: imu3, 35~43: imu4, 44~52: imu5, 53~61: imu6, 62~70: imu7
        我们需要的 Y 轴角度列：
          imu2_y = 20, imu3_y = 29, imu5_y = 47, imu6_y = 56
        """
        # 提取需要的四列
        cols = np.array([20, 29, 47, 56])  # imu2_y, imu3_y, imu5_y, imu6_y
        angles = data[:, cols]  # shape (N, 4)

        # 低通滤波
        def lowpass(sig, cutoff=5, fs=fs, order=2):
            nyq = 0.5 * fs
            b, a = butter(order, cutoff / nyq, btype='low', analog=False)
            return filtfilt(b, a, sig)

        for i in range(4):
            angles[:, i] = lowpass(angles[:, i])

        # 角度补偿并转为弧度
        offsets = np.array([
            offset_thigh_left,
            offset_shank_left,
            offset_thigh_right,
            offset_shank_right
        ])
        angles_rad = np.radians(angles - offsets)

        # 计算横向位移（米）
        left_disp = np.abs(angles_rad[:, 0]) * L_thigh + np.abs(angles_rad[:, 1]) * L_shank
        right_disp = np.abs(angles_rad[:, 2]) * L_thigh + np.abs(angles_rad[:, 3]) * L_shank

        # 合并周期起点并计算步宽
        all_peaks = sorted(peaks_left + peaks_right)
        widths = []
        for i in range(len(all_peaks) - 1):
            start, end = all_peaks[i], all_peaks[i + 1]
            left_max = left_disp[start:end].max()
            right_max = right_disp[start:end].max()
            widths.append(abs(left_max - right_max))

        return widths

    def update_joint_angle_data(self, device_number, angle_value):
        """
        更新特定关节的绘图数据
        """
        # 检查关节角度图是否初始化成功
        if not hasattr(self, 'joint_curves') or not hasattr(self, 'joint_time_data') or not hasattr(self,'joint_angle_data'):
            return

        # 映射设备号到关节索引
        joint_index = self.device_to_joint.get(device_number)
        if joint_index is None:
            return

        # 获取当前时间
        current_time = time.perf_counter() - self.start_time

        # 更新时间队列
        if joint_index < len(self.joint_time_data):
            self.joint_time_data[joint_index].append(current_time)
        else:
            # 如果索引超出范围，扩展列表
            while len(self.joint_time_data) <= joint_index:
                self.joint_time_data.append([])
            self.joint_time_data[joint_index].append(current_time)

        # 更新该关节的角度数据
        if joint_index < len(self.joint_angle_data):
            self.joint_angle_data[joint_index].append(angle_value)
        else:
            # 如果索引超出范围，扩展列表
            while len(self.joint_angle_data) <= joint_index:
                self.joint_angle_data.append([])
            self.joint_angle_data[joint_index].append(angle_value)

    def update_joint_angle_plot(self):
        """更新关节角度图 - 每个关节独立更新"""
        # 确保所有必要的属性都存在
        if not hasattr(self, 'joint_curves') or not hasattr(self, 'joint_time_data') or not hasattr(self,
                                                                                                    'joint_angle_data'):
            return

        # 遍历所有关节
        for joint_index in range(len(self.joint_curves)):
            # 确保索引在有效范围内
            if joint_index >= len(self.joint_time_data) or joint_index >= len(self.joint_angle_data):
                continue

            # 检查是否有实际数据
            has_real_data = bool(self.joint_time_data[joint_index] and self.joint_angle_data[joint_index])

            # 如果没有实际数据，跳过这个关节的更新
            if not has_real_data:
                continue

            try:
                # 使用实际数据
                time_points = list(self.joint_time_data[joint_index])
                angle_points = list(self.joint_angle_data[joint_index])

                if not time_points or not angle_points:
                    continue

                # 获取最近的时间点
                last_time = time_points[-1]

                # 更新曲线数据
                self.joint_curves[joint_index].setData(
                    time_points,
                    angle_points
                )

                # 设置视图范围（始终显示最后8秒）
                view_min = max(0, last_time - 8)
                view_max = last_time

                # 获取视图框
                view_box = self.joint_curves[joint_index].getViewBox()
                if view_box:
                    view_box.setXRange(view_min, view_max, padding=0)

                    # 如果数据量足够（大于8秒），保持固定8秒窗口
                    if view_min > 0:
                        view_box.setLimits(xMin=view_min, xMax=view_max, minXRange=8, maxXRange=8)

            except Exception as e:
                print(f"更新关节角度图错误 (关节 {joint_index}): {str(e)}")

    def begin_record(self):
        """
        启动数据记录的计时器
        """

        # ==== 新增：获取保存路径 ====
        save_path = self.lineEdit_save_path.text().strip()
        if not save_path:
            # 使用默认路径
            save_path = self.default_save_path
        # 清空事件队列
        with self._plantar_q_lock:
            self._plantar_q.clear()
        self._writer_running = True

        # 获取当前日期和时间
        # 使用时间戳生成文件名
        current_datetime = datetime.datetime.now()
        filename = f"data_{current_datetime.strftime('%Y%m%d_%H%M%S')}.csv"

        # 组合完整文件路径
        file_path = os.path.join(save_path, filename)

        # 确保路径存在
        if not os.path.exists(save_path):
            try:
                os.makedirs(save_path)
            except OSError as e:
                QtWidgets.QMessageBox.warning(
                    self,
                    "路径错误",
                    f"无法创建保存目录: {str(e)}",
                    QtWidgets.QMessageBox.Ok
                )
                return

        try:
            # 记录数据用
            self.csv_file = None
            self.csv_writer = None
            self.filename = filename  # 保存文件名

            # ==== 新增：保存路径属性 ====

            self.save_path = save_path  # 保存路径
            # 打开文件
            self.csv_file = open(file_path, 'w', newline='', encoding='utf-8-sig')  # 添加utf-8编码
            self.csv_writer = csv.writer(self.csv_file)

            # 添加姓名登记行（单字段）
            # self.csv_writer.writerow(["姓名："])
            self.csv_writer.writerow(self.fieldnames)

            # 启动定时器
            self.timer_record.start(self.refresh)

            # 更新按钮状态
            self.pushButton_begin_record.setEnabled(False)
            self.pushButton_end_record.setEnabled(True)

        except Exception as e:
            print(f"开始记录失败: {str(e)}")
            QtWidgets.QMessageBox.critical(
                self,
                "记录错误",
                f"无法开始记录数据: {str(e)}",
                QtWidgets.QMessageBox.Ok
            )
            # 确保按钮状态正确
            self.pushButton_begin_record.setEnabled(True)
            self.pushButton_end_record.setEnabled(False)

    def stop_record_save(self):
        """结束数据记录并保存"""
        try:
            # 1. 停止记录定时器
            self.timer_record.stop()
            # 添加短暂延迟确保所有数据写入
            time.sleep(0.1)

            # 2. 正确关闭文件
            if self.csv_file:
                try:
                    # 确保所有数据都写入磁盘
                    self.csv_file.flush()
                    # 使用系统调用强制将数据写入磁盘
                    if hasattr(self.csv_file, 'fileno'):
                        import os
                        os.fsync(self.csv_file.fileno())
                finally:
                    # 无论如何都尝试关闭文件
                    self.csv_file.close()

            # 3. 显示原始数据保存成功的提示
            # 获取保存路径
            save_path = self.lineEdit_save_path.text().strip()
            if not save_path:
                save_path = self.default_save_path

            # 构建完整的文件路径
            file_path = os.path.join(save_path, self.filename)

            # 显示提示框
            QtWidgets.QMessageBox.information(
                self,
                "记录完成",
                f"已结束记录，数据已保存至：\n{file_path}",
                QtWidgets.QMessageBox.Ok
            )

            # 4. 设置固定的步态参数值doubleSpinBox_leg_width
            thigh_length = self.doubleSpinBox_thigh_length_data.value()
            shank_length = self.doubleSpinBox_shank_length_data.value()
            step_width = self.doubleSpinBox_leg_width.value()

            # 5. 保存到步态参数数组
            self.gait_parameters[0] = thigh_length
            self.gait_parameters[1] = shank_length
            self.gait_parameters[2] = step_width

            # 6. 步态参数计算
            time_interval = 0.02

            # 构建原始数据文件的完整路径
            file_path = os.path.join(save_path, self.filename)
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"原始数据文件不存在: {file_path}")

            # 第一步：数据归一化，保存为pre01
            data, headers = data_pre.read_csv_file(file_path)
            pre01 = data_pre.data_pre_analyze01(data, time_interval)

            # 第二步：寻找左髋和右髋的极大值点
            # 提取第一个极大值点到最后一个极大值点的数据内容，保存为pre02（这样可以提取中间的有效数据）
            peaks01, peaks02, pre02 = data_pre.data_pre_analyze02(pre01, 18, 2, 45, 5, 0)
            pre02_a = data_pre.cal_foot_acc(pre02)  # 中间过程，计算足部x方向加速度

            # 第三步：计算各个参数
            peaks_left = data_pre.find_and_filter_peaks(pre02, 18, 2, 0)
            peaks_right = data_pre.find_and_filter_peaks(pre02, 45, 5, 0)

            # 计算参数1：左右腿运动周期
            period_left = min(max(data_pre.calculate_average_interval(peaks_left) * time_interval, 0), 9.9)
            period_right = min(max(data_pre.calculate_average_interval(peaks_right) * time_interval, 0), 9.9)
            self.label_left_period_data.setText(str(round(period_left, 2)))
            self.label_right_period_data.setText(str(round(period_right, 2)))
            self.gait_parameters[7] = period_left
            self.gait_parameters[8] = period_right

            # 计算参数2：左右腿支撑相摆动相占比
            def calculate_phase_percentages(heel_strikes, toe_offs, time_interval):
                """
                计算支撑相和摆动相占比
                :param heel_strikes: 足跟着地事件索引列表
                :param toe_offs: 足尖离地事件索引列表
                :param time_interval: 采样时间间隔
                :return: 平均支撑相占比, 平均摆动相占比
                """
                if not heel_strikes or not toe_offs:
                    return 0.0, 0.0  # 如果没有检测到事件，返回0

                # 确保事件顺序正确
                heel_strikes = sorted(heel_strikes)
                toe_offs = sorted(toe_offs)

                # 移除不在合理范围内的事件
                heel_strikes = [hs for hs in heel_strikes if 0 <= hs < len(pre02_a)]
                toe_offs = [to for to in toe_offs if 0 <= to < len(pre02_a)]

                # 确保每个足跟着地事件后有对应的足尖离地事件
                valid_pairs = []
                for hs in heel_strikes:
                    # 找到在hs之后的第一个to
                    possible_toes = [to for to in toe_offs if to > hs]
                    if possible_toes:
                        to = min(possible_toes)
                        valid_pairs.append((hs, to))
                        # 移除已使用的toe_off事件
                        toe_offs.remove(to)

                if not valid_pairs:
                    return 0.0, 0.0

                # 计算每个周期的支撑相和摆动相
                support_times = []
                swing_times = []

                for i in range(len(valid_pairs) - 1):
                    hs1, to1 = valid_pairs[i]
                    hs2, to2 = valid_pairs[i + 1]

                    # 支撑相时间 = 足跟着地到足尖离地
                    support_time = (to1 - hs1) * time_interval

                    # 摆动相时间 = 足尖离地到下一次足跟着地
                    swing_time = (hs2 - to1) * time_interval

                    # 整个周期时间
                    cycle_time = (hs2 - hs1) * time_interval

                    # 验证数据合理性
                    if support_time > 0 and swing_time > 0 and cycle_time > 0 and \
                            abs((support_time + swing_time) - cycle_time) < 0.1:  # 允许10%误差
                        support_times.append(support_time)
                        swing_times.append(swing_time)

                if not support_times or not swing_times:
                    return 0.0, 0.0

                # 计算平均值
                avg_support_time = sum(support_times) / len(support_times)
                avg_swing_time = sum(swing_times) / len(swing_times)
                avg_cycle_time = avg_support_time + avg_swing_time

                # 计算百分比
                support_per = (avg_support_time / avg_cycle_time) * 100
                swing_per = (avg_swing_time / avg_cycle_time) * 100

                # 确保总和为100%
                total = support_per + swing_per
                if abs(total - 100) > 1:  # 如果误差超过1%，重新计算
                    support_per = (avg_support_time / avg_cycle_time) * 100
                    swing_per = 100 - support_per

                return support_per, swing_per

            # 左腿计算
            heel_strike_left = data_pre.find_heel_strike(pre02_a, 71)
            toe_off_left = data_pre.find_toe_off(pre02_a, 71)
            support_per_left, swing_per_left = calculate_phase_percentages(heel_strike_left, toe_off_left,
                                                                           time_interval)

            # 右腿计算
            heel_strike_right = data_pre.find_heel_strike(pre02_a, 72)
            toe_off_right = data_pre.find_toe_off(pre02_a, 72)
            support_per_right, swing_per_right = calculate_phase_percentages(heel_strike_right, toe_off_right,
                                                                             time_interval)

            # 更新UI和参数存储
            self.label_left_swing_data.setText(str(round(swing_per_left, 2)))
            self.label_left_support_data.setText(str(round(support_per_left, 2)))
            self.gait_parameters[3] = swing_per_left
            self.gait_parameters[5] = support_per_left

            self.label_right_swing_data.setText(str(round(swing_per_right, 2)))
            self.label_right_support_data.setText(str(round(support_per_right, 2)))
            self.gait_parameters[4] = swing_per_right
            self.gait_parameters[6] = support_per_right
            #print(f"左脚加速度数据示例: {pre02_a[:10, 71]}")
           #print(f"右脚加速度数据示例: {pre02_a[:10, 72]}")
           #print(f"检测到的左脚足跟着地事件: {heel_strike_left}")
           #print(f"检测到的左脚足尖离地事件: {toe_off_left}")
            # 计算参数3：左右腿平均步长
            step_length_left = data_pre.cal_step_length(pre02_a, heel_strike_left)
            step_length_left_mean = min(
                max(sum(step_length_left) / len(step_length_left) if step_length_left else 0, 0), 9.9)
            self.label_left_step_length_data.setText(str(round(step_length_left_mean, 3)))
            self.gait_parameters[9] = step_length_left_mean
            step_length_right = data_pre.cal_step_length(pre02_a, heel_strike_right)
            step_length_right_mean = min(
                max(sum(step_length_right) / len(step_length_right) if step_length_right else 0, 0), 9.9)
            self.label_right_step_length_data.setText(str(round(step_length_right_mean, 3)))
            self.gait_parameters[10] = step_length_right_mean
            #平均步幅
            stride_length=step_length_right_mean+step_length_left_mean
            self.label_right_stride_length_data.setText(str(round(stride_length, 3)))

            # ==== 新增：计算步宽 ====
            # 获取肢体长度
            thigh_length = self.doubleSpinBox_thigh_length_data.value()
            shank_length = self.doubleSpinBox_shank_length_data.value()

            # 获取补偿值
            offset_thigh_left = self.comp_data[1]  # 左大腿补偿值
            offset_shank_left = self.comp_data[2]  # 左小腿补偿值
            offset_thigh_right = self.comp_data[4]  # 右大腿补偿值
            offset_shank_right = self.comp_data[5]  # 右小腿补偿值
            widths = self.step_width_from_ndarray(
                pre01,
                peaks_left,
                peaks_right,
                thigh_length,
                shank_length,
                offset_thigh_left,
                offset_shank_left,
                offset_thigh_right,
                offset_shank_right
            )
            if len(widths) != 0:
                widths_mean = self.doubleSpinBox_leg_width.value() + sum(widths) / len(widths)
                print("平均真实步宽（米）：%.3f m" % widths_mean)
                # ==== 新增：更新UI显示 ====
                self.label_step_width_data.setText(str(round(widths_mean, 3)))
                self.label_left_step_width_data.setText(str(round(self.doubleSpinBox_leg_width.value(), 3)))
                self.gait_parameters[11] = widths_mean  # 使用索引2存储步宽

            # 计算参数4：左右腿平均步速
            speed_left = min(max(step_length_left_mean / period_left if period_left != 0 else 0, 0), 9.9)
            #self.label_left_step_speed_data.setText(str(round(speed_left, 3)))
            self.gait_parameters[13] = speed_left
            speed_right = min(max(step_length_right_mean / period_right if period_right != 0 else 0, 0), 9.9)
            #self.label_right_step_speed_data.setText(str(round(speed_right, 3)))
            self.gait_parameters[14] = speed_right
            speed=0.5*(speed_left+speed_right)
            self.label_left_step_speed_data.setText(str(round(speed, 3)))

            # 计算参数5：总平均周期、步长
            peak_all = peaks_left + peaks_right
            period_all = min(max(data_pre.calculate_average_interval(peak_all) * time_interval if peak_all else 0, 0),9.9)
            if period_all != 0:
                self.label_average_period_data.setText(str(round(1/period_all, 2)))
                self.gait_parameters[15] = period_all
                step_all = step_length_left + step_length_right
                step_average = min(max(sum(step_all) / len(step_all) if step_all else 0, 0), 9.9)
                self.label_step_length_data.setText(str(round(step_average, 3)))
                self.gait_parameters[16] = step_average
                self.gait_parameters[17] = speed
                self.gait_parameters[18] = stride_length
                self.gait_parameters[19] = 1/period_all
            # 7. 保存步态参数结算结果到新文件
            # 构建步态参数文件名（在原文件名基础上添加后缀）
            gait_params_filename = f"gait_params_{self.filename.split('.')[0]}.csv"
            gait_params_path = os.path.join(save_path, gait_params_filename)

            # 定义步态参数表头
            gait_params_headers = [
                "大腿长度(m)", "小腿长度(m)","步宽(m)",
                "左腿摆动相占比(%)", "右腿摆动相占比(%)",
                "左腿支撑相占比(%)", "右腿支撑相占比(%)",
                "左腿运动周期(s)", "右腿运动周期(s)",
                "左腿平均步长(m)", "右腿平均步长(m)",
                "左腿平均步速(m/s)", "右腿平均步速(m/s)",
                "平均运动周期(s)", "平均步长(m)","步速(m/s)",
                "步幅(m)","步频(步/s)"
            ]

            # 尝试保存步态参数文件
            try:
                with open(gait_params_path, 'w', newline='', encoding='utf-8-sig') as gait_file:
                    writer = csv.writer(gait_file)

                    # 写入表头
                    writer.writerow(gait_params_headers)

                    # 写入步态参数数据
                    writer.writerow([
                        self.gait_parameters[0], self.gait_parameters[1],self.gait_parameters[11],
                        self.gait_parameters[3], self.gait_parameters[4],
                        self.gait_parameters[5], self.gait_parameters[6],
                        self.gait_parameters[7], self.gait_parameters[8],
                        self.gait_parameters[9], self.gait_parameters[10],
                        self.gait_parameters[13], self.gait_parameters[14],
                        self.gait_parameters[15], self.gait_parameters[16],
                        self.gait_parameters[17],self.gait_parameters[18],
                        self.gait_parameters[19]
                    ])

                    # 添加空行分隔
                    writer.writerow([])
                    writer.writerow([])

                    # 添加详细说明
                    writer.writerow(["参数说明:"])
                    writer.writerow(["大腿长度: 大腿IMU到髋关节的距离"])
                    writer.writerow(["小腿长度: 小腿IMU到膝关节的距离"])
                    writer.writerow(["摆动相占比: 摆动相时间占整个步态周期的百分比"])
                    writer.writerow(["支撑相占比: 支撑相时间占整个步态周期的百分比"])
                    writer.writerow(["运动周期: 完成一个完整步态周期所需的时间"])
                    writer.writerow(["平均步长: 同侧足跟着地点到下一个同侧足跟着地点之间的距离"])
                    writer.writerow(["平均步速: 单位时间内行走的距离"])
            except Exception as e:
                # 步态参数保存失败时打印错误，但不中断整体流程
                print(f"保存步态参数失败: {str(e)}")


        except Exception as e:
            err_msg = traceback.format_exc()
            print(f"结束记录过程中出错: {str(e)}")
            print(err_msg)
            QtWidgets.QMessageBox.warning(
                self,
                "记录错误",
                f"结束记录时出错: {str(e)}",
                QtWidgets.QMessageBox.Ok
            )
        finally:
            # 7. 更新按钮状态
            self.pushButton_begin_record.setEnabled(True)
            self.pushButton_end_record.setEnabled(False)

            # 8. 重置文件相关变量
            self.csv_file = None
            self.csv_writer = None
            self.save_path = None
            self.file_path = None
            self.filename = None

    def record_data(self):
        """定时记录当前数据到 CSV"""
        t_now = round(time.perf_counter() - self.start_time, 3)
        self.data_save[0] = t_now
        #落盘
        self.csv_writer.writerow(self.data_save)
    
    # 左足压力显示开/关   
    def on_show_left_clicked(self):
        """左足压力显示开/关"""
        try:
            # 初始化左足（two_plant.FootSensor）
            if not hasattr(self, "left_foot") or self.left_foot is None:
                print(f"[Plantar] 初始化左足串口: {self.serial_port2}")
        
                self.left_thread = FootSensor(port=None,is_left=True,ser=self.serial_port2)
                self.left_thread.foot_data_ready.connect(self.read_packet_plantar)
                self.left_thread.start()
                print("[Plantar] 左足足底压力线程已启动")
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "足底压力错误", f"足底压力初始化失败：{e}")
            return

        # 定时刷新 UI
        if not hasattr(self, "timer_left"):
            self.timer_left = QtCore.QTimer(self)
            self.timer_left.timeout.connect(lambda: self.update_plantar_labels_side(
                is_left=True, fmt="%.0f", show_color=True, vmin=0.0, vmax=2000.0
            ))

        if not self.timer_left.isActive():
            self.timer_left.start(50)  # 50ms 刷新一次
            print("[Plantar] 左足显示启动")
        else:
            self.timer_left.stop()
            print("[Plantar] 左足显示停止")
        
        self.pushButton_begin_read2.setEnabled(False)
        self.pushButton_imu_close2.setEnabled(False)
        self.pushButton_end_read2.setEnabled(True)
    #读取足底压力数据
    def read_packet_plantar(self, data):
        """从 FootSensor 读取左足压力数据的槽函数"""
        #print(f"收到足底压力数据: {data}")
        if data["side"] == "left":
            self.data_save[71:89] = list(data["values"][:18])
            self.data_save[107] = data["frame_id"]
        if data["side"] == "right":
            self.data_save[89:107] = list(data["values"][:18])  
            self.data_save[108] = data["frame_id"]
    
    def _on_plantar_packet(self, side: str, values: list):
        """被 FootSensor 回调：拿到一帧18点"""
        if ts is None:
            ts = time.perf_counter()
        with getattr(self, "_plantar_lock", threading.Lock()):
            if side == "left":
                self.plantar_left_latest = values[:18]
                #print(f"左足压力数据: {values[:18]}")
                self._plantar_left_ts = time.time()
            else:
                self.plantar_right_latest = values[:18]
                self._plantar_right_ts = time.time()
        # 2) 入队（不阻塞采集线程）。带上帧号，便于后续写入。
        if side == "left" and getattr(self, "left_foot", None):
            try:
                with self.left_foot.lock:
                     fid = int(getattr(self.left_foot, "frame_id", 0))
            except Exception:
                 fid = 0
            item = ("left", fid, float(ts), values[:18])
        elif side == "right" and getattr(self, "right_foot", None):
            try:
                with self.right_foot.lock:
                    fid = int(getattr(self.right_foot, "frame_id", 0))
            except Exception:
                fid = 0
            item = ("right", fid, float(ts), values[:18])
        else:
            item = (side, 0, float(ts), values[:18])

        try:
            with self._plantar_q_lock:
                self._plantar_q.append(item)
        except Exception:
            pass
    # 安全结束采集线程
    def end_read_thread_action_left(self):
        """仅停止左足采集与显示"""
        try:
            # 1) 停采集循环 + 关串口
            if hasattr(self, "left_thread") and self.left_thread:
                try:
                    # 要求 FootSensor 内部有 stop()：running.clear() + ser.close()
                    self.left_thread.stop()
                    print("[Plantar] 左足采集已停止")
                except Exception as e:
                    print(f"[Plantar] 左足 stop() 异常: {e}")

            # 2) 停止左足的定时刷新
            if hasattr(self, "timer_left") and self.timer_left and self.timer_left.isActive():
                self.timer_left.stop()
                print("[Plantar] 左足定时器停止")

            # 3) 等待左足线程退出
            if hasattr(self, "left_thread") and self.left_thread and self.left_thread.isRunning():
                self.left_thread.join(timeout=1.0)
                print("[Plantar] 左足线程结束")

            # 4) 恢复按钮文字（若存在）
            if hasattr(self, "pushButton_show_left"):
                self.pushButton_show_left.setText("显示左足压力")

            # 5) 可选：清理引用，避免重复使用旧对象
            self.left_thread = None
            self.left_foot = None

        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "结束错误", f"停止左足采集失败：{e}")
            print(f"[Plantar] 停止左足采集失败: {e}")
        
        self.pushButton_begin_read2.setEnabled(True)
        self.pushButton_imu_close2.setEnabled(True)
        self.pushButton_end_read2.setEnabled(False)
    # 右足压力结束读取函数
    def end_read_thread_action_right(self):
        """仅停止右足采集与显示"""
        try:
            # 1) 停采集循环 + 关串口
            if hasattr(self, "right_thread") and self.right_thread:
                try:
                    self.right_thread.stop()
                    print("[Plantar] 右足采集已停止")
                except Exception as e:
                    print(f"[Plantar] 右足 stop() 异常: {e}")

            # 2) 停止右足的定时刷新
            if hasattr(self, "timer_right") and self.timer_right and self.timer_right.isActive():
                self.timer_right.stop()
                print("[Plantar] 右足定时器停止")

            # 3) 等待右足线程退出
            if hasattr(self, "right_thread") and self.right_thread and self.right_thread.isRunning():
                self.right_thread.join(timeout=1.0)
                print("[Plantar] 右足线程结束")

            # 4) 恢复按钮文字（若存在）
            if hasattr(self, "pushButton_show_right"):
                self.pushButton_show_right.setText("显示右足压力")

            # 5) 可选：清理引用
            self.right_thread = None
            self.right_foot = None

        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "结束错误", f"停止右足采集失败：{e}")
            print(f"[Plantar] 停止右足采集失败: {e}")
        
        self.pushButton_begin_read3.setEnabled(True)
        self.pushButton_imu_close3.setEnabled(True)
        self.pushButton_end_read3.setEnabled(False)
    # 左足压力读取线程
    
        """
        后台线程：严格使用 FootSensor 内部的死循环读取。
        兼容三种写法：
        1) read_data(callback=...)
        2) run(callback=...)
        3) 没有回调：while True: values = read_once(); _on_plantar_packet(...)
        """
        try:
            # ① 优先：read_data(callback=...)
            if hasattr(self.right_foot, "read_data"):
                self.right_foot.read_data(callback=None)
                return
            # ② 其次：run(callback=...)
            if hasattr(self.right_foot, "run"):
                self.right_foot.run(callback=self._on_plantar_packet)
                return
            # ③ 兜底：主动拉取
            if hasattr(self.right_foot, "read_once"):
                while True:
                    side, values = self.right_foot.read_once()  # 期望返回 ("left"/"right", [18])
                    if isinstance(values, (list, tuple)) and len(values) >= 18:
                        self._on_plantar_packet(side, list(values))
            else:
                print("[Plantar] FootSensor 未找到可用读取接口(read_data/run/read_once)")
        except Exception as e:
            print(f"[Plantar] 右足读取线程异常: {e}")
    # 右足压力显示开关
    def on_show_right_clicked(self):

        """左足压力显示开/关"""
        try:
            # 初始化左足（two_plant.FootSensor）
            if not hasattr(self, "right_foot") or self.right_foot is None:
                print(f"[Plantar] 初始化右足串口: {self.serial_port3}")
            # 启动读取线程（只启动一次）
                self.right_thread = FootSensor(port=None,is_left=False,ser=self.serial_port3)
                self.right_thread.foot_data_ready.connect(self.read_packet_plantar)
                self.right_thread.start()
                print("[Plantar] 右足足底压力线程已启动")
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "足底压力错误", f"足底压力初始化失败：{e}")
            return

        # 定时刷新 UI
        if not hasattr(self, "timer_right"):
            self.timer_right = QtCore.QTimer(self)
            self.timer_right.timeout.connect(lambda: self.update_plantar_labels_side(
                is_left=False, fmt="%.0f", show_color=True, vmin=0.0, vmax=2000.0
            ))

        if not self.timer_right.isActive():
            self.timer_right.start(50)  # 50ms 刷新一次
            print("[Plantar] 右足显示启动")
        else:
            self.timer_right.stop()
            print("[Plantar] 右足显示停止")

        self.pushButton_begin_read3.setEnabled(False)
        self.pushButton_imu_close3.setEnabled(False)
        self.pushButton_end_read3.setEnabled(True)

    def update_plantar_labels_side(self, is_left=True, fmt="%.1f", show_color=False, vmin=0.0, vmax=2000.0):
        """更新单侧18个足底标签"""
        # 1) 获取目标缓冲和标签列表
        labels = self.labels_left if is_left else self.labels_right
        with self._plantar_lock:
            if is_left:
                vals = [float(x) for x in (self.left_thread.data[:18] if hasattr(self, "plantar_left_latest") else [0]*18)]
            else:
                vals = [float(x) for x in (self.right_thread.data[:18] if hasattr(self, "plantar_right_latest") else [0]*18)]
        # 更新标签
        for i, v in enumerate(vals):
            labels[i].setText(fmt % v)
            if show_color:
                self._apply_label_color(labels[i], v, vmin, vmax) 
    
    def _apply_label_color(self, label, value, vmin, vmax):
        """根据数值强度给 QLabel 背景着色（绿→黄→红），可选调用。"""
        if vmax <= vmin:
            label.setStyleSheet("")  # 量程非法时不改色
            return
        t = (value - vmin) / (vmax - vmin)
        t = 0.0 if t < 0 else (1.0 if t > 1.0 else t)
        # 0~0.5: 绿->黄；0.5~1: 黄->红
        if t <= 0.5:
            k = t / 0.5
            r = int(76 + (255-76)*k)   # 76->255
            g = int(175 + (235-175)*k) # 175->235
            b = 80                     # 常量
        else:
            k = (t-0.5) / 0.5
            r = 255
            g = int(235 - (235-87)*k)  # 235->87
            b = int(59 + (59-34)*k)    # 59->34
        label.setStyleSheet(
            f"background-color: rgb({r},{g},{b});"
            "font-size: 14pt;"
            "color: black; border: 1px solid gray;"
        )

class imuThread(QThread):
    """
    线程类，向主程序发送 IMU 的设备编号、轴名称、值类型、值
    """
    update_label = pyqtSignal(list)  # 设备编号、轴名称、值

    def __init__(self, port,target_hz=100):
        super().__init__()
        self.port = port
        self._is_running = True
        self.target_dt = 1.0 / target_hz
        self.latest_packet = None

    def run(self):
        self.port.reset_input_buffer()
        imu = BlueTeethIMU.imu(self.port)
        data_buffer = []
        last_emit = time.time()  # 初始化 last_emit 变量
        while self._is_running:
            imu.read()
            if imu.read_flag == 4:
                # 存储设备号和各维度数据
                data = {
                    'device': imu.device_number,
                    'ang': imu.data_ang[imu.device_number],
                    'vel': imu.data_vel[imu.device_number],
                    'acc': imu.data_acc[imu.device_number],
                    'battery': imu.battery[imu.device_number]
                }
                data_buffer.append(data)

                # 每5个数据包或100ms发射一次
                if len(data_buffer) >= 5 or time.time() - last_emit > 0.1:
                    self.update_label.emit(data_buffer)
                    data_buffer = []
                    last_emit = time.time()

    def stop(self):
        self._is_running = False

class PlotWorker(QThread):
    # 把处理好的 6 条曲线数据一次性发回主线程
    plot_data_ready = pyqtSignal(list)   # list 内元素: (times, angles, idx)

    def __init__(self,
                 joint_time_deques,
                 joint_angle_deques,
                 parent=None):
        super().__init__(parent)
        self.time_deques = joint_time_deques
        self.angle_deques = joint_angle_deques
        self._running = True
        self.period_ms = 100          # 绘图刷新周期（可改）

    def run(self):
        """子线程死循环：准备数据 -> 发信号"""
        while self._running:
            t0 = time.perf_counter()
            packet = []
            MAX_POINTS = 500
            for idx in range(6):
                if not self.time_deques[idx]:
                    continue
                # 转成 list，只保留后 MAX_POINTS 个
                times  = list(self.time_deques[idx])[-MAX_POINTS:]
                angles = list(self.angle_deques[idx])[-MAX_POINTS:]
                packet.append((times, angles, idx))

            if packet:
                self.plot_data_ready.emit(packet)

            # 精确休眠到下一周期
            elapsed = (time.perf_counter() - t0) * 1000
            QThread.msleep(max(1, self.period_ms - int(elapsed)))

    def stop(self):
        self._running = False
        self.wait()

def my_random(start, end):
    # 使用时间戳和计数器确保每次调用结果不同
    current_time = time.time_ns()
    if not hasattr(my_random, "counter"):
        my_random.counter = 0
    my_random.counter += 1

    # 简单但有效的随机算法
    seed = (current_time * my_random.counter) % 0xFFFFFFFF
    seed = (seed * 1103515245 + 12345) % 0xFFFFFFFF

    # 映射到指定范围
    return start + seed % (end - start + 1)


if __name__ == "__main__":
    import sys

    app = QtWidgets.QApplication(sys.argv)
    mainWindow = MainWindow()
    mainWindow.show()
    sys.exit(app.exec_())