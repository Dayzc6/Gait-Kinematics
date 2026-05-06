# 参数
num_layers=10       # 卷积层数:0,1,2,...9
Kernel_size=3       # 卷积核统一设置为3
Hidden_dim=64       # 空洞卷积层、特征聚合网络所有网络层的隐藏维度均设置为 64
stacks=4            # AC和KR均采用4次空洞卷积神经网络（10个DC）堆叠

# IMU输入维度
In_dim=(3+3+4)*2    # IMU输入维度，角速度，加速度，四元数，IMU数量n=2



# 输出维度
AC_dim=4            # AC的输出维度，分类
KR_dim=2            # 最终KR的输出维度，连续型回归量，无分类类别，根据实际的类型进行修改



# Adam
lr=10**(-4) # learning rate
wd=10**(-7) # weight decay

# train_epochs
AC_epochs=500
KR_epochs=1000
Together_epochs=500

