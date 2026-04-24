# Vicon 实验验证项目

本文件夹用于验证 Vicon 丢帧根因，严格按四组基础实验 + 两组诊断实验执行。

## 实验目的

验证当前 Vicon 丢帧是否主要来自：
1. SDK / 网络基础拉流
2. Segment 查询成本
3. Marker 查询成本
4. Segment + Marker 全量读取组合成本
5. 主循环固定 sleep 是否显著降低吞吐
6. 运行时诊断调用是否改变 frame-only 表现

## 基础四组实验

### 实验0：baseline 全量字段
文件：`exp0_baseline_full_marker.py`
- 获取 frame_num + recv_timestamp + 全量 marker
- 用于与当前主系统结果对照

### 实验1：frame-only
文件：`exp1_frame_only.py`
- 只获取 frame_num + recv_timestamp
- 不读取任何 segment / marker
- 用于验证 SDK/网络基础拉流能力
- 额外打印 `GetFrameRate()`、subject 数量等运行时诊断

### 实验2：segment-only
文件：`exp2_segment_only.py`
- 获取 frame_num + recv_timestamp + 全量 segment
- 不读取 marker

### 实验3：marker-only
文件：`exp3_marker_only.py`
- 获取 frame_num + recv_timestamp + 全量 marker
- 不读取 segment

## 新增诊断实验

### 实验4：frame-only + 固定 sleep
文件：`exp4_frame_only_with_sleep.py`
- frame-only 基础上，在每次成功 `GetFrame()` 后 `sleep(0.001)`
- 用于模拟 `worker_vicon.py` 当前主循环尾部固定休眠的影响
- 如果该实验明显比实验1更差，说明固定 sleep 是重要次因

### 实验5：frame-only + 预缓存 subject
文件：`exp5_frame_only_subject_cached.py`
- 采集前先获取一次 `subject_name`
- 正式采集阶段仍只记录 frame_num + recv_timestamp
- 额外打印 `GetFrameRate()`、subject/marker/segment 数量
- 用于确认诊断调用本身是否显著影响 frame-only 结果

## 执行要求

- 每组实验固定 20 秒
- 同一 subject
- 同一网络环境
- Vicon 主机设置不变
- 每次实验单独运行，不要同时开主项目采集
- 建议优先执行：1 → 4 → 5，再决定是否补跑 2 / 3 / 0

## 执行命令

在 Vicon_SDK 环境中执行：

```bash
python experiments/exp1_frame_only.py
python experiments/exp4_frame_only_with_sleep.py
python experiments/exp5_frame_only_subject_cached.py
python experiments/exp2_segment_only.py
python experiments/exp3_marker_only.py
python experiments/exp0_baseline_full_marker.py
```

结果 CSV 会保存到：

```text
experiments/data/
```

## 结果分析

单个文件分析：

```bash
python experiments/analyze_results.py experiments/data/xxx.csv
```

## 判读原则

### 如果 `GetFrameRate()` 明显就是 100 左右，但 frame-only 仍只有 ~80Hz
说明主机目标输出正常，问题更偏向客户端接收 / SDK 调用语义 / 主循环吞吐。

### 如果实验4明显比实验1更差
说明固定 `sleep(0.001)` 会显著吞掉 100Hz 预算，是重要次因。

### 如果实验5与实验1几乎一致
说明少量诊断调用或预缓存 subject 对结论影响很小，主因仍是 `GetFrame()` 链路。

### 如果 frame-only 也丢很多
说明问题更偏向 SDK / 网络 / `GetFrame` 调用语义，不应优先优化字段读取。
