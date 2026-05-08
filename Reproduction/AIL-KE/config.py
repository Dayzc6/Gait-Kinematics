import torch as t

# 参数
num_layers=10       # 卷积层数:0,1,2,...9
Kernel_size=3       # 卷积核统一设置为3
Hidden_dim=64       # 空洞卷积层、特征聚合网络所有网络层的隐藏维度均设置为 64
stacks=4            # AC和KR均采用4次空洞卷积神经网络（10个DC）堆叠

DEVICE="cuda:0" if t.cuda.is_available() else "cpu"
print(f'use:{DEVICE}')

# IMU输入维度
In_dim=(3+3+3)*7    # IMU输入维度，角速度，加速度，四元数，IMU数量n=2
# IMU的输入维度决定采用自己的数据集：
# 3个加速度     acc
# 3个角速度     vel
# 3个角度       ang
# 7个imu

# 输出维度
AC_dim=3            # AC的输出维度，分类（3类）
# 使用自己的数据集，步态相位分类：
# 0: 左脚支撑期
# 1: 右脚支撑期
# 2: 双支撑期


# 最终KR的输出维度，连续型回归量，无分类类别，根据实际的类型进行修改
# 步态参数
# step frequency (steps/min)
# step length (cm)
# left step length (cm)
# right step length (cm)
# left stride length (cm)
# right stride length (cm)
# left step speed (m/s)
# right step speed (m/s)
# step width (cm)
# cycle (s),这个不包含在预测类型中
KR_Kinematics_dim=9            

# 关节参数
# 上身角度
# 左髋角度
# 左膝角度
# 左踝角度
# 右髋角度
# 右膝角度
# 右踝角度
KR_Joint_dim=7

KR_dim=None

# Adam
lr=10**(-4) # learning rate
wd=10**(-7) # weight decay


# train_epochs
batch_size=100      # batch
AC_epochs=500       # AC先训练500个epoch
KR_epochs=1000      # KR再AC的基础上继续训练1000个epoch
Together_epochs=500 # 联合训练500个epoch

