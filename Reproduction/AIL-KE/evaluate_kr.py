import torch
import os
import numpy as np
import matplotlib.pyplot as plt
from sklearn.metrics import mean_squared_error, mean_absolute_error
from models.MainModel import MultiModel
from data.dataset import get_dataloaders, IMUDataset
from config import DEVICE, KR_Kinematics_dim, KR_Joint_dim, CHECKPOINT_DIR
from sklearn.metrics import r2_score

# 创建report目录
REPORT_DIR = r'E:\code\3D-position\Reproduction\AIL-KE\report'
os.makedirs(REPORT_DIR, exist_ok=True)

# 参数名称映射
KINEMATICS_NAMES = [
    'left_pct_stance', 'left_pct_swing', 'right_pct_stance', 'right_pct_swing',
    'step_frequency', 'step_length', 'left_step_length', 'right_step_length',
    'left_stride_length', 'right_stride_length', 'left_step_speed', 'right_step_speed',
    'step_width'
]

JOINT_NAMES = [
    'torso_angle', 'left_hip_angle', 'left_knee_angle', 'left_ankle_angle',
    'right_hip_angle', 'right_knee_angle', 'right_ankle_angle'
]


def evaluate_kr(model, test_loader, kr_type, device, dataset_stats=None):
    """
    评估KR模型，支持反归一化到原始物理单位
    
    Args:
        model: 训练好的模型
        test_loader: 测试数据加载器
        kr_type: 'kinematics' 或 'joint'
        device: 计算设备
        dataset_stats: 包含mean和std的字典，用于反归一化
    """
    model.eval()
    all_preds = []
    all_targets = []
    
    with torch.no_grad():
        for data, _, _, _, target_kr_kin, target_kr_joint in test_loader:
            data = data.to(device)
            if kr_type == 'kinematics':
                target = target_kr_kin.to(device)  # 非归一化标签 (batch, 13, 512)
            else:
                target = target_kr_joint.to(device)  # 非归一化标签 (batch, 7, 512)
            
            pred = model(data, mode='kr')  # 模型输出 (batch, dim, 512)，归一化空间
            
            # 反归一化到原始物理单位
            if dataset_stats is not None:
                mean = dataset_stats['mean'].to(device)
                std = dataset_stats['std'].to(device)
                pred = pred * std.view(1, -1, 1) + mean.view(1, -1, 1)
            
            # 转置为 (batch, seq_len, dim) 方便后续处理
            pred = pred.cpu().numpy().transpose(0, 2, 1)
            target = target.cpu().numpy().transpose(0, 2, 1)
            
            all_preds.append(pred.reshape(-1, pred.shape[-1]))
            all_targets.append(target.reshape(-1, target.shape[-1]))
    
    all_preds = np.vstack(all_preds)
    all_targets = np.vstack(all_targets)
    
    # 计算每个参数的RMSE和MAE
    rmse_per_param = np.sqrt(mean_squared_error(all_targets, all_preds, multioutput='raw_values'))
    mae_per_param = mean_absolute_error(all_targets, all_preds, multioutput='raw_values')
    
    # 计算相对误差
    relative_error = np.mean(np.abs(all_preds - all_targets) / (np.abs(all_targets) + 1e-8), axis=0) * 100
    
    param_names = KINEMATICS_NAMES if kr_type == 'kinematics' else JOINT_NAMES
    
    print(f"\n{'='*60}")
    print(f"=== KR {kr_type.upper()} Evaluation ===")
    print(f"{'='*60}")
    print(f"Overall RMSE: {np.mean(rmse_per_param):.4f}")
    print(f"Overall MAE:  {np.mean(mae_per_param):.4f}")
    print(f"\n{'Param Name':<20} {'RMSE':>10} {'MAE':>10} {'Rel.Err(%)':>12}")
    print("-" * 60)
    for i, (name, rmse, mae, rel_err) in enumerate(zip(param_names, rmse_per_param, mae_per_param, relative_error)):
        print(f"{name:<20} {rmse:>10.4f} {mae:>10.4f} {rel_err:>11.2f}%")
    
    return all_preds, all_targets, rmse_per_param, mae_per_param, param_names


def plot_time_series(all_preds, all_targets, param_names, kr_type, n_samples=3, sample_length=512):
    """
    绘制时间序列对比图：预测值 vs 真实值
    """
    # 选择前n_samples个完整的512长度样本
    n_points = n_samples * sample_length
    
    fig, axes = plt.subplots(len(param_names), 1, figsize=(14, 2*len(param_names)))
    if len(param_names) == 1:
        axes = [axes]
    
    for i, (name, ax) in enumerate(zip(param_names, axes)):
        true_vals = all_targets[:n_points, i]
        pred_vals = all_preds[:n_points, i]
        
        ax.plot(true_vals, label='Ground Truth', alpha=0.8, linewidth=1)
        ax.plot(pred_vals, label='Predicted', alpha=0.8, linewidth=1)
        ax.set_ylabel(name)
        ax.legend(loc='upper right', fontsize=8)
        ax.grid(True, alpha=0.3)
        
        # 在最后一个子图添加x轴标签
        if i == len(param_names) - 1:
            ax.set_xlabel('Time Step')
    
    plt.suptitle(f'{kr_type.upper()} - Time Series Comparison (First {n_samples} samples)', fontsize=14)
    plt.tight_layout()
    save_path = os.path.join(REPORT_DIR, f'{kr_type}_time_series.png')
    plt.savefig(save_path, dpi=150, bbox_inches='tight')
    print(f"\nTime series plot saved to: {save_path}")
    plt.close()


def plot_scatter(all_preds, all_targets, param_names, kr_type):
    """
    绘制散点图：预测值 vs 真实值
    """
    n_params = len(param_names)
    n_cols = 4
    n_rows = (n_params + n_cols - 1) // n_cols
    
    fig, axes = plt.subplots(n_rows, n_cols, figsize=(16, 4*n_rows))
    axes = axes.flatten() if n_params > 1 else [axes]
    
    for i, (name, ax) in enumerate(zip(param_names, axes)):
        true_vals = all_targets[:, i]
        pred_vals = all_preds[:, i]
        
        ax.scatter(true_vals, pred_vals, alpha=0.3, s=1, c='blue')
        
        # 绘制完美预测线
        min_val = min(true_vals.min(), pred_vals.min())
        max_val = max(true_vals.max(), pred_vals.max())
        ax.plot([min_val, max_val], [min_val, max_val], 'r--', label='Perfect', linewidth=2)
        
        ax.set_xlabel('Ground Truth')
        ax.set_ylabel('Predicted')
        ax.set_title(name)
        ax.legend(loc='upper left', fontsize=8)
        ax.grid(True, alpha=0.3)
    
    # 隐藏多余的子图
    for j in range(i+1, len(axes)):
        axes[j].set_visible(False)
    
    plt.suptitle(f'{kr_type.upper()} - Scatter Plot', fontsize=14)
    plt.tight_layout()
    save_path = os.path.join(REPORT_DIR, f'{kr_type}_scatter.png')
    plt.savefig(save_path, dpi=150, bbox_inches='tight')
    print(f"Scatter plot saved to: {save_path}")
    plt.close()


def plot_error_distribution(all_preds, all_targets, param_names, kr_type):
    """
    绘制误差分布箱线图
    """
    errors = all_preds - all_targets
    
    fig, ax = plt.subplots(figsize=(14, 6))
    bp = ax.boxplot(errors, labels=param_names, patch_artist=True)
    
    # 美化
    for patch in bp['boxes']:
        patch.set_facecolor('lightblue')
    
    ax.set_ylabel('Prediction Error (Pred - True)')
    ax.set_title(f'{kr_type.upper()} - Error Distribution')
    ax.axhline(y=0, color='r', linestyle='--', alpha=0.5)
    plt.xticks(rotation=45, ha='right')
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    
    save_path = os.path.join(REPORT_DIR, f'{kr_type}_error_boxplot.png')
    plt.savefig(save_path, dpi=150, bbox_inches='tight')
    print(f"Error distribution plot saved to: {save_path}")
    plt.close()

def calculate_accuracy_metrics(all_preds, all_targets, param_names):
    """
    计算回归任务的"精确度"指标
    """
    print("\n=== Precision Metrics ===")
    print(f"{'Param Name':<20} {'R² Score':>10} {'<5% Error':>12} {'<10% Error':>12}")
    print("-" * 60)
    
    for i, name in enumerate(param_names):
        true_vals = all_targets[:, i]
        pred_vals = all_preds[:, i]
        
        # R² Score
        r2 = r2_score(true_vals, pred_vals)
        
        # 相对误差分布
        rel_err = np.abs(pred_vals - true_vals) / (np.abs(true_vals) + 1e-8) * 100
        pct_5 = np.mean(rel_err < 5) * 100   # 误差<5%的比例
        pct_10 = np.mean(rel_err < 10) * 100 # 误差<10%的比例
        
        print(f"{name:<20} {r2:>10.4f} {pct_5:>11.1f}% {pct_10:>11.1f}%")
        
        # 判断是否达到95%精确度（自定义标准）
        if r2 >= 0.95 and pct_5 >= 80:
            status = "✅ Excellent"
        elif r2 >= 0.90 and pct_5 >= 60:
            status = "⚠️ Good"
        else:
            status = "❌ Needs Improvement"
        print(f"  Status: {status}\n")

if __name__ == '__main__':
    # 获取数据集的统计信息（用于反归一化）
    dataset = IMUDataset()
    
    # 评估KR_Kinematics
    print("\n" + "="*60)
    print("Evaluating KR_Kinematics...")
    model_kin = MultiModel(ac_dim=3, kr_dim=KR_Kinematics_dim).to(DEVICE)
    checkpoint = torch.load(os.path.join(CHECKPOINT_DIR, 'phase2_kinematics.pt'), map_location=DEVICE)
    model_kin.load_state_dict(checkpoint)
    test_loader = get_dataloaders()[2]
    
    stats_kin = {
        'mean': torch.tensor(dataset.kr_kinematics_mean, dtype=torch.float32),
        'std': torch.tensor(dataset.kr_kinematics_std, dtype=torch.float32)
    }
    
    preds_kin, targets_kin, rmse_kin, mae_kin, names_kin = evaluate_kr(
        model_kin, test_loader, 'kinematics', DEVICE, stats_kin
    )
    plot_time_series(preds_kin, targets_kin, names_kin, 'kinematics')
    plot_scatter(preds_kin, targets_kin, names_kin, 'kinematics')
    plot_error_distribution(preds_kin, targets_kin, names_kin, 'kinematics')
    
    calculate_accuracy_metrics(preds_kin, targets_kin, names_kin)

    # 评估KR_Joint
    print("\n" + "="*60)
    print("Evaluating KR_Joint...")
    model_joint = MultiModel(ac_dim=3, kr_dim=KR_Joint_dim).to(DEVICE)
    checkpoint = torch.load(os.path.join(CHECKPOINT_DIR, 'phase2_joint.pt'), map_location=DEVICE)
    model_joint.load_state_dict(checkpoint)
    
    stats_joint = {
        'mean': torch.tensor(dataset.kr_joint_mean, dtype=torch.float32),
        'std': torch.tensor(dataset.kr_joint_std, dtype=torch.float32)
    }
    
    preds_joint, targets_joint, rmse_joint, mae_joint, names_joint = evaluate_kr(
        model_joint, test_loader, 'joint', DEVICE, stats_joint
    )
    plot_time_series(preds_joint, targets_joint, names_joint, 'joint')
    plot_scatter(preds_joint, targets_joint, names_joint, 'joint')
    plot_error_distribution(preds_joint, targets_joint, names_joint, 'joint')
    
    calculate_accuracy_metrics(preds_joint, targets_joint, names_joint)


    print("\n" + "="*60)
    print("All evaluations and plots completed!")
    print(f"Plots saved to: {REPORT_DIR}")
    print("="*60)
