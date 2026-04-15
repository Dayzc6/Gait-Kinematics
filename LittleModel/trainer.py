import torch as t
import numpy as np
import scipy as sci
import torch.nn as nn
import torch.optim as optim
import os
import pandas as pd
from pathlib import Path
from torch.nn import functional as F

device=t.device("cuda" if t.cuda.is_available() else "cpu")
print(f"device:{device}")

base_path=Path('E:\下肢外骨骼IMU测量\步态算法资料')
S038_path=base_path / 'S038'
# names=['','','']
file_name='S038_G01_D01_B01_T01' # 获取数据的文件名称

features=['waist_acceleration_x','waist_acceleration_y','waist_acceleration_z','waist_euler_x','waist_euler_y','waist_euler_z','waist_quaternion_x','waist_quaternion_y','waist_quaternion_z','waist_quaternion_w',
          'thigh_LT_acceleration_x','thigh_LT_acceleration_y','thigh_LT_acceleration_z','thigh_LT_euler_x','thigh_LT_euler_y','thigh_LT_euler_z','thigh_LT_quaternion_x','thigh_LT_quaternion_y','thigh_LT_quaternion_z','thigh_LT_quaternion_w',
          'thigh_RT_acceleration_x','thigh_RT_acceleration_y','thigh_RT_acceleration_z','thigh_RT_euler_x','thigh_RT_euler_y','thigh_RT_euler_z','thigh_RT_quaternion_x','thigh_RT_quaternion_y','thigh_RT_quaternion_z','thigh_RT_quaternion_w',
          'shank_LT_acceleration_x','shank_LT_acceleration_y','shank_LT_acceleration_z','shank_LT_euler_x','shank_LT_euler_y','shank_LT_euler_z','shank_LT_quaternion_x','shank_LT_quaternion_y','shank_LT_quaternion_z','shank_LT_quaternion_w',
          'shank_RT_acceleration_x','shank_RT_acceleration_y','shank_RT_acceleration_z','shank_RT_euler_x','shank_RT_euler_y','shank_RT_euler_z','shank_RT_quaternion_x','shank_RT_quaternion_y','shank_RT_quaternion_z','shank_RT_quaternion_w',          
          'foot_LT_acceleration_x','foot_LT_acceleration_y','foot_LT_acceleration_z','foot_LT_euler_x','foot_LT_euler_y','foot_LT_euler_z','foot_LT_quaternion_x','foot_LT_quaternion_y','foot_LT_quaternion_z','foot_LT_quaternion_w',
          'foot_RT_acceleration_x','foot_RT_acceleration_y','foot_RT_acceleration_z','foot_RT_euler_x','foot_RT_euler_y','foot_RT_euler_z','foot_RT_quaternion_x','foot_RT_quaternion_y','foot_RT_quaternion_z','foot_RT_quaternion_w'          
          ]

# 数据获取模块
class Data_Get():
    def __init__(self,data_path,file_name):
        # 
        full_path=data_path / f"{file_name}.csv"
        try:
            self.df=pd.read_csv(full_path)
        except FileNotFoundError:
            print('Not Found')
            self.df=None

    def data_read(self,features):
        if self.df is None:
            return None
        
        select_data=self.df[features]

        return select_data.to_numpy()
        
# 卷积模块
class MixModel(nn.Module):
    def __init__(self):
        super.__init__()
        self.layer1=nn.Conv1d()
        self.layer2=nn.Conv1d()
        self.layer3=nn.Conv1d()

    def forward(self,x):
        return self.layer1(x)
    
# LSTM模块


if __name__ == "__main__":
    # net=MixModel()
    # S038_path=base_path / 'S038'
    # names=['','','']
    # file_name='S038_G01_D01_B01_T01' # 获取数据的文件名称
    loader=Data_Get(S038_path,file_name)
    imu_matrix=loader.data_read(features)

    if imu_matrix is not None:
        print(f"数据矩阵：{imu_matrix}，{type(imu_matrix)}")
    
    

