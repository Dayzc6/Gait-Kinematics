# 独立测试。在未见过的受试者数据上运行模型，评估泛化能力，并生成最终的轨迹对比报告。
from sklearn.metrics import confusion_matrix, classification_report
import seaborn as sns
import torch
from models.AC import Model_AC
import data.dataset
from config import DEVICE,lr,wd
# 在创建模型后，加载权重前或后，把模型移到 GPU
model_ac=Model_AC().to(DEVICE)
test_loader=data.dataset.get_dataloaders()[2]

# 加载参数
# model_ac.load_state_dict(torch.load(r'E:\code\3D-position\Reproduction\AIL-KE\state_dict'))

# 加载checkpoint,这两个二选一
checkpoint = torch.load(r'E:\code\3D-position\Reproduction\AIL-KE\checkpoint\checkpoint_ac.pt',map_location=DEVICE)
model_ac.load_state_dict(checkpoint['model_state_dict'])

def evaluate(model, test_loader, device):
    model.eval()
    # all_preds 和 all_targets 是二维数组列表，不是一维标签列表。
    all_preds = []
    all_targets = []
    
    with torch.no_grad():
        for data, target in test_loader:
            data = data.to(device)
            output = model(data)
            _, predicted = output.max(1)
            
            # 这里的cpu()可以换成cuda吗
            all_preds.extend(predicted.cpu().numpy().flatten())
            # np只能在cpu上，tensor在cuda上
            # all_preds.extend(predicted.cuda().numpy())            
            all_targets.extend(target.cpu().numpy().flatten())
    
    # 混淆矩阵
    cm = confusion_matrix(all_targets, all_preds)
    
    # 分类报告（包含 precision, recall, F1）
    report = classification_report(all_targets, all_preds, 
                                   target_names=['左支撑', '右支撑', '双支撑'])
    
    print(cm)
    print(report)
    
    return cm, report

if __name__=='__main__':
    evaluate(model_ac,test_loader,DEVICE)
