# 主训练程序
import time
import os
import torch as t
import numpy as np
import pandas as pd
import torch.nn as nn
import matplotlib.pyplot as plt
from config import batch_size, DEVICE, AC_epochs, lr, wd
from models.AC import Model_AC
from models.KR_Kinematics import Model_KR_Kinematics
from models.KR_Joint import Model_KR_Joint
from models.loss_functions import AILKE_Loss
import data.dataset

train_loader=data.dataset.get_dataloaders()[0]
val_loader=data.dataset.get_dataloaders()[1]


model_ac=Model_AC()
model_kr_kinematics=Model_KR_Kinematics()
model_kr_joint=Model_KR_Joint()

criterion=AILKE_Loss()


class MainTrain(nn.Module):
    def __init__(self,model,train_loader,val_loader,criterion,patience=50):  # patience:连续20轮val loss不下降就停
        super().__init__()
        self.device=t.device(DEVICE)
        self.model=model.to(self.device)
        self.train_loader=train_loader     # 导入的train_loader和val_loader格式是什么？
        self.val_loader=val_loader
        self.criterion=criterion
        self.patience=patience
        self.best_val_loss=float('inf')
        self.counter=0

        # 定义优化器
        self.optimizer=t.optim.Adam(self.model.parameters(),lr=lr,weight_decay=wd)

        # 用于记录历史数据，供后续绘图
        self.history = {
            'train_loss': [], 'val_loss': [],
            'train_acc': [], 'val_acc': []
        }
    
    # ac的一个epoch训练
    def train_ac_one_epoch(self,epoch):
        self.model.train() # 开启训练模式（开启dropout、batchnorm等）
        total_loss, correct, total = 0, 0, 0

        # enumerate返回的是(index, (data, target))
        for batch_idx, (data,target_ac) in enumerate(self.train_loader): # 这里不加（）可以吗？为什么要加（）？
            data=data.to(self.device)
            target_ac=target_ac.to(self.device)

            # 梯度清零
            self.optimizer.zero_grad()
            # 向前传播
            output_ac=self.model(data)
            # 计算损失
            # CrossEntropy 需要输入 [N, C, L] 或 [N, C]
            loss=self.criterion(output_ac,target_ac)

            # if batch_idx == 0 and epoch%100 == 0:
                # print(f"output_ac shape: {output_ac.shape}")
                # print(f"target_ac shape: {target_ac.shape}")
                # print(f"output_ac sample: {output_ac[0]}")
                # print(f"target_ac sample: {target_ac[0]}")
                # print(f"loss value: {loss.item()}")      

            # 反向传播
            loss.backward()
            # 更新参数
            self.optimizer.step()

            # 统计
            total_loss+=loss.item()               # 为什么要item（）？
            _,predicted=t.max(output_ac,dim=1)    # 这前面的_是啥？t.max()后输出的格式是？
            # total+=target_ac.size(0)              # 为什么用size？
            total+=target_ac.numel()
            correct+=predicted.eq(target_ac).sum().item()

        return total_loss/len(self.train_loader), correct/total

    def train_kr_kinematics_one_epoch(self):
        self.model.train() # 开启训练模式（开启dropout、batchnorm等）
        total_loss, correct, total = 0, 0, 0

        # enumerate返回的是(index, (data, target))
        for batch_idx, (data,target_ac) in enumerate(self.train_loader): # 这里不加（）可以吗？为什么要加（）？
            data=data.to(self.device)
            target_ac=target_ac.to(self.device)

            # 梯度清零
            self.optimizer.zero_grad()

            # 向前传播
            output_ac=self.model(data)

            # 计算损失
            # CrossEntropy 需要输入除了ac的还有kr的损失函数
            loss=self.criterion(output_ac,target_ac,target_kr)

            # 反向传播
            loss.backward()
            # 更新参数
            self.optimizer.step()

            # 统计
            total_loss+=loss.item()               # 为什么要item（）？
            _,predicted=t.max(output_ac,dim=1)    # 这前面的_是啥？t.max()后输出的格式是？
            # total+=target_ac.size(0)              # 为什么用size？
            total+=target_ac.numel()
            correct+=predicted.eq(target_ac).sum().item()

        return total_loss/len(self.train_loader), correct/total

    def validate(self):
        self.model.eval()       # 开启预测模式
        total_loss, correct, total =0,0,0
        with t.no_grad():       # 验证时不计算梯度，省内存
            for batch_idx,(data, target_ac) in enumerate(self.val_loader):
                data=data.to(self.device)
                target_ac=target_ac.to(self.device)
                output_ac=self.model(data)
                loss=self.criterion(output_ac,target_ac)

                total_loss+=loss.item()
                _,predicted=output_ac.max(1)    # 为什么这里前面要_?这里的max输出格式是？应该是？
                # total+=target_ac.size(0)        # .numel()又有什么区别？可以用吗？
                total+=target_ac.numel()
                correct+=predicted.eq(target_ac).sum().item()

        return total_loss/len(self.val_loader), correct/total
    
    def train(self,ac_epochs,kr_epochs):
        print(f"开始训练，设备：{self.device}")
        start_full_time=time.time()
        epoch10_start=time.time()
        epoch10_start_key=1
        # val_loss_stop=0
        # 先训练500个epoch的ac
        for epoch in range(ac_epochs):
            if epoch10_start_key:
                epoch10_start=time.time()
                epoch10_start_key=0

            train_loss, train_acc=self.train_ac_one_epoch(epoch)
            val_loss, val_acc=self.validate()

            # 记录历史
            self.history['train_loss'].append(train_loss)
            self.history['val_loss'].append(val_loss)
            self.history['train_acc'].append(train_acc)
            self.history['val_acc'].append(val_acc)

            # 每隔 10 个 Epoch 输出一次终端信息
            if (epoch + 1) % 10 == 0 or epoch == 0:
                duration = time.time() - epoch10_start
                epoch10_start_key=1
                # val_loss_stop=val_loss
                print(f"AC_Epoch [{epoch+1}/{ac_epochs}] | "
                      f"AC：Train Loss: {train_loss:.4f} | Val Loss: {val_loss:.4f} | Val Acc: {val_acc:.2%} | Train Acc: {train_acc:.2%}"
                      f"耗时：{duration/60:.2f}分钟")
                # if val_loss<=val_loss_stop:
                    # break
            
            # early stopping检查
            if val_loss<self.best_val_loss:
                self.best_val_loss=val_loss
                self.counter=0
                # 保存最佳模型
                # t.save(self.model.state_dict(),'best_model.pt')
            else:
                self.counter+=1
                if self.counter>=self.patience:
                    print(f'Early stopping at epoch {epoch+1}')
                    break

                
        total_duration = time.time() - start_full_time
        print(f"训练完成！总耗时：{total_duration/60:.2f} 分钟")
        self.plot_curves()
        
    def plot_curves(self):
        plt.figure(figsize=(12,5))

        # 绘制loss曲线
        plt.subplot(1, 2, 1)
        plt.plot(self.history['train_loss'], label='Train Loss')
        plt.plot(self.history['val_loss'], label='Val Loss')
        plt.title('Loss Curve')
        plt.legend()

        # 绘制 Accuracy 曲线
        plt.subplot(1, 2, 2)
        plt.plot(self.history['train_acc'], label='Train Acc')
        plt.plot(self.history['val_acc'], label='Val Acc')
        plt.title('Accuracy Curve')
        plt.legend()
        
        plt.show()


def checkpoint(epochs,model,trainer):
    # 保存更多信息（包含优化器状态等）
    save_name
    if model==model_ac:
        save_name='Model_ac'
    elif model==model_kr_kinematics:
        save_name='model_kr_kinematics'
    else:
        save_name='model_kr_joint'

    checkpoint = {
        'epoch': epochs,
        'model_state_dict': model.state_dict(),
        'optimizer_state_dict': trainer.optimizer.state_dict(),
        'train_acc': trainer.history['train_acc'][-1],
    }
           
    save_path=f'E:\code\3D-position\Reproduction\AIL-KE\checkpoint\Checkpoint_{save_name}.pt'
    
    t.save(checkpoint, save_path)


if __name__=="__main__":
    # AC模型
    trainer_ac=MainTrain(model=model_ac,train_loader=train_loader,val_loader=val_loader,criterion=criterion)
    trainer_ac.train(AC_epochs)

    # t.save(model_ac.state_dict(),r'E:\code\3D-position\Reproduction\AIL-KE\state_dict')

    # 保存更多信息（包含优化器状态等）
    # Checkpoint_AC
    checkpoint(epochs=AC_epochs,model=model_ac,trainer=trainer_ac)

    # Checkpoint_KR_kinematics
    # checkpoint(epochs=AC_epochs,model=model_ac,trainer=trainer_ac)

    # Checkpoint_KR_joint
    # checkpoint(epochs=AC_epochs,model=model_ac,trainer=trainer_ac)


    