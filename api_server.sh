#!/bin/bash
if [ -f ".env" ]; then
    API_PORT=$(python -c "
import os
from dotenv import load_dotenv
load_dotenv()
print(os.getenv('API_PORT', '9039'))
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
else
    API_PORT=9039
    CONDA_ENV_PATH='/work/soft/anaconda3/bin/'
    CONDA_ENVIRONMENT='real_time_vital_analyze'
fi

# 从命令行参数获取 PROJECT_ROOT，如果未提供，则使用现有方式
if [ -n "$1" ]; then
    PROJECT_ROOT="$1"
else
    PROJECT_ROOT=$(dirname "$(readlink -f "$0")")
fi

check_and_kill_port() {
    local port=$1
    local pid=$(lsof -t -i :$port)

    if [ -n "$pid" ]; then
        echo "端口 $port 已被占用，正在终止进程 $pid"
        kill $pid
    else
        echo "端口 $port 未被占用"
    fi
}

check_and_kill_port $API_PORT

# 激活虚拟环境
CONDA_ENV=$CONDA_ENV_PATH
export PATH=$CONDA_ENV:$PATH
eval "$(conda shell.bash hook)"
conda init bash
conda activate $CONDA_ENVIRONMENT

timestamp=$(date +"%Y%m%d%H%M%S")
LOG_PATH=$PROJECT_ROOT/logs/api_server
LOG_FILE="$LOG_PATH/${timestamp}.log"
SOURCE_PATH=$PROJECT_ROOT/api/source

if [ ! -d "$LOG_PATH" ]; then
    # 日志目录不存在，创建它
    mkdir -p "$LOG_PATH"
fi
if [ ! -d "$SOURCE_PATH" ]; then
    # 资源文件目录不存在，创建它
    mkdir -p "$SOURCE_PATH"
fi
if [ ! -d "$FUNCTION_CALL_API_LOG" ]; then
    # function call server文件目录不存在，创建它
    mkdir -p "$FUNCTION_CALL_API_LOG"
fi
python -m api.table.init_tables
echo "日志文件路径: $LOG_FILE"
cd "$PROJECT_ROOT" || { echo "无法切换到项目目录: $PROJECT_ROOT"; exit 1; }
nohup python -m api.server.main_server -p $API_PORT > "$LOG_FILE" 2>&1 &
echo "api_server服务已在后台运行，输出日志位于: $LOG_FILE"
