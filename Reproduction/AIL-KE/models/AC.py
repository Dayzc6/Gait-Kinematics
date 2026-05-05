# Activity Classifier
# input：加速度、角速度、（四元数）
# output：动作类别（如：深蹲、卧推）
import torch as t
import torch.nn as nn
import pandas as pd
import numpy as np
import DC
from config import In_dim
from config import AC_dim
from config import Hidden_dim
from config import num_layers

class Model_AC(nn.Module):
    def __init__(self,in_dim=In_dim,ac_dim=AC_dim,hidden_dim=Hidden_dim):
        super().__init__()
        self.conv_in=nn.Conv1d(in_channels=in_dim,out_channels=hidden_dim,kernel_size=1)

        # self.layer=DC.DilatedResidualLayer()：在 PyTorch 中，nn.Conv1d 的 dilation 是在初始化（__init__）时固定的。
        # 你不能在 forward 时像调用普通函数一样动态更改它。
        # 这会导致模型无法构建计算图，或者所有层都在使用同一个卷积核。
        # 所以：预定义所有的扩张层，存入ModuleList
        self.layers=nn.ModuleList([
            DC.DilatedResidualLayer(dilation=2**i,in_channels=hidden_dim,out_channels=hidden_dim)
            for i in range(num_layers)
        ])
        
        self.conv_out=nn.Conv1d(in_channels=hidden_dim,out_channels=ac_dim,kernel_size=1)

        # self.init=True
        # 深度学习模型在一个 Epoch 中会处理成千上万个 Batch。
        # 你设置 self.init=False 后，除了第一个 Batch 的第一帧，其余所有数据都会跳过 conv_in。
        # 这将导致输入维度不匹配，程序直接报错崩溃。

    def forward(self,x):
        out=self.conv_in(x)
        for layer in self.layers:
            out=layer(out)
        out=self.conv_out(out)
        return out
                

        
        

