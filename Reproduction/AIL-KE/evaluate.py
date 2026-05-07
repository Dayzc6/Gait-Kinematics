# 独立测试。在未见过的受试者数据上运行模型，评估泛化能力，并生成最终的轨迹对比报告。
from sklearn.metrics import confusion_matrix, classification_report
import seaborn as sns
import torch
from models.AC import Model_AC
from data.dataset import test_loader
from config import DEVICE,lr,wd

model=Model_AC()

# 加载参数
model.load_state_dict(torch.load(r'E:\code\3D-position\Reproduction\AIL-KE\state_dict'))

# 加载checkpoint
checkpoint = torch.load(r'E:\code\3D-position\Reproduction\AIL-KE\state_dict')
model.load_state_dict(checkpoint['model_state_dict'])
torch.optim.Adam(model.parameters(),lr=lr,weight_decay=wd).load_state_dict(checkpoint['optimizer_state_dict'])
start_epoch = checkpoint['epoch']

def evaluate(model, test_loader, device):
    model.eval()
    all_preds = []
    all_targets = []
    
    with torch.no_grad():
        for data, target in test_loader:
            data = data.to(device)
            output = model(data)
            _, predicted = output.max(1)
            
            all_preds.extend(predicted.cpu().numpy())
            all_targets.extend(target.numpy())
    
    # 混淆矩阵
    cm = confusion_matrix(all_targets, all_preds)
    
    # 分类报告（包含 precision, recall, F1）
    report = classification_report(all_targets, all_preds, 
                                   target_names=['左支撑', '右支撑', '双支撑'])
    
    print(cm)
    print(report)
    
    return cm, report

if __name__=='__main__':
    evaluate(model,test_loader,DEVICE)
