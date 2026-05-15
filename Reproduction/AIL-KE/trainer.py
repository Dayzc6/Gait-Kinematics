# 主训练程序
import time
import os
import torch as t
import torch.nn as nn
import matplotlib.pyplot as plt
from config import batch_size, DEVICE, AC_epochs, KR_epochs,lr, wd, CHECKPOINT_DIR, KR_Kinematics_dim,KR_Joint_dim
from models.MainModel import MultiModel
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
    def __init__(self,model,train_loader,val_loader,patience=50):  # patience:连续20轮val loss不下降就停
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
        # self.optimizer=t.optim.Adam(self.model.parameters(),lr=lr,weight_decay=wd)

        # 用于记录历史数据，供后续绘图
        self.history = {
            'train_loss': [], 'val_loss': [],
            'train_acc':[], 'val_acc':[]
        }
    
    # 针对不同的模块设置不同的优化器
    def _get_optimizer(self,phase='ac'):
        if phase == 'ac':
            params = [p for n, p in self.model.named_parameters() if n.startswith('ac_')] # 这个模块是怎么写的？为什么？
        elif phase == 'kr':
            params = [p for n, p in self.model.named_parameters() if not n.startswith('ac_')]
        else:
            params = self.model.parameters()
        return t.optim.Adam(params, lr=lr, weight_decay=wd)

    # ac的一个epoch训练
    # def train_ac_one_epoch(self):
        #self.model.train() # 开启训练模式（开启dropout、batchnorm等）
        #total_loss, correct, total = 0, 0, 0

        # enumerate返回的是(index, (data, target))
        #for batch_idx, (data,target_ac,target_kr_kin,target_kr_jo) in enumerate(self.train_loader): # 这里不加（）可以吗？为什么要加（）？
            #data=data.to(self.device)
            #target_ac=target_ac.to(self.device)

            # 梯度清零
            #self.optimizer.zero_grad()
            # 向前传播
            #output_ac=self.model(data)
            # 计算损失
            # CrossEntropy 需要输入 [N, C, L] 或 [N, C]
            #loss=self.criterion(output_ac,target_ac)

            # if batch_idx == 0 and epoch%100 == 0:
                # print(f"output_ac shape: {output_ac.shape}")
                # print(f"target_ac shape: {target_ac.shape}")
                # print(f"output_ac sample: {output_ac[0]}")
                # print(f"target_ac sample: {target_ac[0]}")
                # print(f"loss value: {loss.item()}")      

            # 反向传播
            #loss.backward()
            # 更新参数
            #self.optimizer.step()

            # 统计
            #total_loss+=loss.item()               # 为什么要item（）？
            #_,predicted=t.max(output_ac,dim=1)    # 这前面的_是啥？t.max()后输出的格式是？
            # total+=target_ac.size(0)              # 为什么用size？
            #total+=target_ac.numel()
            #correct+=predicted.eq(target_ac).sum().item()

        #return total_loss/len(self.train_loader), correct/total
    
    def train_phase1_ac(self,epochs):
        optimizer=self._get_optimizer('ac')
        for epoch in range(epochs):
            self.model.train()
            total_loss=0
            correct=0
            total=0
            for data,target_ac,_,_,_,_ in self.train_loader:
                data=data.to(self.device)
                target_ac=target_ac.to(self.device)

                optimizer.zero_grad() # 梯度置零
                output_ac=self.model(data,mode='ac')
                loss=self.criterion(output_ac,target_ac)
                loss.backward()
                optimizer.step()
                total_loss+=loss.item()

                _,predicted=output_ac.max(1)
                total+=target_ac.numel()
                correct+=predicted.eq(target_ac).sum().item()


            # validate + early stopping
            val_loss,val_acc=self._validate_ac()
            train_acc=correct/total
            self.history['train_loss'].append(total_loss/len(self.train_loader))
            self.history['train_acc'].append(train_acc)
            self.history['val_loss'].append(val_loss)
            self.history['val_acc'].append(val_acc)
            if (epoch+1)%10==0:
                print(f"AC Epoch [{epoch+1}/{epochs}] | Train Loss: {self.history['train_loss'][-1]:.4f} | Train Acc: {train_acc:.4f} | Val Loss: {val_loss:.4f} | Val Acc: {val_acc:.4f}")
            # early stopping check
            if val_loss<self.best_val_loss:
                self.best_val_loss=val_loss
                self.counter=0
            else:
                self.counter+=1
                if self.counter>=self.patience:
                    print(f"Early stopping at epoch {epoch+1}")
                    break

        # 训练结束后绘制loss曲线
        save_path = os.path.join(CHECKPOINT_DIR, 'loss_curve_ac.png')
        self.plot_curves(save_path=save_path, phase='ac')                     

    def _validate_ac(self):
        self.model.eval()       # 开启预测模式
        total_loss=0
        correct=0
        total=0
        with t.no_grad():       # 验证时不计算梯度，省内存
            for data, target_ac, _, _, _, _ in self.val_loader:
                data=data.to(self.device)
                target_ac=target_ac.to(self.device)
                output_ac=self.model(data,mode='ac')
                loss=self.criterion(output_ac,target_ac)

                total_loss+=loss.item()
                _,predicted=output_ac.max(1)    # 为什么这里前面要_?这里的max输出格式是？应该是？
                # total+=target_ac.size(0)        # .numel()又有什么区别？可以用吗？
                total+=target_ac.numel()
                correct+=predicted.eq(target_ac).sum().item()

        return total_loss/len(self.val_loader), correct/total
    
    '''def train_phase2_kr(self,ac_epochs,kr_epochs):
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
        self.plot_curves()'''

    def train_phase2_kr(self,epochs,kr_type='kinematics'):
        # 冻结AC
        for name,param in self.model.named_parameters():
            if name.startswith('ac_'):
                param.requires_grad=False
        
        optimizer=self._get_optimizer('kr')
        self.best_val_loss=float('inf')
        self.counter=0

        for epoch in range(epochs):
            self.model.train()
            total_loss=0
            correct=0
            total=0
            for data, _, target_kr_kin, target_kr_joint, _, _ in self.train_loader:
                data=data.to(self.device)
                if kr_type=='kinematics':
                    target_kr=target_kr_kin.to(self.device)
                else:
                    target_kr=target_kr_joint.to(self.device)

                optimizer.zero_grad()
                pred_kr=self.model(data,mode='kr')
                loss=self.criterion.kr_criterion(pred_kr,target_kr)
                loss.backward()
                optimizer.step()
                total_loss+=loss.item()
        
            val_loss=self._validate_kr(kr_type)
            self.history['train_loss'].append(total_loss/len(self.train_loader))
            self.history['val_loss'].append(val_loss)
            # self.history['val_acc'].append(val_acc)

            if (epoch+1)%10==0:
                print(f"KR-{kr_type} Epoch [{epoch+1}/{epochs}] | Train Loss: {self.history['train_loss'][-1]:.4f} | Val Loss: {val_loss:.4f}")            
            if val_loss < self.best_val_loss:
                self.best_val_loss = val_loss
                self.counter = 0
            else:
                self.counter += 1
                if self.counter >= self.patience:
                    print(f"Early stopping at epoch {epoch+1}")
                    break
        
        # 训练结束后绘制loss曲线
        save_path = os.path.join(CHECKPOINT_DIR, f'loss_curve_{kr_type}.png')
        self.plot_curves(save_path=save_path, phase=kr_type)


    def _validate_kr(self,kr_type):
        self.model.eval()
        total_loss=0
        with t.no_grad():
            for data, _, target_kr_kin, target_kr_joint, _, _ in self.val_loader:
                data=data.to(self.device)
                if kr_type=='kinematics':
                    target_kr=target_kr_kin.to(self.device)
                else:
                    target_kr=target_kr_joint.to(self.device)
                pred_kr=self.model(data,mode='kr')
                loss=self.criterion.kr_criterion(pred_kr,target_kr)
                total_loss+=loss.item()
                # _,predicted=pred_kr.max(1)    # 为什么这里前面要_?这里的max输出格式是？应该是？
                # total+=target_kr.size(0)        # .numel()又有什么区别？可以用吗？
                # total+=target_kr.numel()
                # correct+=predicted.eq(target_kr).sum().item()
        
        return total_loss/len(self.val_loader)


    def plot_curves(self, save_path=None, phase='ac'):
        if phase == 'ac':
            fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12,5))
            
            # 绘制loss曲线
            ax1.plot(self.history['train_loss'], label='Train Loss')
            ax1.plot(self.history['val_loss'], label='Val Loss')
            ax1.set_title('Loss Curve')
            ax1.legend()
            ax1.set_xlabel('Epoch')
            ax1.set_ylabel('Loss')
            
            # 绘制 Accuracy 曲线
            ax2.plot(self.history['train_acc'], label='Train Acc')
            ax2.plot(self.history['val_acc'], label='Val Acc')
            ax2.set_title('Accuracy Curve')
            ax2.legend()
            ax2.set_xlabel('Epoch')
            ax2.set_ylabel('Accuracy')
            ax2.set_ylim(0, 1)
        else:
            fig, ax1 = plt.subplots(1, 1, figsize=(8,5))
            ax1.plot(self.history['train_loss'], label='Train Loss')
            ax1.plot(self.history['val_loss'], label='Val Loss')
            ax1.set_title(f'Loss Curve ({phase})')
            ax1.legend()
            ax1.set_xlabel('Epoch')
            ax1.set_ylabel('MSE Loss')
        
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=150, bbox_inches='tight')
            print(f"Loss curve saved to: {save_path}")
        else:
            plt.show()
        plt.close()


def checkpoint(epochs,model,trainer):
    # 保存更多信息（包含优化器状态等）
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
        # 'train_acc': trainer.history['train_acc'][-1],
    }
           
    save_path=rf'E:\code\3D-position\Reproduction\AIL-KE\checkpoint\Checkpoint_{save_name}.pt'
    
    t.save(checkpoint, save_path)


if __name__ == "__main__":
    # ========== 阶段1：训练AC ==========
    print("=== Phase 1: Training AC ===")
    model = MultiModel(ac_dim=3, kr_dim=None)  # kr_dim任意，阶段1不计算KR
    trainer = MainTrain(model, train_loader, val_loader)
    trainer.train_phase1_ac(AC_epochs)
    
    # 保存AC权重
    ac_state = {k: v for k, v in model.state_dict().items() if k.startswith('ac_')}
    t.save(ac_state, os.path.join(CHECKPOINT_DIR, 'phase1_ac.pt'))
    
    # ========== 阶段2a：训练KR_Kinematics ==========
    print("\n=== Phase 2a: Training KR Kinematics ===")
    model_kin = MultiModel(ac_dim=3, kr_dim=KR_Kinematics_dim)
    model_kin.load_state_dict(t.load(os.path.join(CHECKPOINT_DIR, 'phase1_ac.pt')), strict=False)
    trainer_kin = MainTrain(model_kin, train_loader, val_loader)
    trainer_kin.train_phase2_kr(KR_epochs, kr_type='kinematics')
    t.save(model_kin.state_dict(), os.path.join(CHECKPOINT_DIR, 'phase2_kinematics.pt'))
    
    # ========== 阶段2b：训练KR_Joint ==========
    print("\n=== Phase 2b: Training KR Joint ===")
    model_joint = MultiModel(ac_dim=3, kr_dim=KR_Joint_dim)
    model_joint.load_state_dict(t.load(os.path.join(CHECKPOINT_DIR, 'phase1_ac.pt')), strict=False)
    trainer_joint = MainTrain(model_joint, train_loader, val_loader)
    trainer_joint.train_phase2_kr(KR_epochs, kr_type='joint')
    t.save(model_joint.state_dict(), os.path.join(CHECKPOINT_DIR, 'phase2_joint.pt'))


    