# -*- coding: utf-8 -*-
"""
路线2：离线解码 Planter 原始日志
输入：capture_session.py 或 capture_planter_raw.py 生成的 jsonl
输出：左右脚观测 jsonl
每条观测包含：
- recv_timestamp
- side
- values
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
    from DataCollect.Data_Collecter.utils.protocol_planter import parse_planter_frame
except ImportError:
    import config
    from utils.protocol_planter import parse_planter_frame


def decode_planter_log(input_path: str, output_path: str):
    records = read_jsonl(input_path)
    writer = JsonlWriter(output_path)
    buffers = {'Left': bytearray(), 'Right': bytearray()}
    decoded = 0
    try:
        for rec in records:
            side = rec['side']
            buffers[side].extend(hex_to_bytes(rec['raw_hex']))
            recv_ts = rec['recv_timestamp']
            raw_buffer = buffers[side]

            while True:
                while raw_buffer and raw_buffer[0] != config.PLANTER_FRAME_HEADER:
                    raw_buffer.pop(0)

                if len(raw_buffer) < 3:
                    break

                    
                foot_id = raw_buffer[1]
                if foot_id not in (0x01, 0x02):
                    raw_buffer.pop(0)
                    continue

                frame = None
                for frame_len in config.PLANTER_FRAME_LENGTH_CANDIDATES:
                    if len(raw_buffer) >= frame_len:
                        frame = bytes(raw_buffer[:frame_len])
                        del raw_buffer[:frame_len]
                        break

                if frame is None:
                    break

                result = parse_planter_frame(frame)
                if not result:
                    continue

                parsed_side, values = result
                writer.write({
                    'recv_timestamp': recv_ts,
                    'side': parsed_side,
                    'values': values,
                })
                decoded += 1
    finally:
        writer.close()

    print(f'[route2] decode_planter_raw done, decoded={decoded}, file={output_path}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', help='planter raw jsonl path')
    parser.add_argument('--output', help='decoded planter jsonl path')
    args = parser.parse_args()

    input_path = args.input
    if not input_path:
        session_prefix = latest_session_prefix()
        if session_prefix:
            candidate = session_file(session_prefix, 'planter')
            if os.path.exists(candidate):
                input_path = candidate
    if not input_path:
        input_path = latest_matching_file('planter_raw')
    if not input_path:
        raise SystemExit('No Planter raw log found')

    output_path = args.output or make_output_path('planter_decoded', '.jsonl')
    decode_planter_log(input_path, output_path)
