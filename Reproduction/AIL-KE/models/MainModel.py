# 三合一模型

import torch as t
import torch.nn as nn
from models import DC, FAN
from config import stacks
from config import AC_dim, KR_Kinematics_dim, KR_Joint_dim
from config import Hidden_dim, In_dim

class MultiModel(nn.Module):
    def __init__(self,ac_dim=AC_dim,kr_dim=None,in_dim=In_dim,hidden_dim=Hidden_dim):
        super().__init__()
        self.ac_dim=ac_dim
        self.kr_dim=kr_dim

        # AC支路
        self.ac_conv_in=nn.Conv1d(in_channels=in_dim,out_channels=hidden_dim,kernel_size=1)
        self.ac_stacks=nn.ModuleList([DC.DCStack(hidden_dim) for _ in range(stacks)])
        self.ac_head=nn.Conv1d(in_channels=hidden_dim,out_channels=ac_dim,kernel_size=1)

        # KR支路
        if self.kr_dim is not None:
            self.kr_conv_in=nn.Conv1d(in_channels=in_dim,out_channels=hidden_dim,kernel_size=1)
            self.kr_stacks=nn.ModuleList([DC.DCStack(hidden_dim) for _ in range(stacks)])
            # 必须定义 4 个独立的 FAN 模块
            self.FANs=nn.ModuleList([FAN.Model_FAN(hidden_dim) for _ in range(stacks)])
            # 输出头
            self.kr_head=nn.Conv1d(in_channels=hidden_dim,out_channels=kr_dim,kernel_size=1)
        self.relu=nn.ReLU()

    def forward(self,x,mode='ac'):
        """
        mode: 'ac' -> 只返回AC输出
              'kr' -> 只返回KR输出（需要kr_dim不为None）
              'both' -> 返回(AC, KR)
        """
        # AC支路始终计算
        ac_out=self.ac_conv_in(x)
        ac_features=[]
        for stack in self.ac_stacks:
            ac_out=stack(ac_out)
            ac_features.append(ac_out)
        logits_ac=self.ac_head(ac_out)

        if mode == 'ac':
            return logits_ac

        # KR支路计算
        if self.kr_dim is None:
            raise ValueError("Model initialized without kr_dim, cannot compute KR")
        
        kr_out=self.kr_conv_in(x)
        
        for i in range(stacks):
            fan_out=self.FANs[i](ac_features[i])
            kr_out=self.kr_stacks[i](kr_out)
            kr_out=kr_out+fan_out
        
        pred_kr=self.kr_head(kr_out)
            
        if mode == 'kr':
            return pred_kr

        return logits_ac, pred_kr
    


            
            

            
            
            
        


        