# 参数
num_layers=9  # 最大卷积层数
Kernel_size=3 # 卷积核统一设置为3
Hidden_dim=64 # 空洞卷积层、特征聚合网络所有网络层的隐藏维度均设置为 64
In_dim=(3+3+4)*2 # IMU输入维度，角速度，加速度，四元数，IMU数量n=2
KR_dim=2*()
AC_dim=4

# Adam
lr=10**(-4) # learning rate
wd=10**(-7) # weight decay

# train_epochs
AC_epochs=500
KR_epochs=1000
Together_epochs=500

