# 膨胀残差层 (Dilated Residual Layer)
import torch as t
import torch.nn as nn
import pandas as pd
import numpy as np
import sys
from config import Kernel_size
from config import Hidden_dim
from config import in_dim

# 定义单个膨胀残差层
# dilation:膨胀参数
class DilatedResidualLayer(nn.Module):
    def __init__(self,dilation,in_channels=Hidden_dim,out_channels=Hidden_dim):
        super().__init__()

        # 膨胀1D卷积，卷积核大小为3
        self.conv_dilated=nn.Conv1d(in_channels,out_channels,kernel_size=Kernel_size,padding=dilation,dilation=dilation)

        # ReLU激活
        self.ReLu=nn.ReLU()

        # 1x1 卷积用于调整通道或增加非线性
        self.conv_1x1=nn.Conv1d(out_channels,out_channels,kernel_size=1)
        # self.dropout=nn.Dropout()

    def forward(self,x):
        out=self.conv_dilated(x)
        out=self.ReLu(out)
        out=self.conv_1x1(out)
        # out=self.dropout(out)
        return x + out




        
        