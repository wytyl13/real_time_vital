#!/bin/bash
if [ -f ".env" ]; then
    SOCKET_PORT=$(python -c "
import os
from dotenv import load_dotenv
load_dotenv()
print(os.getenv('SOCKET_PORT', '9035'))
")
    CONDA_ENV_PATH=$(python -c "
import os
from dotenv import load_dotenv
load_dotenv()
print(os.getenv('CONDA_ENV_PATH', '/work/soft/anaconda3/bin/'))
")
    CONDA_ENVIRONMENT=$(python -c "
import os
from dotenv import load_dotenv
load_dotenv()
print(os.getenv('CONDA_ENVIRONMENT', 'real_time_vital_analyze'))
")
    WEBSOCET_MANAGER_PORT=$(python -c "
import os
from dotenv import load_dotenv
load_dotenv()
print(os.getenv('WEBSOCET_MANAGER_PORT', '9037'))
")
else
    API_PORT=9035
    CONDA_ENV_PATH='/work/soft/anaconda3/bin/'
    CONDA_ENVIRONMENT='real_time_vital_analyze'
    WEBSOCET_MANAGER_PORT=9037
fi

# 从命令行参数获取 PROJECT_ROOT，如果未提供，则使用现有方式
if [ -n "$1" ]; then
    PROJECT_ROOT="$1"
else
    PROJECT_ROOT=$(dirname "$(readlink -f "$0")")
fi

kill_port() {
    local port=$1
    local pid=$(lsof -ti:$port)
    
    if [ -n "$pid" ]; then
        echo "终止占用端口 $port 的进程: $pid"
        kill -9 $pid && echo "成功" || echo "失败"
    else
        echo "端口 $port 未被占用"
    fi
}

kill_port 9036
kill_port $SOCKET_PORT
kill_port $WEBSOCET_MANAGER_PORT

# 激活虚拟环境
CONDA_ENV=$CONDA_ENV_PATH
export PATH=$CONDA_ENV:$PATH
eval "$(conda shell.bash hook)"
conda init bash
conda activate $CONDA_ENVIRONMENT

timestamp=$(date +"%Y%m%d%H%M%S")
SOCKET_LOG_PATH=$PROJECT_ROOT/logs/socket_server
SOCKET_LOG_FILE="$SOCKET_LOG_PATH/${timestamp}.log"

SOURCE_PATH=$PROJECT_ROOT/api/source
WEBSOCKET_LOG_PATH=$PROJECT_ROOT/logs/websocket_server
WEBSOCKET_LOG_FILE=$WEBSOCKET_LOG_PATH/${timestamp}.log

if [ ! -d "$LOG_PATH" ]; then
    # 日志目录不存在，创建它
    mkdir -p "$SOCKET_LOG_PATH"
fi
if [ ! -d "$SOURCE_PATH" ]; then
    # 资源文件目录不存在，创建它
    mkdir -p "$SOURCE_PATH"
fi
if [ ! -d "$WEBSOCKET_LOG_PATH" ]; then
    # function call server文件目录不存在，创建它
    mkdir -p "$WEBSOCKET_LOG_PATH"
fi
cd "$PROJECT_ROOT" || { echo "无法切换到项目目录: $PROJECT_ROOT"; exit 1; }

nohup python -m src.socket_server_manager --port $SOCKET_PORT > "$SOCKET_LOG_FILE" 2>&1 &
nohup python -m src.websocket_server --websocket_manager_port $WEBSOCET_MANAGER_PORT > "$WEBSOCKET_LOG_FILE" 2>&1 &
echo "socket_manager_server服务已在后台运行，输出日志位于: $SOCKET_LOG_FILE"
echo "websocket_server服务已在后台运行，输出日志位于: $WEBSOCKET_LOG_FILE"
