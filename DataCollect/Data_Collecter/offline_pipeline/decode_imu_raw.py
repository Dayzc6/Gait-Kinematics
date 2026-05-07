# -*- coding: utf-8 -*-
"""
路线2：离线解码 IMU 原始日志
输入：capture_session.py 或 capture_imu_raw.py 生成的 jsonl
输出：设备级观测 jsonl
每条观测包含：
- recv_timestamp
- device_name
- imu_data
"""
import argparse
import os
import sys

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(CURRENT_DIR)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from common import JsonlWriter, hex_to_bytes, latest_matching_file, latest_session_prefix, make_output_path, read_jsonl, session_file

try:
    from DataCollect.Data_Collecter import config
    from DataCollect.Data_Collecter.utils.protocol_imu import parse_imu_frame
except ImportError:
    import config
    from utils.protocol_imu import parse_imu_frame


def decode_imu_log(input_path: str, output_path: str):
    records = read_jsonl(input_path)
    writer = JsonlWriter(output_path)
    raw_buffer = b''
    decoded = 0
    try:
        for rec in records:
            raw_buffer += hex_to_bytes(rec['raw_hex'])
            recv_ts = rec['recv_timestamp']

            while True:
                head_idx = raw_buffer.find(b'\x55')
                if head_idx == -1:
                    break

                start_idx = head_idx - 1 if head_idx > 0 else 0
                end_idx = start_idx + config.IMU_FRAME_TOTAL_LEN
                if end_idx > len(raw_buffer):
                    break

                frame = raw_buffer[start_idx:end_idx]
                raw_buffer = raw_buffer[end_idx:]
                result = parse_imu_frame(frame)
                if not result:
                    continue

                dev_id, imu_data = result
                device_name = config.IMU_DICT.get(dev_id)
                if not device_name:
                    continue

                writer.write({
                    'recv_timestamp': recv_ts,
                    'device_name': device_name,
                    'imu_data': imu_data,
                })
                decoded += 1
    finally:
        writer.close()

    print(f'[route2] decode_imu_raw done, decoded={decoded}, file={output_path}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', help='IMU raw jsonl path')
    parser.add_argument('--output', help='decoded imu jsonl path')
    args = parser.parse_args()

    input_path = args.input
    if not input_path:
        session_prefix = latest_session_prefix()
        if session_prefix:
            candidate = session_file(session_prefix, 'imu')
            if os.path.exists(candidate):
                input_path = candidate
    if not input_path:
        input_path = latest_matching_file('imu_raw')
    if not input_path:
        raise SystemExit('No IMU raw log found')

    output_path = args.output or make_output_path('imu_decoded', '.jsonl')
    decode_imu_log(input_path, output_path)
