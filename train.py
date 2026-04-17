# conda activate gait_kinematics
# 步态运动学构建总程序
# 训练主循环。负责模型初始化、优化器配置、学习率衰减以及在每个 Epoch 后的模型保存。
import numpy as np
import pandas as pd
import torch


# if __name__ == "__main__":

