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

kr_joint_labels=[
    'torso_angle',
    'left_hip_angle',
    'left_knee_angle',
    'left_ankle_angle',
    'right_hip_angle',
    'right_knee_angle',
    'right_ankle_angle'
]

kr_kinematics_labels=[
    'left_pct_stance',
    'left_pct_swing',
    'right_pct_stance',
    'right_pct_swing',
    'step_frequency',
    'step_length',
    'left_step_length',
    'right_step_length',
    'left_stride_length',
    'right_stride_length',
    'left_step_speed',
    'right_step_speed',
    'step_width',
    'cycle_time'
]


class IMUDataset(Dataset):
    def __init__(self, all_data=all_data, window_size=512, stride=50):    
        """
        window_size: 滑动窗口的大小（时间步长）
        stride: 窗口移动的步长（重叠度由 window_size - stride 决定）
        注意：由于目标文献的动作识别类型以及输出不同（相位识别和模式识别不同），window_size要重新设计
        """        
        self.data=pd.concat(all_data, ignore_index=True)  # 合并所有数据
        self.window_size=window_size
        self.stride=stride

        # 提取IMU特征
        imu_cols=[c for c in self.data.columns if c.startswith('imu')]
        self.features=self.data[imu_cols].values

        # 归一化
        # IMU数据的加速度、角速度、角度量纲完全不同（加速度±2g，角速度±500°/s，角度~±180°），
        # 不归一化会导致梯度爆炸/消失。
        self.mean=self.features.mean(axis=0) 
        self.std=self.features.std(axis=0) + 1e-8           # 加极小值防止除零
        self.features=(self.features-self.mean)/self.std

        # 提取标签
        self.ac_labels=self.data['phase_label'].values      # 相位预测标签
        self.kr_kinematics_labels=self.data[kr_kinematics_labels].values  # 步态参数标签
        self.kr_joint_labels=self.data[kr_joint_labels].values            # 关节参数标签

        # 滑动窗口切分
        self.windows=[]
        # self.window_labels=[] 单标签
        self.window_labels_ac_seq=[]
        self.window_labels_kr_kinematics_seq=[]
        self.window_labels_kr_joint_seq=[]

        for i in range(0,len(self.features)-window_size,stride):
            # self.windows.append(self.features[i+window_size-1])
            self.windows.append(self.features[i:i+window_size])
            # self.windows已经是 (N, window_size, In_dim)
            # print(np.shape(self.windows))

            # 标签取窗口最后一个时刻的标签（或多数投票）
            # 标签取窗口最后一个时刻和完整取完有什么区别？
            # 如果目标是实时知道当前处于步态周期的哪个相位，用单标签（最后时刻）更合理且计算简单；
            # 由于一个样本的时间过长以及步态周期中相位变化过快，不适用于单标签
            # self.window_labels.append(self.ac_labels[i+window_size-1])

            # 如果需要重建整个步态周期的连续变化，才用序列标签。
            # 复现模型更适合用seq2seq
            self.window_labels_ac_seq.append(self.ac_labels[i:i+window_size])
            self.window_labels_kr_kinematics_seq.append(self.kr_kinematics_labels[i:i+window_size])
            self.window_labels_kr_joint_seq.append(self.kr_joint_labels[i:i+window_size])


    # 返回数据集大小
    def __len__(self):
        return len(self.windows)
    
    # 获取单个样本
    # 这个地方我不懂，__getitem__的作用是什么？index是什么意思？它要输入什么？输出什么？到哪里去？
    def __getitem__(self, index):
        # pandas 读取的 numpy 数组默认是只读的，torch.LongTensor() 对这种数组有兼容性问题。
        # 返回 (特征tensor, 标签tensor)
        # 模型输出应该是：(batch, 3, window_size)（Conv1d保持序列长度）
        # 注意：PyTorch的CrossEntropyLoss需要标签是 1D LongTensor
        
        # x=t.FloatTensor(self.windows[index])                # (512, 63)
        x=t.tensor(self.windows[index],dtype=t.float32)


        # y=t.tensor(self.window_labels[index],dtype=t.long)  # 标量，不是列表
        # 我们采用固定窗口+序列预测
        # start=index*self.stride
        # 
        # y=self.ac_labels[start:start+self.window_size]
        y_ac_seq=self.window_labels_ac_seq[index]
        # y_seq=t.LongTensor(y_seq)
        y_ac_seq=t.tensor(y_ac_seq,dtype=t.long)

        # kr_kinematics
        y_kr_kinematics_seq=self.window_labels_kr_kinematics_seq[index]
        y_kr_kinematics_seq=t.tensor(y_kr_kinematics_seq,dtype=t.long)

        # kr_joint
        y_kr_joint_seq=self.window_labels_kr_joint_seq[index]
        y_kr_joint_seq=t.tensor(y_kr_joint_seq,dtype=t.long)


        # ⚠️ 重要：PyTorch的CNN/Conv1d expects input of shape [batch, channels, length]
        # 所以需要转置： [window_size, 63] -> [63, window_size]
        x = x.T
        
        return x, y_ac_seq, y_kr_kinematics_seq, y_kr_joint_seq

# 这个函数应该写在class中吗？
def  get_dataloaders(batch_size=100,window_size=512,stride=50):
    # 数据集划分
    # 训练:验证:测试 = 0.7:0.15:0.15
    dataset=IMUDataset(window_size=window_size,stride=stride)

    train_size = int(0.7 * len(dataset))
    val_size = int(0.15 * len(dataset))
    test_size = len(dataset) - train_size - val_size

    train_dataset, val_dataset, test_dataset = random_split(
        dataset, # 传入Dataset，不是Tensor
        [train_size, val_size, test_size],
        generator=t.Generator().manual_seed(42)  # 固定随机种子，保证可复现
    )

    # 创建DataLoader
    train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True)
    val_loader = DataLoader(val_dataset, batch_size=batch_size, shuffle=False)
    test_loader = DataLoader(test_dataset, batch_size=batch_size, shuffle=False)

    return train_loader, val_loader, test_loader







        