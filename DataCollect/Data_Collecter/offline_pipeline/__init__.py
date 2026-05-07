# -*- coding: utf-8 -*-
"""
offline_pipeline 路线 2 目录说明

目标：
- 在不增加正式采集阶段负载的前提下，记录 Vicon / IMU / Planter 的原始或最小必要数据
- 采集结束后，再统一进行解算、严格时间对齐与训练数据集生成

本目录用于逐步实现以下流程：
1. 轻量采集（capture）
2. 原始数据验证（validate）
3. 离线解算（decode）
4. 完整快照重建（build snapshots）
5. 严格同步对齐（align）
6. 训练数据导出（export）
"""
