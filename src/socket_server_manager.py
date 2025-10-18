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
    List
    
)
from enum import Enum


class ConnectionType(Enum):
    SOCKET = "socket"
    MQTT = "mqtt"
    
from pathlib import Path
ROOT_DIRECTORY = Path(__file__).parent.parent
MQTT_CONFIG_PATH = str(ROOT_DIRECTORY / "config" / "yaml" / "mqtt_config.yaml")
DETECT_CONFIG_PATH = str(ROOT_DIRECTORY / "config" / "yaml" / "detect_config.yaml")
REDIS_CONFIG_PATH = str(ROOT_DIRECTORY / "config" / "yaml" / "redis_config.yaml")



from base.producer_consumer import ProducerConsumerManager
from src.socket_server import SocketServer
from base.consumer_tool_pool import ConsumerToolPool
from src.mqtt_client import MQTTClient

from agent.base.base_tool import tool


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
        devices = self.get_all_devices()
        self.logger.info(f"devices: {devices}, \n ")
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


    def _process_stored_device_data(self):
        """处理存储在设备队列中的数据"""
        try:
            # 获取所有设备ID
            devices = self.get_all_devices()
            for device_id in devices:
                device_data_list = self.get_all_device_data(device_id)
                time.sleep(5)
                self.logger.info(f"{device_id}: ------------------ \n {len(device_data_list)}")
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
            self.logger.error(f"处理存储设备数据时出错: {e}")


    def batch_pipline(self):
        ...


    def _start_consumer_worker(self):
        """实现消费者工作逻辑"""
        while self.consumer_worker_running and self._is_running:
            self._process_stored_device_data()


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
    consumer_tool_pool = ConsumerToolPool(model_paths=model_paths)
    
    
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
        topics=["/topic/sx_sleep_heart_rate_lg_02_odata", "/topic/sx_sleep_heart_rate_lg_00_odata"],
        username=mqtt_config.username,
        password=mqtt_config.password
    )
    
    
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