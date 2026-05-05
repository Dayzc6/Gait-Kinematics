# Feature Aggregator
# input：AC 的隐藏层特征
# output：注入 KR 的融合特征
import torch as t
import torch.nn as nn
import pandas as pd
import numpy as np
from config import Hidden_dim
from KR import Temp_kr_dim

class FAN(nn.Module):
    def __init__(self,hidden_dim=Hidden_dim,kr_dim_list=Temp_kr_dim):
        super().__init__()
        self.conv_1x1=nn.Conv1d(hidden_dim,hidden_dim,kernel_size=1)
        self.FAN_ReLU=nn.ReLU()
        self.kr_dim=None
        self.conv_KROut=nn.Conv1d(hidden_dim,self.kr_dim,kernel_size=1)

    def forward(self,x,kr_dim):
        out=self.conv_1x1(x)
        out=self.FAN_ReLU(out)
        out=x + out
        return self.conv_KROut(out)

        

