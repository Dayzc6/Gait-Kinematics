# Kinematics Regressor
# input：同AC的输入特征加速度、角速度、（四元数） + FAN 注入的特征
# output：速度/轨迹 或 关节角度
import torch as t
import torch.nn as nn
from models import DC, FAN
from config import In_dim,KR_Kinematics_dim
from config import Hidden_dim
from config import stacks


# KR需要4个DC进行堆叠
# KR的DC需要注入经过FAN处理后的AC特征
# 也就是说，需要循环四次
# 在500个epoch的ac训练完后进行1000个epoch训练

class Model_KR_Kinematics(nn.Module):
    def __init__(self,in_dim=In_dim,hidden_dim=Hidden_dim,kr_kinematics_dim=KR_Kinematics_dim):
        super().__init__()
        self.conv_ac_in=nn.Conv1d(in_channels=in_dim,out_channels=hidden_dim,kernel_size=1)
        self.conv_kr_in=nn.Conv1d(in_channels=in_dim,out_channels=hidden_dim,kernel_size=1)

        # 预定义所有的扩张层，存入ModuleList
        self.stacks_ac=nn.ModuleList([DC.DCStack(hidden_dim) for _ in range(stacks)])
        self.stacks_kr=nn.ModuleList([DC.DCStack(hidden_dim) for _ in range(stacks)])        

        # 4个独立的FAN模块
        self.FANs=nn.ModuleList([FAN.Model_FAN(hidden_dim) for _ in range(stacks)])

        # KR_Kinematics的输出头
        self.conv_kr_kinematics_out=nn.Conv1d(in_channels=hidden_dim,out_channels=kr_kinematics_dim,kernel_size=1)
        
    def forward(self,x):
        ac_out=self.conv_ac_in(x)
        # 不需要梯度
        kr_kinematics_out = ac_out.detach().clone()

        for i in range(stacks):
            ac_out=self.stacks_ac[i](ac_out)
            kr_kinematics_out=self.stacks_kr[i](kr_kinematics_out)
            fan_out=self.FANs[i](ac_out)
            kr_kinematics_out=fan_out+kr_kinematics_out
        
        kr_kinematics_out=self.conv_kr_kinematics_out(kr_kinematics_out)  
        # out=self.conv_out(out)
        return kr_kinematics_out
    