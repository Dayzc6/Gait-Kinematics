# Vicon + IMU + Planter 数据采集系统

## 项目概述

本项目用于同步采集以下三类数据，并输出结构化 CSV：

- **Vicon**：Subject 的 Segment 与 Marker 三维坐标
- **IMU**：7 个 IMU 设备的加速度、角速度、欧拉角与四元数
- **Planter**：左右脚足底压力数据（当前架构支持双串口接收器聚合）

当前项目已经从旧的“共享最新值 + 轮询写盘”模式，重构为更接近实验验证成功路径的新架构，目标是让正式程序中的 Vicon 接收效果尽量接近此前在 `experiments/` 中验证过的：

- 接近 **100Hz**
- 尽量减少 **跳帧**
- 避免旧架构中的 **重复帧**

---

## 当前正式架构

正式主程序采用如下链路：

- **ViconWorker**：每次 `GetFrame()` 成功即形成一帧，逐帧入队
- **IMUWorker**：接收串口数据，维护 latest 数据与时间缓冲区
- **PlanterWorker**：左右两个接收器分别接收，再聚合成统一左右脚数据包
- **SyncEngine**：逐帧消费 Vicon 队列，并按时间戳匹配 IMU / Planter
- **WriterWorker**：批量写入 `synced.csv`、`imu_raw.csv`、`planter_raw.csv`

这条链路的核心目的，是尽量贴近 `experiments/` 中已经验证有效的 Vicon 接收方式，而不是继续沿用旧的共享值采样模式。

---

## 已验证目录与正式目录

### 1. experiments/
用于保留 Vicon 接收链路的验证性实验，作为性能与质量回归基线。

典型实验包括：

- `exp1_frame_only.py`
- `exp2_segment_only.py`
- `exp3_marker_only.py`
- `exp0_baseline_full_marker.py`
- `exp4_frame_only_with_sleep.py`
- `exp5_frame_only_subject_cached.py`

这些实验用于回答：
- 当前 Vicon 链路是否能接近 100Hz
- 哪一类字段读取会造成显著开销
- 主循环设计是否影响基础接收性能

### 2. 正式主程序
正式入口为：

- `main.py`

当前主程序使用新架构，提供命令行控制：

- `start`
- `stop`
- `status`
- `quit`

---

## 项目结构

```text
Data_Collecter/
├── main.py                     # 正式主入口（CLI）
├── config.py                   # 全局配置
├── run.bat                     # Windows 启动脚本
├── run.sh                      # Linux/Mac 启动脚本
├── core/
│   ├── worker_vicon.py         # Vicon 接收线程（逐帧入队）
│   ├── worker_imu.py           # IMU 接收线程（latest + buffer）
│   ├── worker_planter.py       # Planter 双串口接收 + 聚合
│   ├── sync_engine.py          # 同步引擎（逐帧消费）
│   ├── writer_worker.py        # 批量写盘线程
│   └── sync_master.py          # 旧架构保留参考，不再作为正式主路径
├── utils/
│   ├── protocol_imu.py         # IMU 协议解析
│   ├── protocol_planter.py     # Planter 协议解析
│   ├── csv_schema.py           # 新架构 CSV 展开逻辑
│   ├── data_models.py          # 新架构数据模型
│   └── data_writer.py          # 旧写盘器保留参考
├── experiments/                # Vicon 实验验证脚本与结果分析
├── data/                       # 正式程序输出目录
└── reference/                  # 历史参考文件
```

---

## 当前硬件假设

### Vicon
- 通过 DataStream SDK 连接
- 主机地址由 `config.py` 中 `VICON_HOST_IP` 指定
- 当前默认 `SetStreamMode(0)`，与实验脚本保持一致

### IMU
- 单串口接收
- 当前配置示例：
  - `IMU_PORT = 'COM9'`
  - `IMU_BAUDRATE = 460800`

### Planter
- **双接收器 / 双串口** 模式
- 左右脚分别对应一个接收器
- 当前配置示例：
  - `PLANTER_LEFT_PORT = 'COM10'`
  - `PLANTER_RIGHT_PORT = 'COM13'`

PlanterWorker 会将左右脚两个串口的数据聚合为统一的：

- `Left`
- `Right`

再交给同步层使用。

---

## 配置说明

运行前请检查 `config.py`：

```python
# Vicon
VICON_HOST_IP = "192.168.137.157"
VICON_STREAM_MODE = 0

# IMU
IMU_PORT = 'COM9'
IMU_BAUDRATE = 460800
IMU_TIMEOUT = 0.1

# Planter
PLANTER_LEFT_PORT = 'COM10'
PLANTER_RIGHT_PORT = 'COM13'
PLANTER_BAUD_RATE = 115200
PLANTER_TIMEOUT = 2
```

此外还包括：

- 队列长度
- 写盘批量大小
- 同步超时
- IMU / Planter 缓冲区长度

这些参数会影响正式程序在多线程下的吞吐与稳定性。

---

## 运行方式

建议在项目根目录下，以模块方式启动：

```bash
python -m DataCollect.Data_Collecter.main
```

启动后输入命令：

```text
start   # 开始采集
stop    # 停止采集
status  # 查看设备与 Vicon 当前状态
quit    # 退出程序
```

### 推荐启动步骤
1. 先启动 Vicon 主机并确认数据流正常
2. 再启动本程序
3. 输入 `status` 检查：
   - Vicon 是否 connected
   - IMU 是否 connected
   - Planter 左右是否 connected
   - 当前 Latest Frame 是否增长
4. 输入 `start` 开始采集
5. 输入 `stop` 结束采集并检查输出 CSV

---

## 输出文件说明

每次正式采集会在 `data/` 目录下生成 3 个文件：

### 1. `*_synced.csv`
主同步文件，包含：

- `Timestamp`
- `Vicon_Frame_Num`
- `Vicon_Recv_Timestamp`
- `IMU_Recv_Timestamp`
- `Planter_Recv_Timestamp`
- `Vicon_Gap_Flag`
- `Vicon_Gap_Size`
- `IMU_Stale_ms`
- `Planter_Stale_ms`
- `IMU_Matched_Flag`
- `Planter_Matched_Flag`
- Vicon Segment 列
- Vicon Marker 列
- IMU 全设备数据列
- Planter 左右脚 18 点数据列

### 2. `*_imu_raw.csv`
IMU 原始接收展开文件，每条记录包含：

- `Recv_Timestamp`
- `Device_Name`
- `Acc_X/Y/Z`
- `Gyro_X/Y/Z`
- `Roll/Pitch/Yaw`
- `Quat_x/y/z/w`

### 3. `*_planter_raw.csv`
Planter 原始接收展开文件，每个时间戳对应两行：

- `Side = Left`
- `Side = Right`

并展开 `Point_0 ~ Point_17`。

---

## 数据质量判读建议

### Vicon 质量重点看
在 `synced.csv` 中重点关注：

- `Vicon_Frame_Num`
- `Vicon_Gap_Flag`
- `Vicon_Gap_Size`
- `Vicon_Recv_Timestamp`

理想情况下：

- `Vicon_Gap_Flag` 尽量少
- `Vicon_Gap_Size` 尽量接近 0
- 有效频率尽量接近 100Hz
- 帧号连续增长，不应大量重复或大跨度跳变

### IMU 质量重点看
- `imu_raw.csv` 是否持续有数据
- 是否所有 7 个设备都有连续输出
- `IMU_Matched_Flag` 是否合理
- `IMU_Stale_ms` 是否为合理正值，避免大量负值或极大值

### Planter 质量重点看
- 左右脚接收器是否都正常连接
- `planter_raw.csv` 是否持续输出
- `Planter_Matched_Flag` 是否合理

> 如果当前实验阶段暂未实际使用 Planter，且压力值理论上全为 0，则可以只检查结构与连接状态，不把数值全 0 视为失败。

---

## 当前已知情况

### 已完成的改进
- Vicon 正式链路已从旧共享值采样模式切换到逐帧入队模式
- IMU 已并入新架构（latest + buffer + raw csv）
- Planter 已并入双串口正式架构，并聚合为统一左右脚数据包
- Writer 已改为批量写盘，替代旧逐行写盘方式
- experiments 保留为性能与质量基线

### 仍需持续关注
- 正式程序在多设备同时接入时，Vicon 是否仍能保持接近实验中的 100Hz
- IMU / Planter 匹配逻辑是否存在不合理时间戳（例如未来包匹配到过去帧）
- 正式系统整体负载是否会拖低 Vicon 主链路质量

---

## 常见问题

### Q1: 为什么正式程序的 Vicon 表现和 experiments 不完全一样？
A: `experiments/` 是最小验证路径，而正式主程序包含：
- Vicon 接收
- IMU/Planter 接收
- 同步匹配
- 三文件写盘

所以正式系统总负载更高，可能导致 Vicon 质量与最小实验存在差异。应持续用 experiments 作为真实性能基线。

### Q2: 为什么 `planter_raw.csv` 全是 0？
A: 如果当前实验阶段并未实际使用足底压力设备，或设备没有输出有效压力值，那么全 0 是可以接受的。此时只需关注：
- 结构是否正确
- 左右脚接收器是否连接成功
- 文件是否连续输出

### Q3: 为什么 `IMU_Matched_Flag = 1` 但时间不合理？
A: 这通常说明同步匹配策略找到了某个 IMU 包，但不一定是严格意义上“早于或等于当前 Vicon 帧时间”的合理匹配。后续应重点关注 `IMU_Stale_ms` 是否为合理值。

### Q4: 为什么 Git 提示 LF / CRLF？
A: 这是版本控制层面的换行符警告，通常不会影响程序实际运行，但可能影响 diff / commit 的整洁度。

---

## 推荐调试顺序

1. 先跑 `experiments/` 验证 Vicon 单链路
2. 再跑正式主程序 `python -m DataCollect.Data_Collecter.main`
3. 先验证 `status`
4. 再做短时 `start -> stop`
5. 优先看 `synced.csv` 的 Vicon 质量
6. 再看 IMU / Planter raw 文件是否稳定输出

---

## 版本说明

- 创建时间：2026-04-23
- 当前 README 已更新为 **新架构版本说明**
