# offline_pipeline

该目录用于实现一条与当前正式主程序并行的新方案：

- **正式主程序**：边采集边输出最终 `synced.csv`
- **offline_pipeline**：三个设备分别采集、分别记录绝对时间戳，采集后再解码、重建，并最终重采样到 Vicon 时间轴

这条路线遵循你的新要求：

> 不采用实时快照对齐；
> Vicon、IMU、Planter 都各自记录绝对时间戳；
> 采后再对 IMU / Planter 解码，并以 Vicon 的时间轴做严格重采样。

---

## 当前已实现到“可运行测试”的阶段

目前路线 2 已经实现以下最小可运行链路：

### 采集阶段
- `capture_vicon_minimal.py`
  - 记录：`frame_num`、`recv_timestamp`、`frame_rate`
- `capture_imu_raw.py`
  - 记录：`recv_timestamp`、`raw_hex`
- `capture_planter_raw.py`
  - 记录：`recv_timestamp`、`side`、`raw_hex`
- `capture_session.py`
  - **统一会话入口**：同时启动 Vicon / IMU / Planter 三路采集
  - 输出三份独立日志：
    - `*_vicon.jsonl`
    - `*_imu.jsonl`
    - `*_planter.jsonl`

### 离线阶段
- `decode_imu_raw.py`
  - 从 IMU 原始日志中解出设备级观测
- `decode_planter_raw.py`
  - 从 Planter 原始日志中解出左右脚观测
- `build_imu_snapshots.py`
  - 按时间窗口重建完整 7 设备 IMU observations
- `build_planter_packets.py`
  - 按时间窗口重建完整双脚 Planter observations
- `align_to_vicon.py`
  - 以 Vicon `frame_num + recv_timestamp` 为主轴做严格历史匹配
- `export_training_dataset.py`
  - 导出第一版训练数据 CSV
- `validate_raw_logs.py`
  - 检查 raw / decoded / aligned 等中间日志是否存在、是否有内容

---

## 目录结构

```text
offline_pipeline/
├── __init__.py
├── README.md
├── common.py
├── capture_vicon_minimal.py
├── capture_imu_raw.py
├── capture_planter_raw.py
├── capture_session.py
├── validate_raw_logs.py
├── decode_imu_raw.py
├── decode_planter_raw.py
├── build_imu_snapshots.py
├── build_planter_packets.py
├── align_to_vicon.py
└── export_training_dataset.py
```

---

## 设计原则

### 1. 三种设备分别采集，分别记录绝对时间戳
采集阶段不做跨设备实时同步，只做：

- **Vicon**：记录 `frame_num + recv_timestamp (+ frame_rate)`
- **IMU**：记录 `recv_timestamp + raw_hex`
- **Planter**：记录 `recv_timestamp + side + raw_hex`

### 2. 采集后再解码和重建
- IMU 原始日志 → 设备级观测 → 完整 IMU observations
- Planter 原始日志 → 左右脚观测 → 完整双脚 observations

### 3. 最终以 Vicon 时间轴重采样 / 对齐
对每个 Vicon 帧：
- 用该帧的 `recv_timestamp` 作为主时间轴节点
- 只允许历史且在窗口内的 IMU / Planter observations 匹配到它

### 4. 不修改当前正式主程序
本目录与当前 `main.py` 正式程序并行存在，互不干扰。

---

## 输出位置

路线 2 的中间日志统一写到：

```text
offline_pipeline/raw_logs/
```

文件格式为：
- `*.jsonl`
- 每行一个 JSON 记录

---

## 推荐测试流程

### 方案 A：统一会话采集（推荐）
在项目根目录下运行：

```bash
python -m DataCollect.Data_Collecter.offline_pipeline.capture_session
```

它会同时启动：
- Vicon minimal
- IMU raw
- Planter raw

并在同一会话下生成三份日志：
- `*_vicon.jsonl`
- `*_imu.jsonl`
- `*_planter.jsonl`

### 方案 B：分别单独测试三路采集
如果你只想先单独验证某一路，也可以分别运行：

```bash
python -m DataCollect.Data_Collecter.offline_pipeline.capture_vicon_minimal
python -m DataCollect.Data_Collecter.offline_pipeline.capture_imu_raw
python -m DataCollect.Data_Collecter.offline_pipeline.capture_planter_raw
```

---

## 离线处理流程

### 第一步：检查日志是否生成

```bash
python -m DataCollect.Data_Collecter.offline_pipeline.validate_raw_logs
```

### 第二步：离线解码

```bash
python -m DataCollect.Data_Collecter.offline_pipeline.decode_imu_raw
python -m DataCollect.Data_Collecter.offline_pipeline.decode_planter_raw
```

### 第三步：重建完整 observations

```bash
python -m DataCollect.Data_Collecter.offline_pipeline.build_imu_snapshots
python -m DataCollect.Data_Collecter.offline_pipeline.build_planter_packets
```

### 第四步：对齐到 Vicon 时间轴

```bash
python -m DataCollect.Data_Collecter.offline_pipeline.align_to_vicon
```

### 第五步：导出训练数据集

```bash
python -m DataCollect.Data_Collecter.offline_pipeline.export_training_dataset
```

---

## 当前版本的局限

这是路线 2 的**第一版可运行测试实现**，还存在一些限制：

1. Vicon 目前只记录最小必要字段：`frame_num + recv_timestamp + frame_rate`
2. IMU / Planter 原始日志按 chunk 记录，还没有加入更丰富的元数据（如串口序号、会话配置等）
3. IMU / Planter 的“完整 observation 重建”目前是第一版规则，后续可以继续调优
4. `align_to_vicon.py` 当前使用的是第一版严格历史匹配逻辑，后续可继续扩展为更完整的重采样策略
5. `export_training_dataset.py` 当前是第一版导出格式，后续可以根据训练需求继续精简或扩展

但它已经足够用于回答：
- 路线 2 是否真正可运行
- 原始日志是否能成功解码
- 是否能基于绝对时间戳对齐到 Vicon 时间轴
- 与当前正式主程序相比，轻量采集是否能提升 Vicon 主链路质量

---

## 当前最适合的用途

路线 2 现在最适合做：

1. **数据采集质量测试**
   - 检查在不做实时快照同步的情况下，Vicon 是否更稳定

2. **绝对时间戳对齐验证**
   - 检查 IMU / Planter 是否能在采后严格对齐到 Vicon 时间轴

3. **训练数据重建流程验证**
   - 检查最终导出的训练数据是否比当前正式主程序更可信

---

## 后续建议

等你验证路线 2 能跑通后，下一步建议：

1. 为 `capture_session.py` 增加更多会话元数据记录
2. 增加对齐质量统计（匹配率、延迟分布、丢弃率）
3. 增加更严格的数据验收脚本
4. 对比路线 1（当前正式主程序）与路线 2（绝对时间戳采集 + 采后重采样）的最终训练数据质量
