# Vicon+IMU+Planter 数据采集系统

## 项目概述

本系统用于同步采集Vicon运动捕捉系统、IMU惯性测量单元和Planter足底压力传感器的数据，并通过CSV文件保存。

### 核心功能

1. **Vicon数据采集**：获取Subject的Segment和Marker三维坐标
2. **IMU数据采集**：获取7个IMU设备的加速度、角速度、欧拉角和四元数
3. **Planter数据采集**：获取左右脚各18个感应点的压力数据
4. **同步采集**：以Vicon帧号驱动，解决丢帧和重复帧问题
5. **GUI控制**：提供开始/停止采集的图形界面

### 解决问题

| 问题 | 解决方案 |
|------|----------|
| Vicon丢帧 | 帧号驱动采集，每个新帧都被记录 |
| Vicon重复帧 | 增加`IsDuplicate`列标记（0=新帧，1=重复帧） |
| 数据不同步 | 记录时同时获取三个传感器的最新数据 |

## 系统要求

- Python 3.8+
- Conda环境（推荐）：Vicon_SDK
- 依赖模块：
  - vicon_dssdk（Vicon SDK）
  - pyserial（串口通信）
  - scipy（科学计算）
  - numpy（数值计算）

## 项目结构

```
Data_Collecter_2/
├── main.py                 # 主入口程序
├── config.py               # 全局配置
├── run.bat                # Windows启动脚本
├── run.sh                 # Linux/Mac启动脚本
├── core/
│   ├── worker_vicon.py     # Vicon接收线程
│   ├── worker_imu.py     # IMU接收线程
│   ├── worker_planter.py # Planter接收线程
│   └── sync_master.py     # 同步采集主控
├── utils/
│   ├── protocol_imu.py   # IMU协议解析
│   ├── protocol_planter.py # Planter协议解析
│   └── data_writer.py    # CSV写入器
├── data/                  # CSV输出目录
└── reference/             # 参考文件
```

## 配置说明

在运行前，检查`config.py`中的配置参数：

```python
# IMU串口配置
IMU_PORT = 'COM12'        # IMU连接的串口号
IMU_BAUDRATE = 460800     # 波特率

# Planter串口配置
PLANTER_PORT = 'COM11'     # Planter连接的串口号
PLANTER_BAUD_RATE = 115200 # 波特率

# Vicon配置
VICON_HOST_IP = "192.168.137.157"  # Vicon主机IP
```

## 使用方法

### 方式1：使用启动脚本（推荐）

```bash
# Windows
双击 run.bat

# Linux/Mac
bash run.sh
# 或
./run.sh
```

### 方式2：直接运行Python

```bash
conda activate Vicon_SDK
python main.py
```

### 操作流程

1. 启动程序后，系统自动连接三个硬件设备
2. 等待状态显示"状态: 待机中"
3. 点击"开始采集"按钮：
   - 自动创建CSV文件
   - 发送Vicon录制指令
   - 开始帧号驱动采集
4. 点击"停止采集"按钮：
   - 停止采集
   - 发送Vicon停止指令
   - 显示保存路径

## CSV输出格式

| 列名 | 说明 |
|------|------|
| Timestamp | Unix时间戳（秒） |
| Vicon_Frame_Num | Vicon帧号 |
| IsDuplicate | 重复帧标记（0=新帧，1=重复帧） |
| Vicon_{Seg}_X/Y/Z | Segment三维坐标 |
| Vicon_{Marker}_X/Y/Z | Marker三维坐标 |
| IMU_{Name}_Acc_X/Y/Z | 加速度（m/s²） |
| IMU_{Name}_Gyro_X/Y/Z | 角速度（°/s） |
| IMU_{Name}_Roll/Pitch/Yaw | 欧拉角（°） |
| IMU_{Name}_Quat_x/y/z/w | 四元数 |
| Planter_Left_{0-17} | 左脚18个点压力值 |
| Planter_Right_{0-17} | 右脚18个点压力值 |

## 注意事项

1. **串口冲突**：确保IMU和Planter的串口号不冲突
2. **Vicon连接**：确保电脑与Vicon在同一网络
3. **数据丢失**：如果Vicon丢帧严重，检查网络稳定性
4. **重复帧**：正常现象，Vicon帧率高于采集频���时会出现

## 常见问题

### Q1: 串口打开失败
A: 检查串口号是否正确，串口是否被其他程序占用

### Q2: Vicon连接失败
A: 检查IP地址是否正确，确保网络连通

### Q3: CSV文件为空
A: 检查是否点击了"开始采集"按钮

### Q4: 数据重复太多
A: 这是正常现象，可以使用CSV的`IsDuplicate`列过滤

## 技术支持

如有问题，请检查：
1. 硬件连接是否正常
2. 串口是否正确
3. Vicon网络是否连通
4. 依赖模块是否安装完整

---

**创建时间**: 2026-04-23
**版本**: 1.0.0