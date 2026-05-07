# -*- coding: utf-8 -*-
"""
路线2：最小化 Vicon 采集
记录：
- frame_num
- recv_timestamp
- 可选运行时诊断
目标：尽量贴近 experiments 的 Vicon 单链路质量
"""
import os
import sys
import time

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(CURRENT_DIR)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from common import JsonlWriter, make_session_prefix

try:
    from DataCollect.Data_Collecter import config
    from DataCollect.Data_Collecter.experiments.common import connect_vicon, collect_runtime_diagnostics, print_runtime_diagnostics
except ImportError:
    import config
    from experiments.common import connect_vicon, collect_runtime_diagnostics, print_runtime_diagnostics

DURATION_SECONDS = 20


def run_capture():
    output_prefix = make_session_prefix('vicon_minimal')
    output_path = output_prefix + '.jsonl'
    writer = JsonlWriter(output_path)
    client = connect_vicon(enable_segment=False, enable_marker=True)
    try:
        diagnostics = collect_runtime_diagnostics(client)
        print_runtime_diagnostics(diagnostics, 'route2_capture_vicon_minimal')

        start = time.time()
        count = 0
        while time.time() - start < DURATION_SECONDS:
            if client.GetFrame():
                recv_ts = time.time()
                frame_num = client.GetFrameNumber()
                try:
                    frame_rate = client.GetFrameRate()
                except Exception:
                    frame_rate = None
                writer.write({
                    'recv_timestamp': recv_ts,
                    'frame_num': frame_num,
                    'frame_rate': frame_rate,
                })
                count += 1

        print(f'[route2] Vicon 最小采集完成，frames={count}, file={output_path}')
    finally:
        writer.close()
        client.Disconnect()


if __name__ == '__main__':
    run_capture()
