@echo off
chcp 65001 >nul
title Vicon+IMU+Planter 数据采集系统

echo ========================================
echo   Vicon+IMU+Planter 数据采集系统
echo ========================================
echo.

REM 检查Python环境
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到Python，请先安装Python
    pause
    exit /b 1
)

REM 检查conda环境
where conda >nul 2>&1
if not errorlevel 1 (
    echo [信息] 检测到Conda环境
    echo [信息] 尝试激活Vicon_SDK环境...
    call conda activate Vicon_SDK 2>nul
    if errorlevel 1 (
        echo [警告] 无法激活Vicon_SDK环境，将使用当前环境
    )
)

REM 检查必要模块
echo [信息] 检查依赖模块...
python -c "import vicon_dssdk" 2>nul
if errorlevel 1 (
    echo [警告] 未找到vicon_dssdk模块
    echo [信息] 请确保已正确安装Vicon SDK
)

python -c "import serial" 2>nul
if errorlevel 1 (
    echo [错误] 未找到pyserial模块
    echo [信息] 正在尝试安装...
    pip install pyserial
)

python -c "import scipy" 2>nul
if errorlevel 1 (
    echo [错误] 未找到scipy模块
    echo [信息] 正在尝试安装...
    pip install scipy
)

echo.
echo [信息] 启动数据采集系统...
echo [信息] 数据将保存到: data\
echo.

REM 启动主程序
python "%~dp0main.py"

pause