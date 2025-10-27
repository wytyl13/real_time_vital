#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time    : 2025/08/22 09:22
@Author  : weiyutao
@File    : socket_server_manager.py
"""
import time
import threading
from typing import (
    Optional,
    List,
    Dict,
    Any
)
from enum import Enum
import asyncio

from tools.utils import Utils


utils = Utils()

class ConnectionType(Enum):
    SOCKET = "socket"
    MQTT = "mqtt"
    
from pathlib import Path
ROOT_DIRECTORY = Path(__file__).parent.parent
MQTT_CONFIG_PATH = str(ROOT_DIRECTORY / "config" / "yaml" / "mqtt_config.yaml")
DETECT_CONFIG_PATH = str(ROOT_DIRECTORY / "config" / "yaml" / "detect_config.yaml")
REDIS_CONFIG_PATH = str(ROOT_DIRECTORY / "config" / "yaml" / "redis_config.yaml")
SQL_CONFIG_PATH = str(ROOT_DIRECTORY / "config" / "yaml" / "sql_config.yaml")



from base.producer_consumer import ProducerConsumerManager
from src.socket_server import SocketServer
from base.consumer_tool_pool import ConsumerToolPool
from src.mqtt_client import MQTTClient

from agent.base.base_tool import tool
from src.sleep_data_storage import DataPoint

class SubscriptionStatus(str, Enum):
    """订阅状态枚举"""
    PENDING = 'pending'         # 待订阅
    SUBSCRIBED = 'subscribed'   # 已订阅
    FAILED = 'failed'           # 失败
    UNSUBSCRIBED = 'unsubscribed'  # 已取消

update_subscription_status_url = "https://ai.shunxikj.com:9039/api/device_info/update"

@tool
class SocketServerManager(ProducerConsumerManager):
    """示例实现：模拟SocketServerManager"""
    injected_data: Optional[List] = None

    def __init__(
        self,
        max_producers=20, 
        max_consumers=30, 
        production_queue_size=1000, 
        consumer_tool_pool: ConsumerToolPool = None,
        use_redis=False,
        redis_config=None,
        device_storage_type='memory',  # 'memory', 'redis', 'hybrid'
        device_storage_redis_config=None,
        device_max_queue_size=60,
        injected_data: Optional[List] = None,
    ):
        self.injected_data = injected_data
        self.socket_servers = {}
        self.mqtt_clients = {}
        self.init(
            max_producers=max_producers,
            max_consumers=max_consumers,
            production_queue_size=production_queue_size,
            consumer_tool_pool=consumer_tool_pool,
            use_redis=use_redis,
            redis_config=redis_config,
            device_storage_type=device_storage_type,
            device_storage_redis_config=device_storage_redis_config,
            device_max_queue_size=device_max_queue_size
        )
        self.device_topics = []
        self.load_topics_from_api()
        
    def load_topics_from_api(self):
        try:
            response = utils.request_url(
                url="https://ai.shunxikj.com:9039/api/device_info",
                param_dict={"subscription_status": "subscribed"}
            )
            self.device_topics = [item["topic"] for item in response]
        except Exception as e:
            import traceback
            error_info = f"Fail to exec load_topics_from_api function {traceback.format_exc()}"
            print(error_info)
            raise ValueError(error_info) from e
        

    def start_mqtt_client(self, connection_id: str, broker_host: str, broker_port: int = 8083, 
                     topics: list = None, **kwargs):
        if connection_id in self.mqtt_clients:
            self.logger.warning(f"MQTT client {connection_id} already exists")
            return
        print(f"broker_host: --------------------------------------- {broker_host}")
        production_id = f"mqtt_client_{connection_id}"
        self.production_line_locks[production_id] = threading.Lock()
        self.production_line_stop_flags[production_id] = False
        
        mqtt_client = MQTTClient(
            broker_host=broker_host,
            broker_port=broker_port,
            topics=topics or [],
            data_callback=self._classify_and_store_data,
            injected_data=self.injected_data,
            **kwargs
        )
        mqtt_client.start()
        self.mqtt_clients[connection_id] = mqtt_client
        self.active_production_lines[production_id] = {
            'connection_id': connection_id,
            'type': 'mqtt',
            'mqtt_client': mqtt_client
        }
        self.logger.info(f"Started MQTT client {connection_id} for {broker_host}:{broker_port}")


    def _classify_and_store_data(self, parse_data):
        """
        数据分类存储到固定大小滑动队列
        Args:
            parse_data: 解析后的数据，最后一个元素是device_id
        """
        device_id = parse_data[-1]
        # 2. 同时存储到设备专用队列（60秒数据缓存）
        self.put_device_data(device_id, parse_data)
        websocket_data = {
            'device_id': device_id,
            'timestamp': parse_data[0] if isinstance(parse_data, tuple) and len(parse_data) > 0 else int(time.time()),
            'breath_bpm': parse_data[1] if isinstance(parse_data, tuple) and len(parse_data) > 1 else 0,
            'breath_curve': parse_data[2] if isinstance(parse_data, tuple) and len(parse_data) > 2 else 0,
            'heart_bpm': parse_data[3] if isinstance(parse_data, tuple) and len(parse_data) > 3 else 0,
            'heart_curve': parse_data[4] if isinstance(parse_data, tuple) and len(parse_data) > 4 else 0,
            'target_distance': parse_data[5] if isinstance(parse_data, tuple) and len(parse_data) > 5 else 0,
            'signal_strength': parse_data[6] if isinstance(parse_data, tuple) and len(parse_data) > 6 else 0,
            'valid_bit_id': parse_data[7] if isinstance(parse_data, tuple) and len(parse_data) > 7 else 0,
            'body_move_energy': parse_data[8] if isinstance(parse_data, tuple) and len(parse_data) > 8 else 0,
            'body_move_range': parse_data[9] if isinstance(parse_data, tuple) and len(parse_data) > 9 else 0,
            'in_bed': parse_data[10] if isinstance(parse_data, tuple) and len(parse_data) > 10 else 0
        }
        self.redis_device_storage.publish_websocket_data(device_id=device_id, websocket_data=websocket_data)
        # devices = self.get_all_devices()
        # self.logger.info(f"devices: {devices}, \n ")
        # self.logger.info(f"devices_data: {self.get_all_device_data(devices[0])}, \n ")


    def start_socket_server(self, port: int):
        if port in self.socket_servers:
            self.logger.warning(f"Socket server on port {port} already exists")
            return
        production_id = f"socket_server_{port}"

        self.production_line_locks[production_id] = threading.Lock()

        self.production_line_stop_flags[production_id] = False
        socket_server = SocketServer(
            port=port,
            data_callback=self._classify_and_store_data,
            injected_data=self.injected_data,
        )
        socket_server.start()
        self.socket_servers[port] = socket_server
        self.active_production_lines[production_id] = {
            'port': port,
            'socket_server': socket_server
        }
        self.logger.info(f"Started socket server on port {port} with production ID {production_id}")


    def start_produce_worker(self, connection_type: str, connection_id: str = None, **kwargs):
        if connection_type == "socket" or connection_type == ConnectionType.SOCKET:
            port = kwargs.get('port')
            if not port:
                raise ValueError("Socket connection requires 'port' parameter")
            self.start_socket_server(port)
        elif connection_type == "mqtt" or connection_type == ConnectionType.MQTT:
            
            if not connection_id:
                connection_id = f"mqtt_{int(time.time())}"
            broker_host = kwargs.pop('broker_host')
            if not broker_host:
                raise ValueError("MQTT connection requires 'broker_host' parameter")
            broker_port = kwargs.pop('broker_port', 8083)
            topics = kwargs.pop('topics', [])
            if not topics:
                topics = self.device_topics
                self.logger.info(f"使用从API加载的topics: {topics}")
            else:
                self.logger.info(f"使用传递的topics: {topics}")
            print(f"broker_host: --------------------------------- {broker_host}")
            self.start_mqtt_client(connection_id, broker_host, broker_port, topics, **kwargs)
        else:
            raise ValueError(f"Unsupported connection type: {connection_type}")


    def stop_produce_worker(self, production_id):
        """停止特定的生产者"""
        if production_id in self.active_production_lines:
            connection_info = self.active_production_lines[production_id]
            if connection_info.get('type') == 'socket':
                # 停止Socket服务器的逻辑保持原样
                future = connection_info
                if hasattr(future, 'done') and not future.done():
                    future.cancel()
            elif connection_info.get('type') == 'mqtt':
                # 停止MQTT客户端
                mqtt_client = connection_info.get('mqtt_client')
                if mqtt_client:
                    mqtt_client.stop()
                connection_id = connection_info.get('connection_id')
                if connection_id and connection_id in self.mqtt_clients:
                    del self.mqtt_clients[connection_id]
            
            del self.active_production_lines[production_id]
            self.logger.info(f"停止生产者: {production_id}")


    def _store_data(self, data: DataPoint, reason: str):
        """存储数据到数据库（真正的同步版本）"""
        db_provider = self.consumer_tool_pool.get_consumer_tool("sleep_data_storage_db_save")
        if db_provider is None:
            self.logger.error("无法获取连接")
            return
        
        try:
            db_dict = data.to_db_dict()
            # 使用真正的同步方法
            result = db_provider.add_record_sync(data=db_dict)
            self.logger.info(f"存储成功 ID:{result}")
            return result
        except Exception as e:
            self.logger.error(f"存储失败: {e}")
            return None
        finally:
            self.consumer_tool_pool.release_consumer_tool("sleep_data_storage_db_save", db_provider)


    def _process_stored_device_data(self):
        """处理存储在设备队列中的数据"""
        try:
            # ========== 从统一的工具池获取存储工具 ==========
            # ========== 使用上下文管理器自动管理工具生命周期 ==========
            with self.consumer_tool_pool.get_tool("sleep_data_storage") as storage_tool:
                # 获取所有设备ID
                devices = self.get_all_devices()
                for device_id in devices:
                    device_data_list = self.get_all_device_data(device_id)
                    if not device_data_list:
                        continue
                    
                    # 使用工具执行存储判断
                    should_store, reason, latest_data = storage_tool.process_uart_data_window(
                        device_sn=device_id,
                        uart_data_list=device_data_list
                    )
                    self.logger.info(f"should_store: {should_store}, {reason}")
                    if should_store:
                        self._store_data(data=latest_data, reason=reason)
                    
                    # time.sleep(5)
                    # self.logger.info(f"{device_id}: ------------------ \n {len(device_data_list)}")
                    # self.logger.info(f"{device_id}: ------------------ \n {device_data_list}")
                    
                    """
                    批次实时数据处理管道
                    batch_result = pipline(batch_device_data)
                    批次插入实时数据
                    """
                    
                    """
                    插入实时数据测试
                    self.real_time_data_state.put([{"device_id": device_data_list[-1][-1], "data": device_data_list[-1]}])
                    self.logger.info(f"real_time_data_state: --------------- {self.real_time_data_state.get_all_devices_data()}")
                    device_data = self.real_time_data_state.get(device_id="13271C9D10004071111715B507")
                    self.logger.info(f"13271C9D10004071111715B507 data: --------------- {device_data}")
                    device_UNKNOWN_data = self.real_time_data_state.get(device_id="UNKNOWN")
                    self.logger.info(f"UNKNOWN data: --------------- {device_UNKNOWN_data}")
                    """
        except Exception as e:
            self.logger.error(f"处理存储设备数据时出错: {str(e)}")


    def batch_pipline(self):
        ...


    def _start_consumer_worker(self):
        """实现消费者工作逻辑"""
        while self.consumer_worker_running and self._is_running:
            self._process_stored_device_data()
            time.sleep(1)


    def shutdown(self):
        """关闭管理器"""
        self.logger.info("关闭SocketServerManager...")
        
        self._is_running = False
        self.consumer_worker_running = False
        
        # 停止所有生产者
        for production_id in list(self.active_production_lines.keys()):
            self.stop_produce_worker(production_id)
        
        # 停止所有MQTT客户端
        for connection_id, mqtt_client in self.mqtt_clients.items():
            try:
                mqtt_client.stop()
            except Exception as e:
                self.logger.error(f"停止MQTT客户端 {connection_id} 失败: {e}")
            self.mqtt_clients.clear()
        
        
        if self.consumer_worker_thread:
            self.consumer_worker_thread.join(timeout=5)
        
        if self.producer_pool:
            self.producer_pool.shutdown(wait=True)
        
        if self.consumer_pool:
            self.consumer_pool.shutdown(wait=True)
        
        self.logger.info("关闭完成")


    def update_subscription_status(self, topic: str, subscription_status: SubscriptionStatus) -> bool:
        try:
            result = utils.request_url(
                url=update_subscription_status_url,
                param_dict={"topic": topic, "subscription_status": subscription_status},
            )
            return True
        except Exception as e:
            raise ValueError("Fail to update subscription status ! {str(e)}") from e
        return False


    def add_topic(self, topic: str, connection_id: str = "mqtt_client_1") -> Dict[str, Any]:
        """
        添加单个topic到指定的MQTT客户端
        
        Args:
            topic: 要添加的topic
            connection_id: MQTT客户端连接ID
            
        Returns:
            Dict: 操作结果
        """
        if connection_id not in self.mqtt_clients:
            return {
                'success': False,
                'error': f'MQTT客户端 {connection_id} 不存在',
                'result': False
            }
        
        mqtt_client = self.mqtt_clients[connection_id]
        
        # 调用MQTT客户端的单个添加方法
        try:
            result = mqtt_client.add_topic(topic)
        except Exception as e:
            try:
                self.update_subscription_status(topic=topic, subscription_status="failed")
            except Exception as e:
                self.logger.info(str(e))
                raise ValueError(str(e)) from e
            raise ValueError("Fail to add topic! {str(e)}") from e
        
        # 更新manager的device_topics列表
        if result and topic not in self.device_topics:
            self.device_topics.append(topic)
        
        self.logger.info(f"添加topic到客户端 {connection_id}: {topic} -> {result}")
        try:
            self.update_subscription_status(topic=topic, subscription_status="subscribed")
        except Exception as e:
            self.logger.info(str(e))
            raise ValueError(str(e)) from e
        return {
            'success': True,
            'connection_id': connection_id,
            'topic': topic,
            'result': result,
            'current_device_topics': self.device_topics.copy(),
            'mqtt_client_topics': mqtt_client.get_subscribed_topics()
        }


    def remove_topic(self, topic: str, connection_id: str = "mqtt_client_1") -> Dict[str, Any]:
        """
        从指定的MQTT客户端移除单个topic
        
        Args:
            topic: 要移除的topic
            connection_id: MQTT客户端连接ID
            
        Returns:
            Dict: 操作结果
        """
        if connection_id not in self.mqtt_clients:
            return {
                'success': False,
                'error': f'MQTT客户端 {connection_id} 不存在',
                'result': False
            }
        
        mqtt_client = self.mqtt_clients[connection_id]
        
        # 调用MQTT客户端的单个移除方法
        result = mqtt_client.remove_topic(topic)
        
        # 更新manager的device_topics列表
        if result and topic in self.device_topics:
            self.device_topics.remove(topic)
        
        self.logger.info(f"移除topic从客户端 {connection_id}: {topic} -> {result}")
        self.update_subscription_status(topic=topic, subscription_status="unsubscribed")
        return {
            'success': True,
            'connection_id': connection_id,
            'topic': topic,
            'result': result,
            'current_device_topics': self.device_topics.copy(),
            'mqtt_client_topics': mqtt_client.get_subscribed_topics()
        }


    def add_topics_batch(self, new_topics: List[str], connection_id: str = "mqtt_client_1") -> Dict[str, Any]:
        """
        批量添加topics到指定的MQTT客户端
        
        Args:
            new_topics: 要添加的topic列表
            connection_id: MQTT客户端连接ID
            
        Returns:
            Dict: 操作结果
        """
        if connection_id not in self.mqtt_clients:
            return {
                'success': False,
                'error': f'MQTT客户端 {connection_id} 不存在',
                'results': {topic: False for topic in new_topics}
            }
        
        results = {}
        for topic in new_topics:
            single_result = self.add_topic(topic, connection_id)
            results[topic] = single_result['result'] if single_result['success'] else False
        
        self.logger.info(f"批量添加topics到客户端 {connection_id}: {results}")
        
        mqtt_client = self.mqtt_clients[connection_id]
        return {
            'success': True,
            'connection_id': connection_id,
            'results': results,
            'current_device_topics': self.device_topics.copy(),
            'mqtt_client_topics': mqtt_client.get_subscribed_topics()
        }


    def remove_topics_batch(self, topics_to_remove: List[str], connection_id: str = "mqtt_client_1") -> Dict[str, Any]:
        """
        批量从指定的MQTT客户端移除topics
        
        Args:
            topics_to_remove: 要移除的topic列表
            connection_id: MQTT客户端连接ID
            
        Returns:
            Dict: 操作结果
        """
        if connection_id not in self.mqtt_clients:
            return {
                'success': False,
                'error': f'MQTT客户端 {connection_id} 不存在',
                'results': {topic: False for topic in topics_to_remove}
            }
        
        results = {}
        for topic in topics_to_remove:
            single_result = self.remove_topic(topic, connection_id)
            results[topic] = single_result['result'] if single_result['success'] else False
        
        self.logger.info(f"批量移除topics从客户端 {connection_id}: {results}")
        
        mqtt_client = self.mqtt_clients[connection_id]
        return {
            'success': True,
            'connection_id': connection_id,
            'results': results,
            'current_device_topics': self.device_topics.copy(),
            'mqtt_client_topics': mqtt_client.get_subscribed_topics()
        }


    def get_current_topics(self, connection_id: str = "mqtt_client_1") -> Dict[str, Any]:
        """
        获取指定MQTT客户端当前订阅的topics
        
        Args:
            connection_id: MQTT客户端连接ID
            
        Returns:
            Dict: 当前topics信息
        """
        if connection_id not in self.mqtt_clients:
            return {
                'success': False,
                'error': f'MQTT客户端 {connection_id} 不存在',
                'topics': []
            }
        
        mqtt_client = self.mqtt_clients[connection_id]
        current_topics = mqtt_client.get_subscribed_topics()
        
        return {
            'success': True,
            'connection_id': connection_id,
            'topics': current_topics,
            'is_connected': mqtt_client.is_connected(),
            'topics_count': len(current_topics),
            'manager_device_topics': self.device_topics.copy()
        }


    def sync_topics_with_api(self, connection_id: str = "mqtt_client_1") -> Dict[str, Any]:
        """
        从API同步最新的topics到指定的MQTT客户端
        
        Args:
            connection_id: MQTT客户端连接ID
            
        Returns:
            Dict: 同步结果
        """
        if connection_id not in self.mqtt_clients:
            return {
                'success': False,
                'error': f'MQTT客户端 {connection_id} 不存在'
            }
        
        try:
            # 重新从API加载topics
            self.load_topics_from_api()
            
            mqtt_client = self.mqtt_clients[connection_id]
            
            # 使用MQTT客户端的sync_topics方法同步到API的topics
            sync_result = mqtt_client.sync_topics(self.device_topics)
            
            self.logger.info(f"从API同步topics到客户端 {connection_id}: {sync_result}")
            
            return {
                'success': True,
                'connection_id': connection_id,
                'api_topics': self.device_topics.copy(),
                'sync_result': sync_result,
                'api_topics_count': len(self.device_topics),
                'final_client_topics': mqtt_client.get_subscribed_topics()
            }
            
        except Exception as e:
            error_msg = f"从API同步topics失败: {e}"
            self.logger.error(error_msg)
            return {
                'success': False,
                'error': error_msg,
                'connection_id': connection_id
            }


    def get_all_mqtt_clients_topics(self) -> Dict[str, Any]:
        """
        获取所有MQTT客户端的topics信息
        
        Returns:
            Dict: 所有客户端的topics信息
        """
        all_clients_info = {}
        
        for connection_id, mqtt_client in self.mqtt_clients.items():
            all_clients_info[connection_id] = {
                'topics': mqtt_client.get_subscribed_topics(),
                'is_connected': mqtt_client.is_connected(),
                'topics_count': len(mqtt_client.get_subscribed_topics())
            }
        
        return {
            'success': True,
            'clients_count': len(self.mqtt_clients),
            'clients_info': all_clients_info,
            'manager_device_topics': self.device_topics.copy(),
            'manager_topics_count': len(self.device_topics)
        }




def create_api_app(manager_instance):
    """创建API应用"""
    from fastapi import FastAPI
    from fastapi.responses import JSONResponse
    from pydantic import BaseModel
    from typing import Optional, List
    from datetime import datetime
    
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
    
    # 复制你的所有API接口到这里...
    @app.post("/add_topic")
    async def add_topic(request: TopicRequest):
        try:
            result = manager_instance.add_topic(request.topic, request.connection_id)
            return JSONResponse(
                status_code=200,
                content={"success": True, "message": "添加topic成功", "data": result, "timestamp": datetime.now().isoformat()}
            )
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={"success": False, "message": f"添加topic失败: {e}", "timestamp": datetime.now().isoformat()}
            )


    @app.post("/remove_topic")
    async def remove_topic(request: TopicRequest):
        """删除单个topic"""
        try:
            result = manager_instance.remove_topic(request.topic, request.connection_id)
            return JSONResponse(
                status_code=200,
                content={"success": True, "message": "删除topic成功", "data": result, "timestamp": datetime.now().isoformat()}
            )
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={"success": False, "message": f"删除topic失败: {e}", "timestamp": datetime.now().isoformat()}
            )


    @app.post("/add_topics_batch")
    async def add_topics_batch(request: TopicsRequest):
        """批量添加topics"""
        try:
            result = manager_instance.add_topics_batch(request.topics, request.connection_id)
            return JSONResponse(
                status_code=200,
                content={"success": True, "message": "批量添加topics成功", "data": result, "timestamp": datetime.now().isoformat()}
            )
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={"success": False, "message": f"批量添加topics失败: {e}", "timestamp": datetime.now().isoformat()}
            )


    @app.post("/remove_topics_batch")
    async def remove_topics_batch(request: TopicsRequest):
        """批量删除topics"""
        try:
            result = manager_instance.remove_topics_batch(request.topics, request.connection_id)
            return JSONResponse(
                status_code=200,
                content={"success": True, "message": "批量删除topics成功", "data": result, "timestamp": datetime.now().isoformat()}
            )
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={"success": False, "message": f"批量删除topics失败: {e}", "timestamp": datetime.now().isoformat()}
            )


    @app.get("/get_current_topics")
    async def get_current_topics(connection_id: Optional[str] = "mqtt_client_1"):
        """获取当前订阅的topics，该方法有歧义"""
        try:
            connection_id = "mqtt_client_1" if connection_id is None else connection_id
            result = manager_instance.get_current_topics(connection_id)
            return JSONResponse(
                status_code=200,
                content={"success": True, "message": "获取当前topics成功", "data": result, "timestamp": datetime.now().isoformat()}
            )
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={"success": False, "message": f"获取当前topics失败: {e}", "timestamp": datetime.now().isoformat()}
            )


    @app.post("/get_current_topics")
    async def get_current_topics(request: ConnectionRequest):
        """获取当前订阅的topics，该方法有歧义"""
        try:
            result = manager_instance.get_current_topics(request.connection_id)
            return JSONResponse(
                status_code=200,
                content={"success": True, "message": "获取当前topics成功", "data": result, "timestamp": datetime.now().isoformat()}
            )
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={"success": False, "message": f"获取当前topics失败: {e}", "timestamp": datetime.now().isoformat()}
            )


    @app.post("/sync_topics_with_api")
    async def sync_topics_with_api(request: ConnectionRequest):
        """从API同步topics"""
        try:
            result = manager_instance.sync_topics_with_api(request.connection_id)
            return JSONResponse(
                status_code=200,
                content={"success": True, "message": "API同步topics成功", "data": result, "timestamp": datetime.now().isoformat()}
            )
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={"success": False, "message": f"API同步失败: {e}", "timestamp": datetime.now().isoformat()}
            )


    @app.get("/get_all_mqtt_clients_topics")
    async def get_all_mqtt_clients_topics():
        """获取所有MQTT客户端的topics信息"""
        try:
            result = manager_instance.get_all_mqtt_clients_topics()
            return JSONResponse(
                status_code=200,
                content={"success": True, "message": "获取所有客户端信息成功", "data": result, "timestamp": datetime.now().isoformat()}
            )
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={"success": False, "message": f"获取所有客户端信息失败: {e}", "timestamp": datetime.now().isoformat()}
            )


    @app.post("/get_all_mqtt_clients_topics")
    async def get_all_mqtt_clients_topics():
        """获取所有MQTT客户端的topics信息"""
        try:
            result = manager_instance.get_all_mqtt_clients_topics()
            return JSONResponse(
                status_code=200,
                content={"success": True, "message": "获取所有客户端信息成功", "data": result, "timestamp": datetime.now().isoformat()}
            )
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={"success": False, "message": f"获取所有客户端信息失败: {e}", "timestamp": datetime.now().isoformat()}
            )


    # 健康检查接口
    @app.get("/health")
    async def health():
        """健康检查"""
        try:
            health_data = {"status": "ok", "service": "topic_management_api"}
            return JSONResponse(
                status_code=200,
                content={"success": True, "message": "服务健康检查成功", "data": health_data, "timestamp": datetime.now().isoformat()}
            )
        except Exception as e:
            error_info = f"健康检查失败: {e}"
            return JSONResponse(
                status_code=500,
                content={"success": False, "message": error_info, "timestamp": datetime.now().isoformat()}
            )
    
    return app




def demo_usage(port: int):
    """演示不同配置的使用方式"""
    
    print("🚀 ProducerConsumerManager 设备存储演示")
    print("=" * 60)
    from base.rnn_model_info import RNNModelInfo
    from neural_network.rnn.model import LSTM
    from config.detector_config import DetectorConfig
    from agent.config.sql_config import SqlConfig
    from pathlib import Path
    import signal
    import threading
    from src.sleep_data_storage import SleepDataStorage
    from api.table.base.real_time_vital_data import RealTimeVitalData
    from agent.provider.sql_provider import SqlProvider

    # 创建停止事件
    stop_event = threading.Event()

    def signal_handler(signum, frame):
        stop_event.set()

    signal.signal(signal.SIGINT, signal_handler)  # Ctrl+C
    signal.signal(signal.SIGTERM, signal_handler)  # 终止信号
    
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
    print(f"model_paths: --------------------------------------\n {model_paths}")
    consumer_tool_pool = ConsumerToolPool(model_paths={}, total_pool_size=0)


    consumer_tool_pool.add_tool(
        tool_name="sleep_data_storage",
        tool_factory=lambda: SleepDataStorage(max_normal_interval=60.0),
        pool_size=3
    )

    consumer_tool_pool.add_tool(
        tool_name="sleep_data_storage_db_save",
        tool_factory=lambda: SqlProvider(model=RealTimeVitalData, sql_config_path=SQL_CONFIG_PATH),
        pool_size=3
    )
    
    # 配置1: 生产队列使用内存，设备存储使用内存
    print("\n📦 配置1: 全内存存储")
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
    manager1.start_produce_worker("socket", port=port)
    
    
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
    
    api_app = create_api_app(manager1)
    
    def start_api_server():
        import uvicorn
        uvicorn.run(api_app, host="0.0.0.0", port=9040)
    api_thread = threading.Thread(target=start_api_server, daemon=True)
    api_thread.start()
    print("🔥 API服务已启动在端口9040")
    
    
    # 查看设备数据
    devices = manager1.get_all_devices()
    print(f"所有设备: {devices}")
    
    # 等待停止信号
    stop_event.wait()

    # 优雅关闭
    manager1.shutdown()
    
    # for device_id in devices[:2]:  # 只看前2个设备
    #     time.sleep(1)
    #     queue_size = manager1.get_device_queue_size(device_id)
    #     print(f"设备 {device_id} 队列大小: {queue_size}")
    # time.sleep(1000000)
    # manager1.shutdown()
    
    # 配置2: 生产队列使用内存，设备存储使用Redis
    # print("\n🔄 配置2: 生产队列内存 + 设备存储Redis")
    # try:
    #     manager2 = ExampleSocketServerManager()
    #     manager2.init(
    #         max_producers=5,
    #         max_consumers=2,
    #         production_queue_size=100,
    #         consumer_tool_pool=None,
    #         use_redis=False,  # 生产队列使用内存
    #         device_storage_type='redis',  # 设备存储使用Redis
    #         device_storage_redis_config={
    #             'host': 'localhost',
    #             'port': 6379,
    #             'database': 0,
    #             'key_prefix': 'device_queue_demo'
    #         }
    #     )
        
    #     manager2._start_consumer_worker()
    #     producer_id = manager2.start_produce_worker("socket_source_2")
        
    #     time.sleep(2)
        
    #     stats = manager2.get_comprehensive_stats()
    #     print(f"统计信息: {json.dumps(stats, indent=2, ensure_ascii=False)}")
        
    #     manager2.shutdown()
        
    # except Exception as e:
    #     print(f"Redis配置失败: {e}")
    
    # # 配置3: 混合配置演示
    # print("\n🎯 配置3: 混合存储演示")
    # try:
    #     manager3 = ExampleSocketServerManager()
    #     manager3.init(
    #         max_producers=5,
    #         max_consumers=2,
    #         production_queue_size=100,
    #         consumer_tool_pool=None,
    #         use_redis=True,  # 生产队列使用Redis
    #         redis_config={
    #             'host': 'localhost',
    #             'port': 6379,
    #             'database': 1,  # 不同的数据库
    #         },
    #         device_storage_type='hybrid',  # 设备存储使用混合模式
    #         device_storage_redis_config={
    #             'host': 'localhost',
    #             'port': 6379,
    #             'database': 2,  # 设备存储用不同数据库
    #             'key_prefix': 'hybrid_device_queue'
    #         }
    #     )
        
    #     manager3._start_consumer_worker()
    #     producer_id = manager3.start_produce_worker("socket_source_3")
        
    #     time.sleep(2)
        
    #     stats = manager3.get_comprehensive_stats()
    #     print(f"统计信息: {json.dumps(stats, indent=2, ensure_ascii=False)}")
        
    #     # 演示运行时切换存储
    #     print("\n🔄 演示设备存储切换...")
    #     success = manager3.switch_device_storage('memory')
    #     print(f"切换到内存存储: {'成功' if success else '失败'}")
        
    #     if success:
    #         stats_after = manager3.get_comprehensive_stats()
    #         print(f"切换后统计: {stats_after['device_storage']}")
        
    #     manager3.shutdown()
        
    # except Exception as e:
    #     print(f"混合配置失败: {e}")


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


if __name__ == "__main__":
    # ExampleSocketServerManager(
    #     max_producers=5,
    #         max_consumers=2,
    #         production_queue_size=100,
    #         consumer_tool_pool=None,
    #         use_redis=True,  # 生产队列使用Redis
    #         redis_config={
    #             'host': 'localhost',
    #             'port': 6379,
    #             'database': 1,  # 不同的数据库
    #         },
    #         device_storage_type='hybrid',  # 设备存储使用混合模式
    #         device_storage_redis_config={
    #             'host': 'localhost',
    #             'port': 6379,
    #             'database': 2,  # 设备存储用不同数据库
    #             'key_prefix': 'hybrid_device_queue'
    #         }
    # )
    args = parse_arguments()
    demo_usage(port=args.port)