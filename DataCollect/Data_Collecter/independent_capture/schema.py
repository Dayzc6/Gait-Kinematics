# -*- coding: utf-8 -*-
"""
independent_capture 统一数据集 schema
- Vicon / IMU / Planter 分开独立输出
- 字段命名尽量贴近现有主数据集风格
- 现阶段只服务采集输出，不包含跨模态同步字段
"""
from DataCollect.Data_Collecter.independent_capture import local_config as config


def generate_vicon_headers(seg_names, marker_names):
    headers = [
        'Session_ID',
        'Trial_ID',
        'Subject_ID',
        'Timestamp',
        'Vicon_Recv_Timestamp',
        'Vicon_Recv_Timestamp_Mono',
        'Vicon_Frame_Num',
        'Vicon_Subject_Name',
        'Vicon_Gap_Flag',
        'Vicon_Gap_Size',
        'Vicon_Original_Valid_Flag',
    ]

    for seg in seg_names:
        headers.extend([
            f'Vicon_{seg}_Occluded_Flag',
            f'Vicon_{seg}_X',
            f'Vicon_{seg}_Y',
            f'Vicon_{seg}_Z',
        ])

    for marker in marker_names:
        headers.extend([
            f'Vicon_{marker}_X',
            f'Vicon_{marker}_Y',
            f'Vicon_{marker}_Z',
        ])

    return headers


IMU_HEADERS = [
    'Session_ID',
    'Trial_ID',
    'Subject_ID',
    'Timestamp',
    'IMU_Recv_Timestamp',
    'IMU_Recv_Timestamp_Mono',
    'IMU_Device_ID',
    'IMU_Device_Name',
    'IMU_Device_Seq',
    'IMU_Parse_OK_Flag',
    'IMU_Acc_X',
    'IMU_Acc_Y',
    'IMU_Acc_Z',
    'IMU_Gyro_X',
    'IMU_Gyro_Y',
    'IMU_Gyro_Z',
    'IMU_Roll',
    'IMU_Pitch',
    'IMU_Yaw',
    'IMU_Quat_x',
    'IMU_Quat_y',
    'IMU_Quat_z',
    'IMU_Quat_w',
]


PLANTER_HEADERS = [
    'Session_ID',
    'Trial_ID',
    'Subject_ID',
    'Timestamp',
    'Planter_Recv_Timestamp',
    'Planter_Recv_Timestamp_Mono',
    'Planter_Side',
    'Planter_Side_Seq',
    'Planter_Read_Seq',
    'Planter_Candidate_Frame_Seq',
    'Planter_Parse_OK_Flag',
    'Planter_Init_OK_Flag',
    'Planter_Frame_Length',
    'Planter_Frame_Length_Mode',
    'Planter_All_Zero_Flag',
    'Planter_Review_Flag',
] + [f'Planter_{i}' for i in range(config.PLANTER_SENSOR_POINTS)]
