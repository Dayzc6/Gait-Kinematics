# AIL-KE 步态参数识别系统

## 项目简介

本项目是论文 **"Learning-based 3D human kinematics estimation using behavioral constraints from activity classification"** (Kim et al., 2025, Nature Communications) 的复现与改进实现。

原文献提出的 **AIL-KE (Activity-in-the-loop Kinematics Estimator)** 模型通过将活动分类（AC）与运动学回归（KR）相结合，利用人类行为约束提升IMU（惯性测量单元）数据的运动学估计精度。本项目将原文献的动作识别任务迁移至**步态参数识别领域**，实现了：

- **步态相位识别**（AC模块）：识别左脚支撑期、右脚支撑期、双支撑期
- **步态参数预测**（KR-Kinematics模块）：预测步频、步长、步速、步宽等13个步态参数
- **关节角度预测**（KR-Joint模块）：预测躯干、髋、膝、踝等7个关节角度

## 参考文献

```
Kim, D., Jin, Y., Cho, H., Jones, T., Zhou, Y. M., Fadaie, A., ... & Walsh, C. J. (2025). 
Learning-based 3D human kinematics estimation using behavioral constraints from activity classification. 
Nature Communications, 16, 3454. https://doi.org/10.1038/s41467-025-58624-6
```

**核心思想**：
- 人类运动虽具有高维度特性，但在特定活动中表现出有限的模式和较低的变异性
- 通过AC模块提取活动分类信息作为行为约束，通过FAN网络注入KR模块，引导运动学回归
- 采用堆叠空洞卷积神经网络（DCNN）处理时序IMU数据

## 系统架构

### 整体结构

```
AIL-KE/
├── AC (Activity Classifier)          # 活动分类器
│   ├── Conv1d(In_dim → Hidden_dim)   # 输入投影
│   ├── 2× DCStack (各含10层DC)       # 空洞卷积堆叠
│   └── Conv1d(Hidden_dim → AC_dim)   # 分类输出头
│
├── FAN (Feature Aggregation Network) # 特征聚合网络
│   ├── 1×1 Conv + ReLU + Residual    # 残差连接
│   └── 1×1 Conv                      # 输出适配KR
│
└── KR (Kinematics Regressor)         # 运动学回归器
    ├── Conv1d(In_dim → Hidden_dim)   # 输入投影
    ├── 2× DCStack (各含10层DC)       # 空洞卷积堆叠
    │   └── 每层注入FAN(AC特征)        # 行为约束注入
    └── Conv1d(Hidden_dim → KR_dim)   # 回归输出头
```

### 关键模块说明

**1. DC (Dilated Convolution) 空洞残差层**
- 每层空洞率：2^i (i=0,1,...,9)
- 卷积核大小：3
- 最大感受野：2^9 = 512（覆盖整个窗口）
- 包含残差连接：x + conv_dilated → ReLU → conv_1x1

**2. AC模块（Activity Classifier）**
- 输入：IMU数据 (63通道 × 512时间步)
- 输出：步态相位 (3类 × 512时间步)
- 损失函数：CrossEntropyLoss
- 当前准确率：94.33%（验证集）

**3. KR-Kinematics模块**
- 输入：IMU数据 + FAN注入的AC特征
- 输出：13个步态参数 (13通道 × 512时间步)
- 损失函数：MSELoss
- 主要参数：步频、步长、步速、步宽、支撑期百分比等

**4. KR-Joint模块**
- 输入：IMU数据 + FAN注入的AC特征
- 输出：7个关节角度 (7通道 × 512时间步)
- 损失函数：MSELoss
- 主要参数：躯干角、髋角、膝角、踝角

## 数据结构

### 输入数据（IMU特征）

**数据来源**：7个惯性测量单元（IMU），采样率100Hz

**每个IMU包含3类数据**：
- `ang`：角度（3轴）
- `vel`：角速度（3轴）
- `acc`：加速度（3轴）

**总输入维度**：(3 + 3 + 3) × 7 = **63维**

**IMU分布**：
```
imu1-imu7：分别佩戴于身体不同部位
```

### 输出标签

**1. AC标签（步态相位分类）**
- 0: 左脚支撑期
- 1: 右脚支撑期
- 2: 双支撑期

**2. KR-Kinematics标签（13维步态参数）**
| 参数名 | 单位 | 说明 |
|--------|------|------|
| left_pct_stance | % | 左脚支撑期百分比 |
| left_pct_swing | % | 左脚摆动期百分比 |
| right_pct_stance | % | 右脚支撑期百分比 |
| right_pct_swing | % | 右脚摆动期百分比 |
| step_frequency | steps/min | 步频 |
| step_length | cm | 步长 |
| left_step_length | cm | 左步长 |
| right_step_length | cm | 右步长 |
| left_stride_length | cm | 左跨步长 |
| right_stride_length | cm | 右跨步长 |
| left_step_speed | m/s | 左步速 |
| right_step_speed | m/s | 右步速 |
| step_width | cm | 步宽 |

**3. KR-Joint标签（7维关节角度）**
| 参数名 | 单位 | 说明 |
|--------|------|------|
| torso_angle | ° | 躯干角度 |
| left_hip_angle | ° | 左髋关节角度 |
| left_knee_angle | ° | 左膝关节角度 |
| left_ankle_angle | ° | 左踝关节角度 |
| right_hip_angle | ° | 右髋关节角度 |
| right_knee_angle | ° | 右膝关节角度 |
| right_ankle_angle | ° | 右踝关节角度 |

### 数据文件格式

**原始数据**：`data/data_csv/`
- 文件名格式：`{速度}kmh{试验编号}_merged.csv`
- 示例：`1.8kmh1_merged.csv`, `5.4kmh0_merged.csv`
- 每文件约10,000帧（100秒 @ 100Hz）
- 总列数：182列（包含IMU、关节角、步态参数、Vicon标记点等）

**数据预处理**：
1. `data/process_gait_labels.py`：根据步态周期生成相位标签
2. `data/rename_columns.py`：将中文列名标准化为英文
3. `data/dataset.py`：滑动窗口切分、归一化、数据集划分

**滑动窗口设置**：
- 窗口大小：512帧（5.12秒）
- 步长：50帧（0.5秒，重叠率90%）
- 划分比例：训练70% / 验证15% / 测试15%

## 环境配置

### 硬件要求

- **GPU**：NVIDIA GPU（推荐，支持CUDA）
- **显存**：≥ 4GB
- **内存**：≥ 16GB
- **存储**：≥ 5GB（含数据集）

### 软件环境

| 依赖项 | 版本 | 说明 |
|--------|------|------|
| Python | 3.10+ | 编程语言 |
| PyTorch | 2.0+ | 深度学习框架 |
| CUDA | 11.8+ | GPU加速（可选） |
| pandas | 1.5+ | 数据处理 |
| numpy | 1.24+ | 数值计算 |
| scikit-learn | 1.3+ | 评估指标 |
| matplotlib | 3.7+ | 绘图可视化 |
| seaborn | 0.12+ | 统计可视化 |

### 安装依赖

```bash
# 创建conda环境
conda create -n ail-ke python=3.10
conda activate ail-ke

# 安装PyTorch（带CUDA）
conda install pytorch torchvision torchaudio pytorch-cuda=11.8 -c pytorch -c nvidia

# 安装其他依赖
pip install pandas numpy scikit-learn matplotlib seaborn
```

### 项目目录结构

```
AIL-KE/
├── config.py                    # 全局配置参数
├── trainer.py                   # 主训练脚本（三阶段训练）
├── evaluate.py                  # AC模块评估
├── evaluate_kr.py              # KR模块评估与可视化
├── data/
│   ├── dataset.py              # PyTorch Dataset与DataLoader
│   ├── process_gait_labels.py  # 步态相位标签生成
│   ├── rename_columns.py       # 列名标准化
│   └── data_csv/               # 原始CSV数据文件
├── models/
│   ├── __init__.py             # 模块导出
│   ├── MainModel.py            # 统一模型（AC+FAN+KR）
│   ├── AC.py                   # 活动分类器
│   ├── KR.py                   # 运动学回归器（基类）
│   ├── KR_Kinematics.py        # 步态参数回归
│   ├── KR_Joint.py             # 关节角度回归
│   ├── FAN.py                  # 特征聚合网络
│   ├── DC.py                   # 空洞卷积模块
│   └── loss_functions.py       # 损失函数定义
├── reference/
│   ├── Kim et al. 2025.pdf     # 参考文献
│   └── upload_to_kimi.py       # PDF上传工具
├── checkpoint/                 # 模型检查点保存目录
└── report/                     # 评估报告与可视化结果
```

## 使用说明

### 1. 数据准备

确保 `data/data_csv/` 目录下包含所有CSV数据文件，文件命名格式为 `{速度}kmh{编号}_merged.csv`。

### 2. 训练模型

```bash
# 完整三阶段训练
python trainer.py
```

**训练流程**：
1. **阶段1**：AC模块预训练（500 epochs，早停机制）
2. **阶段2a**：KR-Kinematics训练（1000 epochs，固定AC权重）
3. **阶段2b**：KR-Joint训练（1000 epochs，固定AC权重）

**训练输出**：
- `checkpoint/phase1_ac.pt`：AC模块权重
- `checkpoint/phase2_kinematics.pt`：KR-Kinematics完整权重
- `checkpoint/phase2_joint.pt`：KR-Joint完整权重
- `checkpoint/loss_curve_*.png`：训练损失曲线

### 3. 评估模型

```bash
# AC模块评估（混淆矩阵、准确率）
python evaluate.py

# KR模块评估（RMSE、MAE、可视化对比图）
python evaluate_kr.py
```

**评估输出**：
- 终端：各参数RMSE、MAE、相对误差
- `report/kinematics_time_series.png`：步态参数时序对比
- `report/kinematics_scatter.png`：步态参数散点图
- `report/kinematics_error_boxplot.png`：步态参数误差分布
- `report/joint_time_series.png`：关节角度时序对比
- `report/joint_scatter.png`：关节角度散点图
- `report/joint_error_boxplot.png`：关节角度误差分布

## 核心配置参数

详见 `config.py`：

| 参数 | 值 | 说明 |
|------|-----|------|
| num_layers | 10 | 每个DCStack的空洞卷积层数 |
| Kernel_size | 3 | 卷积核大小 |
| Hidden_dim | 64 | 隐藏层维度 |
| stacks | 2 | DCStack堆叠次数 |
| In_dim | 63 | IMU输入维度 |
| AC_dim | 3 | 步态相位类别数 |
| KR_Kinematics_dim | 13 | 步态参数维度 |
| KR_Joint_dim | 7 | 关节角度维度 |
| lr | 1e-4 | 学习率 |
| wd | 1e-4 | 权重衰减（L2正则化） |
| batch_size | 100 | 批次大小 |
| AC_epochs | 500 | AC训练轮数 |
| KR_epochs | 1000 | KR训练轮数 |

## 当前性能指标

### AC模块（步态相位分类）
- **验证准确率**：
- **早停轮数**：
- **各类别F1-score**：

### KR-Kinematics模块（步态参数回归）
- **整体RMSE**：
- **整体MAE**：
- **最佳参数**：
- **待优化**：

### KR-Joint模块（关节角度回归）
- **整体RMSE**：
- **整体MAE**：
- **最佳关节**：
- **待优化**：

## 关键技术要点

### 1. 序列到序列（Seq2Seq）设计
不同于原文献的单标签分类，本项目采用**每个时间步都有标签**的序列预测方式。一个512帧的窗口包含约8-10个完整步态周期，模型需要输出每个时间步的相位/参数。

### 2. 标签归一化策略
- **IMU特征**：z-score标准化（零均值、单位方差）
- **KR训练标签**：z-score标准化，加速收敛
- **KR评估标签**：反归一化到原始物理单位，保证可解释性

### 3. 三阶段训练策略
严格遵循文献：
1. 先训练AC至收敛（活动分类准确）
2. 固定AC权重，训练KR（防止AC退化）
3. 可选：联合微调（本项目已实现框架）

### 4. Early Stopping
- 耐心值：50 epochs
- 监控指标：验证集损失
- 保存最佳模型，防止过拟合

## 常见问题

**Q: 训练时出现 `RuntimeError: Input type and weight type should be the same`**
A: 确保模型和数据都在同一设备上（CPU/GPU）。已在代码中统一使用 `DEVICE` 配置。

**Q: 如何调整窗口大小？**
A: 修改 `config.py` 或 `dataset.py` 中的 `window_size` 参数。注意窗口大小应大于最大空洞率（512）。

**Q: 可以只训练AC模块吗？**
A: 可以。在 `trainer.py` 中注释掉阶段2a/2b的代码即可。

**Q: 如何添加新的步态参数？**
A: 修改 `dataset.py` 中的 `kr_kinematics_labels` 列表和 `config.py` 中的 `KR_Kinematics_dim`。

## 作者与致谢

- **原始论文作者**：Kim et al. (Harvard University, Korea University)
- **复现与改进**：本项目团队
- **指导框架**：基于PyTorch 2.0实现

## 许可证

本项目仅供学术研究使用。原始论文的代码和数据遵循Nature Communications的开放获取政策。

---

**最后更新**：2026年5月
