# 损失函数
import torch as t
import torch.nn as nn
import pandas as pd
import numpy as np

"""
注意：这里有一个维度匹配问题。
当前模型输出 pred_kr: (batch, kr_dim, 512)，但dataset返回的 target_kr: (batch, 512, kr_dim)（因为是从CSV直接取的）。
需要在dataset中 转置target_kr 或在loss中转置
"""


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
        # AC: pred_ac (batch, 3, 512), target_ac (batch, 512)
        Loss_ac=self.ac_criterion(pred_ac,target_ac)

        # 如果是联合训练阶段，还需要加上回归损失      
        if pred_kr is not None:
            # KR: pred_kr (batch, kr_dim, 512), target_kr (batch, 512, kr_dim)
            # 注意：需要转置 pred_kr 或 target_kr 使维度匹配
            
            Loss_kr=self.kr_criterion(pred_kr,target_kr)
            return Loss_ac + Loss_kr
        
        return Loss_ac
    

    

        
