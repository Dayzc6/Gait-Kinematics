#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "DataStreamClient.h" // 确保头文件在包含路径中 [cite: 81, 97]

int main() {
    // 1. 创建客户端句柄 [cite: 5]
    CClient * pClient = Client_Create();
    
    // 配置服务器地址
    const char* HostName = "192.168.137.113:801"; 
    printf("正在连接到: %s...\n", HostName);

    // 2. 建立连接 [cite: 5]
    COutput_Connect ConnectOutput = Client_Connect(pClient, HostName);
    if (ConnectOutput.Result != Success) {
        printf("连接失败！错误代码: %d\n", ConnectOutput.Result);
        Client_Destroy(pClient);
        return -1;
    }

    // 3. 启用需要的数据类型 [cite: 6]
    Client_EnableSegmentData(pClient);
    
    // 4. 设置流模式为推送模式 (推荐实时分析使用) [cite: 9]
    // 注意：1.13 C 接口直接使用枚举常量名
    Client_SetStreamMode(pClient, ServerPush);

    printf("开始接收数据...\n");

    for (int i = 0; i < 100; ++i) {
        // 5. 获取新帧 [cite: 9]
        if (Client_GetFrame(pClient) == Success) {
            
            // 获取第一个受试者的名称
            char SubjectName[128];
            // 假设已知受试者索引为 0 [cite: 10]
            if (Client_GetSubjectName(pClient, 0, 128, SubjectName) == Success) {
                
                // 6. 获取特定段（如 R_Femur）的全局坐标 [cite: 4]
                COutput_GetSegmentGlobalTranslation Trans;
                const char* SegmentName = "R_Femur";
                
                Client_GetSegmentGlobalTranslation(pClient, SubjectName, SegmentName, &Trans);
                
                if (Trans.Result == Success) {
                    if (!Trans.Occluded) {
                        printf("帧: %d | %s: X=%.2f, Y=%.2f, Z=%.2f\n", 
                                i, SegmentName, Trans.Translation[0], Trans.Translation[1], Trans.Translation[2]);
                    } else {
                        printf("帧: %d | %s 被遮挡 (Occluded)\n", i, SegmentName);
                    }
                }
            }
        }
    }

    // 7. 断开连接并销毁客户端 [cite: 5]
    Client_Disconnect(pClient);
    Client_Destroy(pClient);
    
    return 0;
}



