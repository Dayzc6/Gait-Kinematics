"""
将CSV文件的中文列名改为英文
"""
import pandas as pd
import os

COLUMN_RENAME = {
    '绝对时间戳(s)': 'timestamp',
    '上身角度': 'torso_angle',
    '左髋角度': 'left_hip_angle',
    '左膝角度': 'left_knee_angle',
    '左踝角度': 'left_ankle_angle',
    '右髋角度': 'right_hip_angle',
    '右膝角度': 'right_knee_angle',
    '右踝角度': 'right_ankle_angle',
    'left pct stance (%GC)': 'left_pct_stance',
    'left pct swing (%GC)': 'left_pct_swing',
    'right pct stance (%GC)': 'right_pct_stance',
    'right pct swing (%GC)': 'right_pct_swing',
    'step frequency (steps/min)': 'step_frequency',
    'step length (cm)': 'step_length',
    'left step length (cm)': 'left_step_length',
    'right step length (cm)': 'right_step_length',
    'left stride length (cm)': 'left_stride_length',
    'right stride length (cm)': 'right_stride_length',
    'left step speed (m/s)': 'left_step_speed',
    'right step speed (m/s)': 'right_step_speed',
    'step width (cm)': 'step_width',
    'cycle (s)': 'cycle_time',
    'phase_label': 'phase_label',
}

def rename_columns(csv_path):
    df = pd.read_csv(csv_path)
    df = df.rename(columns=COLUMN_RENAME)
    df.to_csv(csv_path, index=False)
    return df.columns[:20].tolist()

if __name__ == '__main__':
    data_dir = r'E:\code\3D-position\Reproduction\AIL-KE\data\data_csv'
    for f in os.listdir(data_dir):
        if f.endswith('_merged.csv'):
            filepath = os.path.join(data_dir, f)
            cols = rename_columns(filepath)
            print(f'{f}: 已修改')
            print(f'  前几列: {cols[:8]}')