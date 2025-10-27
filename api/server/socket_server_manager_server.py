#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time    : 2025/10/24 15:17
@Author  : weiyutao
@File    : socket_server_manager_server.py
"""


import logging
import sys
from fastapi import FastAPI
import uvicorn
from pathlib import Path
import signal
import threading
from pydantic import BaseModel
from typing import (
    Optional,
    Any,
    List
)
from fastapi.responses import JSONResponse
from datetime import datetime


from src.socket_server_manager import SocketServerManager
from base.rnn_model_info import RNNModelInfo
from neural_network.rnn.model import LSTM
from config.detector_config import DetectorConfig
from agent.config.sql_config import SqlConfig
from base.consumer_tool_pool import ConsumerToolPool

# ========================================================日志================================================================
# 1. 配置API日志（FastAPI + HTTP请求）
api_logger = logging.getLogger('api')
api_handler = logging.FileHandler('api.log')
api_formatter = logging.Formatter('%(asctime)s - API - %(levelname)s - %(message)s')
api_handler.setFormatter(api_formatter)
api_logger.addHandler(api_handler)
api_logger.setLevel(logging.INFO)
api_logger.propagate = False

# 2. 配置其他所有日志（Manager + MQTT + 系统）
other_logger = logging.getLogger('other')
other_handler = logging.FileHandler('manager.log')
other_formatter = logging.Formatter('%(asctime)s - OTHER - %(levelname)s - %(message)s')
other_handler.setFormatter(other_formatter)
other_logger.addHandler(other_handler)
other_logger.setLevel(logging.INFO)
other_logger.propagate = False

# 3. 配置uvicorn使用API日志
uvicorn_logger = logging.getLogger("uvicorn")
uvicorn_logger.handlers.clear()
uvicorn_logger.addHandler(api_handler)  # 使用同一个handler
uvicorn_logger.propagate = False

logging.basicConfig(handlers=[other_handler], level=logging.INFO)
# ========================================================日志================================================================

ROOT_DIRECTORY = Path(__file__).parent.parent.parent
MQTT_CONFIG_PATH = str(ROOT_DIRECTORY / "config" / "yaml" / "mqtt_config.yaml")
DETECT_CONFIG_PATH = str(ROOT_DIRECTORY / "config" / "yaml" / "detect_config.yaml")
REDIS_CONFIG_PATH = str(ROOT_DIRECTORY / "config" / "yaml" / "redis_config.yaml")


CONFIG = DetectorConfig.from_file(DETECT_CONFIG_PATH).__dict__
redis_config = SqlConfig.from_file(REDIS_CONFIG_PATH)
mqtt_config = SqlConfig.from_file(MQTT_CONFIG_PATH)
TOPIC_DICT = CONFIG['topics']
conf_dict = CONFIG["conf"]
model_path_dict = CONFIG["model_path"]
class_list_dict = CONFIG["class_list"]
topic_list = TOPIC_DICT
model_paths = {}
    
for conf_key, conf_value in conf_dict.items():
    for topic_name in topic_list:
        topic_key = conf_key + topic_name
        model_paths[topic_key] = RNNModelInfo(
            model_path="/work/ai/whoami/"+model_path_dict[topic_name],
            model_type_class=LSTM,
            classes=class_list_dict[topic_name],
            conf=conf_value[topic_name]
        )
consumer_tool_pool = ConsumerToolPool(model_paths=model_paths)



# 5. 创建manager（所有manager相关日志会去manager.log）
manager1 = SocketServerManager(
    max_producers=5,
    max_consumers=2,
    production_queue_size=100,
    consumer_tool_pool=consumer_tool_pool,
    use_redis=False,  # 生产队列使用内存/redis
    redis_config=redis_config,
    device_storage_type='memory'  # 设备存储使用内存/redis
)

# 启动Socket服务器
manager1.start_produce_worker("socket", port=9035)

# 启动MQTT客户端
manager1.start_produce_worker(
    "mqtt", 
    "mqtt_client_1", 
    broker_host=mqtt_config.host,
    broker_port=mqtt_config.port,
    # topics=["/topic/sx_sleep_heart_rate_lg_02_odata", "/topic/sx_sleep_heart_rate_lg_00_odata"],
    username=mqtt_config.username,
    password=mqtt_config.password
)


def parse_arguments():
    """解析命令行参数"""
    import argparse
    parser = argparse.ArgumentParser(description='Socket Server Manager')
    
    # 添加port参数
    parser.add_argument(
        '--port', 
        type=int, 
        default=9035, 
        help='socket server port (default: 9035)'
    )
    return parser.parse_args()


app = FastAPI(title="Topic Management API", version="1.0.0")


# 请求模型
class TopicRequest(BaseModel):
    topic: str
    connection_id: Optional[str] = "mqtt_client_1"

class TopicsRequest(BaseModel):
    topics: List[str]
    connection_id: Optional[str] = "mqtt_client_1"

class ConnectionRequest(BaseModel):
    connection_id: Optional[str] = "mqtt_client_1"


@app.post("/add_topic")
async def add_topic(request: TopicRequest):
    """添加单个topic"""
    api_logger.info(f"API请求: 添加topic {request.topic}")
    try:
        result = manager1.add_topic(request.topic, request.connection_id)
        api_logger.info(f"API响应: {result}")
        return JSONResponse(
            status_code=200,
            content={"success": True, "message": "添加topic成功", "data": result, "timestamp": datetime.now().isoformat()}
        )
    except Exception as e:
        error_info = f"添加topic失败: {e}"
        api_logger.error(error_info)
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": error_info, "timestamp": datetime.now().isoformat()}
        )

@app.delete("/remove_topic")
async def remove_topic(request: TopicRequest):
    """删除单个topic"""
    api_logger.info(f"API请求: 删除topic {request.topic}")
    try:
        result = manager1.remove_topic(request.topic, request.connection_id)
        api_logger.info(f"API响应: {result}")
        return JSONResponse(
            status_code=200,
            content={"success": True, "message": "删除topic成功", "data": result, "timestamp": datetime.now().isoformat()}
        )
    except Exception as e:
        error_info = f"删除topic失败: {e}"
        api_logger.error(error_info)
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": error_info, "timestamp": datetime.now().isoformat()}
        )

@app.post("/add_topics_batch")
async def add_topics_batch(request: TopicsRequest):
    """批量添加topics"""
    api_logger.info(f"API请求: 批量添加topics {request.topics}")
    try:
        result = manager1.add_topics_batch(request.topics, request.connection_id)
        api_logger.info(f"API响应: {result}")
        return JSONResponse(
            status_code=200,
            content={"success": True, "message": "批量添加topics成功", "data": result, "timestamp": datetime.now().isoformat()}
        )
    except Exception as e:
        error_info = f"批量添加topics失败: {e}"
        api_logger.error(error_info)
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": error_info, "timestamp": datetime.now().isoformat()}
        )

@app.delete("/remove_topics_batch")
async def remove_topics_batch(request: TopicsRequest):
    """批量删除topics"""
    api_logger.info(f"API请求: 批量删除topics {request.topics}")
    try:
        result = manager1.remove_topics_batch(request.topics, request.connection_id)
        api_logger.info(f"API响应: {result}")
        return JSONResponse(
            status_code=200,
            content={"success": True, "message": "批量删除topics成功", "data": result, "timestamp": datetime.now().isoformat()}
        )
    except Exception as e:
        error_info = f"批量删除topics失败: {e}"
        api_logger.error(error_info)
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": error_info, "timestamp": datetime.now().isoformat()}
        )

@app.get("/get_current_topics")
async def get_current_topics(connection_id: Optional[str] = "topic_manager_client"):
    """获取当前订阅的topics"""
    api_logger.info(f"API请求: 获取当前topics, connection_id={connection_id}")
    try:
        result = manager1.get_current_topics(connection_id)
        api_logger.info(f"API响应: 找到{len(result.get('topics', []))}个topics")
        return JSONResponse(
            status_code=200,
            content={"success": True, "message": "获取当前topics成功", "data": result, "timestamp": datetime.now().isoformat()}
        )
    except Exception as e:
        error_info = f"获取当前topics失败: {e}"
        api_logger.error(error_info)
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": error_info, "timestamp": datetime.now().isoformat()}
        )

@app.post("/sync_topics_with_api")
async def sync_topics_with_api(request: ConnectionRequest):
    """从API同步topics"""
    api_logger.info(f"API请求: 从API同步topics, connection_id={request.connection_id}")
    try:
        result = manager1.sync_topics_with_api(request.connection_id)
        api_logger.info(f"API响应: 同步结果 {result.get('success', False)}")
        return JSONResponse(
            status_code=200,
            content={"success": True, "message": "API同步topics成功", "data": result, "timestamp": datetime.now().isoformat()}
        )
    except Exception as e:
        error_info = f"API同步失败: {e}"
        api_logger.error(error_info)
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": error_info, "timestamp": datetime.now().isoformat()}
        )

@app.get("/get_all_mqtt_clients_topics")
async def get_all_mqtt_clients_topics():
    """获取所有MQTT客户端的topics信息"""
    api_logger.info(f"API请求: 获取所有MQTT客户端topics信息")
    try:
        result = manager1.get_all_mqtt_clients_topics()
        api_logger.info(f"API响应: 找到{result.get('clients_count', 0)}个客户端")
        return JSONResponse(
            status_code=200,
            content={"success": True, "message": "获取所有客户端信息成功", "data": result, "timestamp": datetime.now().isoformat()}
        )
    except Exception as e:
        error_info = f"获取所有客户端信息失败: {e}"
        api_logger.error(error_info)
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": error_info, "timestamp": datetime.now().isoformat()}
        )

# 健康检查接口
@app.get("/health")
async def health():
    """健康检查"""
    api_logger.info("API请求: 健康检查")
    try:
        health_data = {"status": "ok", "service": "topic_management_api"}
        return JSONResponse(
            status_code=200,
            content={"success": True, "message": "服务健康检查成功", "data": health_data, "timestamp": datetime.now().isoformat()}
        )
    except Exception as e:
        error_info = f"健康检查失败: {e}"
        api_logger.error(error_info)
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": error_info, "timestamp": datetime.now().isoformat()}
        )

if __name__ == "__main__":
    args = parse_arguments()
    uvicorn.run(app, host="0.0.0.0", port=9040)