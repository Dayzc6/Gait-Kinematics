# Kinematics Regressor
# input：同AC的输入特征加速度、角速度、（四元数） + FAN 注入的特征
# output：速度/轨迹 或 关节角度
import torch as t
import torch.nn as nn
import pandas as pd
import numpy as np
import DC
from config import In_dim,KR_dim
from config import Hidden_dim
from config import num_layers

class Model_KR(nn.Module):
    def __init__(self,in_dim=In_dim,hidden_dim=Hidden_dim,kr_dim=KR_dim):
        super().__init__()
        self.conv_in=nn.Conv1d(in_channels=in_dim,out_channels=hidden_dim,kernel_size=1)

        # 预定义所有的扩张层，存入ModuleList
        self.layers=nn.ModuleList([
            DC.DilatedResidualLayer(dilation=2**i,in_channels=hidden_dim,out_channels=hidden_dim)
            for i in range(num_layers)
        ])
        
        self.conv_out=nn.Conv1d(in_channels=hidden_dim,out_channels=kr_dim,kernel_size=1)

    def Temp_kr_dim(self,x):
        temp_tensor=t.zeros(x)
        temp_kr_dim_list=[]
        for layer in self.layers:
            temp_tensor=layer(temp_tensor)
            temp_kr_dim=temp_tensor.shape(1)
            temp_kr_dim_list.append(temp_kr_dim)
        return temp_kr_dim_list

    def forward(self,x):
        out=self.conv_in(x)
        for layer in self.layers:
            out=layer(out)
            temp_kr_dim=out.shape(1)
            
        out=self.conv_out(out)
        return out
    