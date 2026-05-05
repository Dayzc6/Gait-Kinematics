# PyTorch Dataset类
# 数据载入器。实现滑动窗口（Sliding Window）切分，将长序列信号打包成训练批次（Batch），并负责训练集/验证集的随机划分。
import csv
import torch as t
import numpy as np
import pandas as pd
from torch.utils.data import Dataset, DataLoader, random_split

class IMUDataset(Dataset):
    def __init__(self, csv_file, window_size=512, stride=100):    
        """
        window_size: 滑动窗口的大小（时间步长）
        stride: 窗口移动的步长（重叠度由 window_size - stride 决定）
        """        
        data=pd.read_csv()
        