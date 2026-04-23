# 【收割者】100Hz 定时进程：抓取快照并压入磁盘队列
import multiprocessing
import time
import numpy as np


def sync_master_loop(shared_dict, output_queue, stop_event):
    interval = 0.01  # 100Hz 严格同步
    next_tick = time.perf_counter()
    
    while not stop_event.is_set():
        # 高精度定时对齐
        while time.perf_counter() < next_tick:
            pass
        
        # --- 瞬间收割所有传感器快照 ---
        # 即使某个硬件现在没数据，这里直接取 shared_dict 里的旧值（Zero-Order Hold）



        
        now = time.time()
        v_data = shared_dict.get('vicon')
        i_data = shared_dict.get('imu')
        f_l_data = shared_dict.get('foot_left')
        f_r_data = shared_dict.get('foot_right')
        
        # 展平所有字典，拼成一个巨大的 List (Row)
        full_row = [now] + flatten(v_data) + flatten(i_data) + f_l_data + f_r_data
        
        # 丢给磁盘进程处理，主进程立刻进入下一个循环
        output_queue.put(full_row)
        
        next_tick += interval

