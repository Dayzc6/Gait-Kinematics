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
from config import stacks

# KR需要4个DC进行堆叠
# KR的DC需要注入经过FAN处理后的AC特征
# 也就是说，需要循环四次

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

    def forward(self,x):
        out=self.conv_in(x)
        for layer in self.layers:

            out=layer(out)  
        # out=self.conv_out(out)
        return out
    