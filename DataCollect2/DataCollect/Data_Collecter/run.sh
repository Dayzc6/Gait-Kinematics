#!/bin/bash
# Vicon+IMU+Planter 数据采集系统启动脚本

echo "========================================"
echo "  Vicon+IMU+Planter 数据采集系统"
echo "========================================"
echo ""

# 检查Python
if ! command -v python &> /dev/null; then
    echo "[错误] 未找到Python，请先安装Python"
    exit 1
fi

echo "[信息] 检查依赖模块..."

# 检查pyserial
python -c "import serial" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "[错误] 未找到pyserial模块"
    echo "[信息] 正在尝试安装..."
    pip install pyserial
fi

# 检查scipy
python -c "import scipy" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "[错误] 未找到scipy模块"
    echo "[信息] 正在尝试安装..."
    pip install scipy
fi

echo ""
echo "[信息] 启动数据采集系统..."
echo "[信息] 数据将保存到: data/"
echo ""

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 启动主程序
python "$SCRIPT_DIR/main.py"