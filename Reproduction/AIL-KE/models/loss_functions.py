# 损失函数
import torch as t
import torch.nn as nn
import pandas as pd
import numpy as np

class AILKE_Loss(nn.Module):
    def __init__(self):
        # 初始化
        super().__init__() # nn.Module标准初始化

        # 在初始化阶段选择对应的损失参数器
        self.ac_criterion=nn.CrossEntropyLoss()
        self.kr_criterion=nn.MSELoss()

    def forward(self,pred_ac,target_ac,pred_kr=None,target_kr=None):
        # 计算分类损失
        # pred_ac 形状: (Batch, Num_Classes, Time)
        # target_ac 形状: (Batch, Time)   这里的Time指什么？      
        Loss_ac=self.ac_criterion(pred_ac,target_ac)

        # 如果是联合训练阶段，还需要加上回归损失      
        if pred_kr is not None:
            # pred_kr 形状: (Batch, Num_Classes, Time)
            # target_kr 形状: (Batch, Time)  
            Loss_kr=self.kr_criterion(pred_kr,target_kr)
            return Loss_ac + Loss_kr
        
        return Loss_ac
    

    

        
