# Vicon 实验验证项目

本文件夹用于验证 **Vicon 单链路接收质量**，并作为正式主程序重构后的性能回归基线。

与正式主程序不同，`experiments/` 追求的是：

- 尽量短的 Vicon 调用链路
- 尽量少的同步/写盘干扰
- 明确区分 frame-only / segment-only / marker-only / baseline 的性能差异

因此，实验结果主要用于回答：

1. 当前 Vicon DataStream 基础接收是否能接近 **100Hz**
2. Segment / Marker 查询是否会显著拖慢接收
3. 某些主循环设计（例如固定 sleep）是否会影响接收性能
4. 正式主程序出现掉帧时，问题是来自 **Vicon 单链路** 还是来自 **正式系统整体负载**

---

## 实验脚本说明

### 实验0：baseline 全量字段
文件：`exp0_baseline_full_marker.py`

- 获取 `frame_num + recv_timestamp + 全量 marker`
- 用于与正式主程序中的 Vicon 质量对照
- 如果该实验接近 100Hz，而正式主程序明显更差，则说明问题更偏向正式系统整体负载，而不是 Vicon 基础接收本身

### 实验1：frame-only
文件：`exp1_frame_only.py`

- 只获取 `frame_num + recv_timestamp`
- 不读取任何 segment / marker
- 用于验证 SDK / 网络 / `GetFrame()` 基础拉流能力
- 会打印运行时诊断信息，例如 `GetFrameRate()`、subject 数量等

### 实验2：segment-only
文件：`exp2_segment_only.py`

- 获取 `frame_num + recv_timestamp + 全量 segment`
- 不读取 marker
- 用于判断 Segment 查询链路是否存在额外阻塞或偶发长耗时

### 实验3：marker-only
文件：`exp3_marker_only.py`

- 获取 `frame_num + recv_timestamp + 全量 marker`
- 不读取 segment
- 用于判断 Marker 查询成本相对 frame-only 的影响

### 实验4：frame-only + 固定 sleep
文件：`exp4_frame_only_with_sleep.py`

- 在 frame-only 基础上，每次成功 `GetFrame()` 后额外 `sleep(0.001)`
- 用于模拟旧 `worker_vicon.py` 中的固定休眠逻辑是否显著影响吞吐

### 实验5：frame-only + 预缓存 subject
文件：`exp5_frame_only_subject_cached.py`

- 采集前先获取一次 `subject_name`
- 正式采集阶段仍只记录 `frame_num + recv_timestamp`
- 用于判断 subject 查询 / 诊断调用本身是否影响 frame-only 结果

---

## 推荐执行顺序

建议在 Vicon_SDK 环境中，优先按以下顺序执行：

```bash
python experiments/exp1_frame_only.py
python experiments/exp4_frame_only_with_sleep.py
python experiments/exp5_frame_only_subject_cached.py
python experiments/exp2_segment_only.py
python experiments/exp3_marker_only.py
python experiments/exp0_baseline_full_marker.py
```

### 原则
- 每组实验固定 20 秒
- 使用同一 subject
- 使用同一网络环境
- Vicon 主机设置保持不变
- 每次实验单独运行，不要同时启动正式主程序

结果 CSV 默认保存到：

```text
experiments/data/
```

---

## 结果分析

单个文件分析：

```bash
python experiments/analyze_results.py experiments/data/xxx.csv
```

重点关注：

- `rows`
- `first_frame`
- `last_frame`
- `frame_span`
- `gap_rows`
- `gap_sum`
- `effective_hz`
- `diff_counter_top10`

---

## 判读原则

### 1. frame-only 是否接近 100Hz
如果 `exp1_frame_only` 已经能达到接近 100Hz，说明：

- Vicon SDK 基础接收链路本身是健康的
- 正式主程序如果仍掉到 80Hz 左右，更可能是正式系统总负载问题，而不是 Vicon 单链路本身的问题

### 2. segment-only / marker-only / baseline 是否比 frame-only 明显差
如果：
- frame-only 很稳
- marker-only 和 baseline 也很稳
- 但 segment-only 明显差

则说明问题更偏向 Segment 查询链路。

### 3. 实验4是否明显比实验1更差
如果 `exp4_frame_only_with_sleep` 明显更差，说明固定 `sleep(0.001)` 会显著吞掉接收预算。

如果差异很小，则说明固定 sleep 不是主因。

### 4. 实验5是否与实验1基本一致
如果 `exp5_frame_only_subject_cached` 与 `exp1_frame_only` 差异很小，说明：

- 预缓存 subject
- 少量诊断调用

并不是基础接收性能的主要影响因素。

### 5. 正式主程序与 experiments 的关系
如果 experiments 中：
- frame-only、marker-only、baseline 都接近 100Hz

而正式主程序中：
- `synced.csv` 的 effective_hz 明显下降
- gap 明显增大

则说明：

> 问题不在 Vicon 单链路，而在正式系统整体架构负载（例如 IMU/Planter 接入、SyncEngine 匹配、WriterWorker 写盘等）。

---

## 使用建议

- `experiments/` 不是正式业务采集入口，而是 **Vicon 性能与质量基线**
- 每次正式架构改动后，建议至少回归：
  - `exp1_frame_only.py`
  - `exp3_marker_only.py`
  - `exp0_baseline_full_marker.py`
- 只有在这些实验仍保持接近 100Hz 时，才说明正式程序遇到的问题主要来自系统集成层，而不是 Vicon 基础接收层

---

## 当前推荐定位思路

当正式程序出现以下现象时：

- 跳帧增多
- effective_hz 掉到 80Hz 左右
- `Vicon_Gap_Flag` / `Vicon_Gap_Size` 明显增加

建议先做：

1. 重新运行 `exp1_frame_only.py`
2. 再运行 `exp0_baseline_full_marker.py`
3. 对照正式 `synced.csv` 的结果

如果实验仍稳、正式程序不稳，则说明应优先优化正式程序架构，而不是怀疑 Vicon SDK 基础接收。
