# ViconDataStream 1.13
# Vicon_SDK

import vicon_dssdk.ViconDataStream as VDS
import time

VICON_HOST_IP = "192.168.137.201:801"  # Vicon主机上的端口，在同一无线网络中的 IPv4 地址

# Kinematic Fit
def run_vicon_1_13_fixed():
    client = VDS.Client()
    print(f"正在连接至 Vicon SDK 1.13: {VICON_HOST_IP}")
    client.Connect(VICON_HOST_IP)
    
    # 启用数据流
    client.EnableSegmentData()
    
    # 【修正1】：直接使用 VDS.ServerPush
    try:
        client.SetStreamMode(0)
    except:
        pass

    print("链路已就绪，等待数据...")

    count = 0
    while count < 100:
        # 【修正2】：直接使用 VDS.Success
        if client.GetFrame():
            subjects = client.GetSubjectNames()
            print(subjects)
            if subjects:
                s_name = subjects[0]
                print(s_name)
                segs = client.GetSegmentNames(s_name)
                print(segs)
                if segs:
                    seg_name = segs[1]
                    print(seg_name)
                    # 1.13 版获取位移
                    res = client.GetSegmentGlobalTranslation(s_name, seg_name)
                    print(res)
                    
                    # 1.13 版解包：res[0]是结果, res[1]是[x,y,z], res[2]是Occluded
                    if res[0] == 1:
                        pos = res[1]
                        occluded = res[2]
                        
                        if not occluded:
                            print(f"帧 {count} | 部位: {seg_name} | X: {pos[0]:.2f}, Y: {pos[1]:.2f}, Z: {pos[2]:.2f}")
                            count += 1
                        else:
                            print(f"警告：部位 {seg_name} 被遮挡")
        time.sleep(0.1)

if __name__ == "__main__":

    run_vicon_1_13_fixed()



