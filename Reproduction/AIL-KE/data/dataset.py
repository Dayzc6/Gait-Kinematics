# PyTorch Dataset类
# 数据载入器。实现滑动窗口（Sliding Window）切分，将长序列信号打包成训练批次（Batch），并负责训练集/验证集的随机划分。
import csv
import os
import glob
import torch as t
import numpy as np
import pandas as pd
from config import In_dim
from torch.utils.data import Dataset, DataLoader, random_split

data_dir=r'E:\code\3D-position\Reproduction\AIL-KE\data\data_csv'
csv_files=glob.glob(os.path.join(data_dir, "*_merged.csv"))
# 如果我希望是将data_csv中的数据都导入到其中，应该怎么写入？都打开然后拼接在一起吗？还是说训练只需要一个数据集就够用了？

all_data=[]
for csv_file in csv_files:
    df=pd.read_csv(csv_file)
    all_data.append(df)
    

class IMUDataset(Dataset):
    def __init__(self, all_data=all_data, window_size=512, stride=100):    
        """
        window_size: 滑动窗口的大小（时间步长）
        stride: 窗口移动的步长（重叠度由 window_size - stride 决定）
        """        
        self.data=pd.concat(all_data, ignore_index=True)  # 合并所有数据
        
        # 提取特征
        imu_cols=[c for c in self.data.columns if c.startswith('imu')]
        self.features=self.data[imu_cols].values

        # 归一化
        # IMU数据的加速度、角速度、角度量纲完全不同（加速度±2g，角速度±500°/s，角度~±180°），
        # 不归一化会导致梯度爆炸/消失。
        self.mean=self.features.mean(axis=0) 
        self.std=self.features.std(axis=0)
        self.features=(self.features-self.mean)/self.std

        # 提取标签
        self.ac_labels=self.data['phase_label'].values

        # 滑动窗口切分
        self.windows=[]
        self.window_labels=[]
        for i in range(0,len(self.features)-window_size,stride):
            # self.windows.append(self.features[i+window_size-1])
            self.windows.append(self.features[i:i+window_size])
            print(np.shape(self.windows))

            # 标签取窗口最后一个时刻的标签（或多数投票）
            # 标签取窗口最后一个时刻和完整取完有什么区别？
            # 如果目标是实时知道当前处于步态周期的哪个相位，用单标签（最后时刻）更合理且计算简单；
            # 如果需要重建整个步态周期的连续变化，才用序列标签。
            self.window_labels.append(self.ac_labels[i+window_size-1])
            # self.window_labels.append(self.ac_labels[i:window_size])


    # 返回数据集大小
    def __len__(self):
        return len(self.windows)
    
    # 获取单个样本
    # 这个地方我不懂，__getitem__的作用是什么？index是什么意思？它要输入什么？输出什么？到哪里去？
    def __getitem__(self, index):
        # 返回 (特征tensor, 标签tensor)
        # 模型输出应该是：(batch, 3, window_size)（Conv1d保持序列长度）
        # 注意：PyTorch的CrossEntropyLoss需要标签是 1D LongTensor
        x=t.FloatTensor(self.windows[index])
        y=t.LongTensor([self.window_labels[index]])

        # ⚠️ 重要：PyTorch的CNN/Conv1d expects input of shape [batch, channels, length]
        # 所以需要转置： [window_size, 63] -> [63, window_size]
        x = x.T
        
        return x, y
    
    def dataset_trans(self):
        data_tensor=t.FloatTensor(self.windows)
        print(data_tensor.shape)
        data_len=self.__len__()
        data_tensor=data_tensor.reshape(data_len,In_dim,1)  # 这个复现项目中的N，C，L都是什么？L是stride吗？还是Batch_size?
        print(data_tensor.shape)
        return data_tensor

# 这个函数应该写在class中吗？
def get_dataloaders(batch_size=100,window_size=512,stride=100):
    # 数据集划分
    # 训练:验证:测试 = 0.7:0.15:0.15
    dataset=IMUDataset(window_size=window_size,stride=stride).dataset_trans()

    train_size = int(0.7 * len(dataset))
    val_size = int(0.15 * len(dataset))
    test_size = len(dataset) - train_size - val_size

    train_dataset, val_dataset, test_dataset = random_split(
        dataset, 
        [train_size, val_size, test_size],
        generator=t.Generator().manual_seed(42)  # 固定随机种子，保证可复现
    )

    # 创建DataLoader
    train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True)
    val_loader = DataLoader(val_dataset, batch_size=batch_size, shuffle=False)
    test_loader = DataLoader(test_dataset, batch_size=batch_size, shuffle=False)

    return train_loader, val_loader, test_loader







        