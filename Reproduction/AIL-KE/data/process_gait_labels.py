"""
步态相位标签处理脚本
将百分比数据转换为分类标签：
- 类别0: 左脚支撑期
- 类别1: 右脚支撑期
- 类别2: 双支撑期
"""
import pandas as pd
import numpy as np
import os

def generate_phase_labels(csv_path):
    """
    根据步态参数生成相位标签

    Args:
        csv_path: CSV文件路径

    Returns:
        phase_labels: 数组，值为0(左支撑), 1(右支撑), 2(双支撑)
    """
    df = pd.read_csv(csv_path)

    left_pct = df['left pct stance (%GC)'].iloc[0] / 100
    right_pct = df['right pct stance (%GC)'].iloc[0] / 100
    cycle = df['cycle (s)'].iloc[0]
    start_time = df['绝对时间戳(s)'].iloc[0]

    timestamps = df['绝对时间戳(s)'].values
    circles = ((timestamps - start_time) % cycle) / cycle

    phase_offset = 0.5
    phase_labels = np.zeros(len(df), dtype=int)

    for i in range(len(df)):
        c = circles[i]
        left_c = c
        right_c = (c + phase_offset) % 1.0

        left_stance = left_c < left_pct
        right_stance = right_c < right_pct

        if left_stance and right_stance:
            phase_labels[i] = 2
        elif left_stance and not right_stance:
            phase_labels[i] = 0
        elif not left_stance and right_stance:
            phase_labels[i] = 1
        else:
            phase_labels[i] = 1

    return phase_labels


def process_all_files(data_dir):
    """
    处理目录下所有CSV文件

    Args:
        data_dir: 数据目录路径
    """
    files_processed = []

    for filename in os.listdir(data_dir):
        if filename.endswith('_merged.csv'):
            filepath = os.path.join(data_dir, filename)
            print(f'处理: {filename}')

            phase_labels = generate_phase_labels(filepath)

            df = pd.read_csv(filepath)
            df['phase_label'] = phase_labels
            df.to_csv(filepath, index=False)

            counts = np.bincount(phase_labels, minlength=3)
            total = len(df)
            print(f'  标签分布: 左支撑={counts[0]}({counts[0]/total*100:.1f}%), '
                  f'右支撑={counts[1]}({counts[1]/total*100:.1f}%), '
                  f'双支撑={counts[2]}({counts[2]/total*100:.1f}%)')

            files_processed.append(filename)

    print(f'\n处理完成，共 {len(files_processed)} 个文件')


def verify_labels(data_dir):
    """
    验证标签正确性（通过IMU数据）

    Args:
        data_dir: 数据目录路径
    """
    filepath = os.path.join(data_dir, '1.8kmh1_merged.csv')
    df = pd.read_csv(filepath)

    labels = df['phase_label'].values

    print('\n=== 验证标签正确性 ===')
    print('\n左腿IMU (imu3_ang_x) 在各类别的均值:')
    for label in range(3):
        mask = labels == label
        imu_data = df['imu3ang_x'][mask]
        print(f'  类别{label}: {imu_data.mean():.2f} (n={len(imu_data)})')

    print('\n右腿IMU (imu6_ang_x) 在各类别的均值:')
    for label in range(3):
        mask = labels == label
        imu_data = df['imu6ang_x'][mask]
        print(f'  类别{label}: {imu_data.mean():.2f} (n={len(imu_data)})')


if __name__ == '__main__':
    data_dir = r'E:\code\3D-position\Reproduction\AIL-KE\data\data_csv'
    process_all_files(data_dir)
    verify_labels(data_dir)