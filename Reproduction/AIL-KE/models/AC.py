# Activity Classifier
# input：加速度、角速度、角度
# output：相位识别
import torch as t
import torch.nn as nn
import pandas as pd
import numpy as np
from models import DC
from config import In_dim
from config import AC_dim
from config import Hidden_dim
from config import stacks

# AC需要4个DC进行堆叠
# 也就是说，需要循环四次
class Model_AC(nn.Module):
    def __init__(self,in_dim=In_dim,ac_dim=AC_dim,hidden_dim=Hidden_dim):
        super().__init__()
        self.conv_in=nn.Conv1d(in_channels=in_dim,out_channels=hidden_dim,kernel_size=1)

        # self.layer=DC.DilatedResidualLayer()：在 PyTorch 中，nn.Conv1d 的 dilation 是在初始化（__init__）时固定的。
        # 你不能在 forward 时像调用普通函数一样动态更改它。
        # 这会导致模型无法构建计算图，或者所有层都在使用同一个卷积核。
        # 所以：预定义所有的扩张层，存入ModuleList
        self.ac_stacks=nn.ModuleList([DC.DCStack(hidden_dim) for _ in range(stacks)])

      
        # 这个应该是4个堆叠完后输出的分类用的output，最后一个堆叠完后才使用分类维度
        self.conv_out=nn.Conv1d(in_channels=hidden_dim,out_channels=ac_dim,kernel_size=1)

        # self.init=True
        # 深度学习模型在一个 Epoch 中会处理成千上万个 Batch。
        # 你设置 self.init=False 后，除了第一个 Batch 的第一帧，其余所有数据都会跳过 conv_in。
        # 这将导致输入维度不匹配，程序直接报错崩溃。

    def forward(self,x):
        # x.shape
        ac_out=self.conv_in(x)
        # ac_out.shape
        for ac_stack in self.ac_stacks:
            ac_out=ac_stack(ac_out)
        ac_out=self.conv_out(ac_out)
        return ac_out[:,:,-1] # 单标签，只取最后一个时间步: (batch, 3)
                

        
        

