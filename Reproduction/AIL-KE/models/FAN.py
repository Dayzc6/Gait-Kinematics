# Feature Aggregator
# input：AC 的隐藏层特征
# output：注入 KR 的融合特征
import torch as t
import torch.nn as nn
import pandas as pd
import numpy as np
from config import Hidden_dim

class Model_FAN(nn.Module):
    def __init__(self,hidden_dim=Hidden_dim):
        super().__init__()
        self.conv_1x1=nn.Conv1d(hidden_dim,hidden_dim,kernel_size=1)
        self.FAN_ReLU=nn.ReLU()
        self.conv_KROut=nn.Conv1d(hidden_dim,hidden_dim,kernel_size=1)

    def forward(self,ac_feat):
        out=self.conv_1x1(ac_feat)
        out=self.FAN_ReLU(out)
        out=ac_feat + out
        return self.conv_KROut(out)

        

