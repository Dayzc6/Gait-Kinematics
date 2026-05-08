# 该模型为主要的思路复现，并不作为实际模型使用

import torch as t
import torch.nn as nn
import pandas as pd
import numpy as np
import sys
import DC, FAN
from config import num_layers, stacks
from config import AC_dim, KR_dim
from config import Hidden_dim, In_dim

class MultiModel(nn.Module):
    def __init__(self,ac_dim=AC_dim,kr_dim=KR_dim,in_dim=In_dim,hidden_dim=Hidden_dim):
        super().__init__()
        self.ac_conv_in=nn.Conv1d(in_channels=in_dim,out_channels=hidden_dim,kernel_size=1)
        self.kr_conv_in=nn.Conv1d(in_channels=in_dim,out_channels=hidden_dim,kernel_size=1)

        # 核心：必须定义 4 个独立的 AC Stack 和 4 个独立的 KR Stack
        # 使用 ModuleList 确保参数被正确注册
        self.ac_stacks=nn.ModuleList([DC.DCStack(hidden_dim) for _ in range(stacks)])
        self.kr_stacks=nn.ModuleList([DC.DCStack(hidden_dim) for _ in range(stacks)])

        # 必须定义 4 个独立的 FAN 模块
        self.FANs=nn.ModuleList([FAN.Model_FAN(hidden_dim) for _ in range(stacks)])

        # 输出头
        self.ac_head=nn.Conv1d(in_channels=hidden_dim,out_channels=ac_dim,kernel_size=1)
        self.kr_head=nn.Conv1d(in_channels=hidden_dim,out_channels=kr_dim,kernel_size=1)
        self.relu=nn.ReLU()

    def forward(self,x):
        # 局部特征列表，不在self中保存，防止内存溢出
        ac_features=[]

        # AC支路
        ac_out=self.ac_conv_in(x)
        for stack in self.ac_stacks:
            ac_out=stack(ac_out)
            ac_features.append(ac_out)

        # KR支路
        kr_out=self.kr_conv_in(x)
        for i in range(stacks):
            # 注入逻辑：KR输入 = 前一层输出 + FAN(对应AC层输出)      
            injected_feat=self.FANs[i](ac_features[i])
            kr_out=self.kr_stacks[i](kr_out)
            kr_out=kr_out + injected_feat
        
        # 最终输出
        logits_ac=self.ac_head(ac_out)
        pred_kr=self.kr_head(kr_out)

        return self.softmax(logits_ac), pred_kr
    


            
            

            
            
            
        


        