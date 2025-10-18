#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time    : 2025/08/21 17:09
@Author  : weiyutao
@File    : producer_consumer.py
集成设备队列存储的ProducerConsumerManager
"""

import threading
import queue
import json
import time
from concurrent.futures import ThreadPoolExecutor
from typing import (
    AsyncGenerator,
    AsyncIterator,
    Dict,
    Iterator,
    Optional,
    Tuple,
    Union,
    overload,
    Generic,
    TypeVar,
    Any,
    Type,
    List
)
from abc import ABC, abstractmethod
from pydantic import BaseModel, Field
from pathlib import Path


from base.consumer_tool_pool import ConsumerToolPool
from base.thread_safe_dict import ThreadSafeDict
from base.memory_manager import MemoryMonitor
from base.bound_thread_pool import BoundedThreadPoolExecutor

# 导入设备存储组件
from base.device_queue_storage_interface import DeviceQueueStorageInterface
from base.device_queue_storage_factory import DeviceQueueStorageFactory
from base.redis_device_queue_storage import RedisDeviceQueueStorage

from agent.config.sql_config import SqlConfig
from agent.base.base_tool import tool

from agent.utils.utils import Utils

utils = Utils()

environment = utils.load_project_env()

ROOT_DIRECTORY = Path(__file__).parent.parent
REDIS_CONFIG_PATH = str(ROOT_DIRECTORY / "config" / "yaml" / "redis.yaml")
REDIS_CONFIG_PATH = environment["REDIS_CONFIG_PATH"] if "REDIS_CONFIG_PATH" in environment else REDIS_CONFIG_PATH


@tool
class UnifiedQueue:
    """统一的设备数据存储接口，支持内存和Redis两种后端，每个设备只存储最新数据"""

    def __init__(self, use_redis=False, redis_config=None, queue_name="device_data"):
        """
        初始化UnifiedQueue
        
        Args:
            use_redis: 是否使用Redis后端
            redis_config: Redis配置
            queue_name: 存储键名前缀
        """
        self.use_redis = use_redis
        self.queue_name = queue_name
        self._lock = threading.RLock()
        
        if use_redis:
            self._init_redis(redis_config or {})
        else:
            self._init_memory_storage()


    def _init_memory_storage(self):
        """初始化内存存储"""
        self.device_data = {}  # {device_id: {'data': data, 'timestamp': timestamp}}
        self.redis_client = None
        self.logger.info("Memory-based device data storage initialized")


    def _init_redis(self, redis_config):
        """初始化Redis存储"""
        try:
            import redis
            self.redis_client = redis.Redis(
                host=redis_config.host,
                port=redis_config.port,
                db=redis_config.database,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5
            )
            # 测试连接
            self.redis_client.ping()
            self.device_data = None
            self.device_set_key = f"{self.queue_name}:devices"
            self.logger.info(f"Redis connected for device data storage: {self.queue_name}")
        except Exception as e:
            import traceback
            self.logger.error(f"Redis connection failed: {e}, {traceback.format_exc()} falling back to memory storage")
            self.use_redis = False
            self._init_memory_storage()


    def put(self, device_data: Union[Dict[str, Any], List[Dict[str, Any]]]) -> bool:
        """
        统一的put接口，支持单条和多条数据，每个设备只保存最新数据
        
        Args:
            device_data: 
                - 单条数据: {'device_id': 'xxx', 'data': {...}}
                - 多条数据: [{'device_id': 'xxx', 'data': {...}}, ...]
                
        Returns:
            bool: 是否成功
        """
        try:
            # 统一处理为列表格式
            if isinstance(device_data, dict):
                device_data_list = [device_data]
            elif isinstance(device_data, list):
                device_data_list = device_data
            else:
                self.logger.error(f"Invalid data format: {type(device_data)}")
                return False
            
            # 批量处理
            success_count = 0
            current_time = time.time()
            
            for item in device_data_list:
                if not isinstance(item, dict) or 'device_id' not in item or 'data' not in item:
                    self.logger.error(f"Invalid item format: {item}")
                    continue
                
                device_id = item['device_id']
                data = item['data']
                
                if self.use_redis:
                    if self._redis_put_device_data(device_id, data, current_time):
                        success_count += 1
                else:
                    if self._memory_put_device_data(device_id, data, current_time):
                        success_count += 1
            
            return success_count == len(device_data_list)
            
        except Exception as e:
            self.logger.error(f"Put operation failed: {e}")
            return False


    def get(self, device_id: str) -> Optional[Any]:
        """获取指定设备的数据"""
        if self.use_redis:
            return self._redis_get_device_data(device_id)
        else:
            return self._memory_get_device_data(device_id)


    def get_with_timestamp(self, device_id: str) -> Optional[Dict[str, Any]]:
        """获取指定设备的数据和时间戳"""
        if self.use_redis:
            return self._redis_get_device_data_with_timestamp(device_id)
        else:
            return self._memory_get_device_data_with_timestamp(device_id)


    def exists(self, device_id: str) -> bool:
        """检查设备是否存在数据"""
        return self.get(device_id) is not None


    def get_all_devices(self) -> List[str]:
        """获取所有设备ID列表"""
        if self.use_redis:
            return self._redis_get_all_devices()
        else:
            return self._memory_get_all_devices()


    def get_all_devices_data(self) -> Dict[str, Any]:
        """获取所有设备的数据"""
        result = {}
        devices = self.get_all_devices()
        
        for device_id in devices:
            data = self.get(device_id)
            if data is not None:
                result[device_id] = data
        
        return result


    def get_all_devices_with_timestamp(self) -> Dict[str, Dict[str, Any]]:
        """获取所有设备的数据和时间戳"""
        result = {}
        devices = self.get_all_devices()
        
        for device_id in devices:
            data_with_ts = self.get_with_timestamp(device_id)
            if data_with_ts is not None:
                result[device_id] = data_with_ts
        
        return result


    def delete_device(self, device_id: str) -> bool:
        """删除指定设备的数据"""
        if self.use_redis:
            return self._redis_delete_device(device_id)
        else:
            return self._memory_delete_device(device_id)


    def clear_all(self):
        """清空所有设备数据"""
        if self.use_redis:
            self._redis_clear_all()
        else:
            self._memory_clear_all()


    def device_count(self) -> int:
        """获取设备总数"""
        return len(self.get_all_devices())


    # Memory实现
    def _memory_put_device_data(self, device_id: str, data: Any, timestamp: float) -> bool:
        """内存存储设备数据（覆盖式）"""
        try:
            with self._lock:
                self.device_data[device_id] = {
                    'data': data,
                    'timestamp': timestamp
                }
                return True
        except Exception as e:
            self.logger.error(f"Memory put device data error: {e}")
            return False


    def _memory_get_device_data(self, device_id: str) -> Optional[Any]:
        """内存获取设备数据"""
        try:
            with self._lock:
                if device_id not in self.device_data:
                    return None
                return self.device_data[device_id]['data']
        except Exception as e:
            self.logger.error(f"Memory get device data error: {e}")
            return None


    def _memory_get_device_data_with_timestamp(self, device_id: str) -> Optional[Dict[str, Any]]:
        """内存获取设备数据和时间戳"""
        try:
            with self._lock:
                if device_id not in self.device_data:
                    return None
                return self.device_data[device_id].copy()
        except Exception as e:
            self.logger.error(f"Memory get device data with timestamp error: {e}")
            return None


    def _memory_get_all_devices(self) -> List[str]:
        """内存获取所有设备ID"""
        with self._lock:
            return list(self.device_data.keys())


    def _memory_delete_device(self, device_id: str) -> bool:
        """内存删除设备数据"""
        try:
            with self._lock:
                if device_id in self.device_data:
                    del self.device_data[device_id]
                    return True
                return False
        except Exception as e:
            self.logger.error(f"Memory delete device error: {e}")
            return False


    def _memory_clear_all(self):
        """内存清空所有数据"""
        try:
            with self._lock:
                self.device_data.clear()
        except Exception as e:
            self.logger.error(f"Memory clear all error: {e}")


    # Redis实现
    def _get_device_key(self, device_id: str) -> str:
        """获取设备在Redis中的键名"""
        return f"{self.queue_name}:{device_id}"


    def _redis_put_device_data(self, device_id: str, data: Any, timestamp: float) -> bool:
        """Redis存储设备数据（覆盖式）"""
        try:
            device_key = self._get_device_key(device_id)
            
            # 序列化数据
            serialized_data = json.dumps({
                'data': data,
                'timestamp': timestamp
            })
            
            # 使用Redis管道
            pipe = self.redis_client.pipeline()
            
            # 添加到设备集合
            pipe.sadd(self.device_set_key, device_id)
            
            # 直接设置设备数据（覆盖）
            pipe.set(device_key, serialized_data)
            
            # 设置过期时间（可选，防止数据过期）
            pipe.expire(device_key, 3600)  # 1小时过期
            
            # 执行管道
            pipe.execute()
            
            return True
        except Exception as e:
            self.logger.error(f"Redis put device data error: {e}")
            return False


    def _redis_get_device_data(self, device_id: str) -> Optional[Any]:
        """Redis获取设备数据"""
        try:
            device_key = self._get_device_key(device_id)
            serialized_data = self.redis_client.get(device_key)
            
            if serialized_data is None:
                return None
            
            # 反序列化数据
            data_obj = json.loads(serialized_data)
            return data_obj['data']
        except Exception as e:
            self.logger.error(f"Redis get device data error: {e}")
            return None


    def _redis_get_device_data_with_timestamp(self, device_id: str) -> Optional[Dict[str, Any]]:
        """Redis获取设备数据和时间戳"""
        try:
            device_key = self._get_device_key(device_id)
            serialized_data = self.redis_client.get(device_key)
            
            if serialized_data is None:
                return None
            
            # 反序列化数据
            return json.loads(serialized_data)
        except Exception as e:
            self.logger.error(f"Redis get device data with timestamp error: {e}")
            return None


    def _redis_get_all_devices(self) -> List[str]:
        """Redis获取所有设备ID"""
        try:
            devices = list(self.redis_client.smembers(self.device_set_key))
            # 过滤掉不存在数据的设备
            valid_devices = []
            for device_id in devices:
                device_key = self._get_device_key(device_id)
                if self.redis_client.exists(device_key):
                    valid_devices.append(device_id)
                else:
                    # 清理无效设备
                    self.redis_client.srem(self.device_set_key, device_id)
            return valid_devices
        except Exception as e:
            self.logger.error(f"Redis get all devices error: {e}")
            return []


    def _redis_delete_device(self, device_id: str) -> bool:
        """Redis删除设备数据"""
        try:
            device_key = self._get_device_key(device_id)
            
            # 使用管道删除
            pipe = self.redis_client.pipeline()
            pipe.delete(device_key)
            pipe.srem(self.device_set_key, device_id)
            results = pipe.execute()
            
            return results[0] > 0  # 返回是否确实删除了数据
        except Exception as e:
            self.logger.error(f"Redis delete device error: {e}")
            return False


    def _redis_clear_all(self):
        """Redis清空所有数据"""
        try:
            devices = list(self.redis_client.smembers(self.device_set_key))
            if not devices:
                return
                
            # 使用管道删除所有设备数据
            pipe = self.redis_client.pipeline()
            for device_id in devices:
                device_key = self._get_device_key(device_id)
                pipe.delete(device_key)
            pipe.delete(self.device_set_key)
            pipe.execute()
            
            self.logger.info(f"Redis cleared all data for {len(devices)} devices")
        except Exception as e:
            self.logger.error(f"Redis clear all error: {e}")


    # 统计和管理方法
    def get_stats(self) -> Dict[str, Any]:
        """获取存储统计信息"""
        try:
            devices = self.get_all_devices()
            stats = {
                'storage_type': 'redis' if self.use_redis else 'memory',
                'total_devices': len(devices),
                'device_list': devices
            }
            
            return stats
        except Exception as e:
            self.logger.error(f"Get stats error: {e}")
            return {
                'storage_type': 'redis' if self.use_redis else 'memory',
                'error': str(e)
            }


    async def execute(self):
        ...


@tool
class ProducerConsumerManager:
    """生产者消费者管理器，支持设备队列存储"""

    def init(self, 
             max_producers=20, 
             max_consumers=30, 
             production_queue_size=1000, 
             consumer_tool_pool: ConsumerToolPool = None,
             # 原有Redis配置（用于生产队列）
             use_redis=False,
             redis_config=None,
             # 新增：设备存储配置
             device_storage_type='memory',  # 'memory', 'redis', 'hybrid'
             device_storage_redis_config=None,
             device_max_queue_size=60):  # 每个设备最多60秒数据
        
        self.active_production_lines: Dict[str, Any] = ThreadSafeDict()
        self.production_line_locks: Dict[str, Any] = ThreadSafeDict()
        self.production_line_stop_flags: Dict[str, Any] = ThreadSafeDict()
        self.memory_monitor: MemoryMonitor = MemoryMonitor()  # 内存管理
        self.producer_pool: ThreadPoolExecutor = None
        self.consumer_pool: BoundedThreadPoolExecutor = None
        self.production_queue: UnifiedQueue = None  # 统一队列
        # 新增：设备队列存储
        self.device_storage: DeviceQueueStorageInterface = None
        self.consumer_worker_running: bool = True
        self.consumer_worker_thread: threading.Thread = None
        self.consumer_tool_pool: Any = None
        self._is_running: bool = None
        """增强的生产者消费者管理器初始化
        
        Args:
            max_producers: 生产者线程池大小
            max_consumers: 消费者线程池大小  
            production_queue_size: 生产队列大小
            consumer_tool_pool: 消费者工具池
            use_redis: 生产队列是否使用Redis
            redis_config: 生产队列Redis配置
            device_storage_type: 设备存储类型 ('memory', 'redis', 'hybrid')
            device_storage_redis_config: 设备存储Redis配置（可与生产队列Redis不同）
            device_max_queue_size: 每个设备最大队列大小（通常60秒数据）
        """

        self.producer_pool = ThreadPoolExecutor(max_workers=max_producers)
        self.consumer_pool = BoundedThreadPoolExecutor(max_workers=max_consumers, max_queue_size=30)
        redis_config = SqlConfig.from_file(Path(REDIS_CONFIG_PATH)) if redis_config is None else redis_config
        
        # 初始化实时状态存储队列，每个设备仅保存最近1秒的状态，
        # 供前端显示实时状态信息（也供后端预警使用）（原有逻辑）
        # 供实时数据持久化存储
        self.real_time_data_state = UnifiedQueue(
            use_redis=use_redis,
            redis_config=redis_config,
            maxsize=production_queue_size,
            queue_name=f"real_time_data_{id(self)}"
        )


        # 初始化设备存储（新增）
        self.redis_device_storage: RedisDeviceQueueStorage = None
        self._init_device_storage(
            device_storage_type, 
            device_storage_redis_config or redis_config,  # 如果没有单独配置，使用生产队列的配置
            device_max_queue_size
        )

        self.consumer_worker_running = True
        self._is_running = True
        

        self.consumer_tool_pool: ConsumerToolPool = consumer_tool_pool
        if self.consumer_tool_pool is None:
            raise ValueError("consumer_tool_pool must not be null!")

        # 所有想要在子类线程中看到的状态在这之前定义
        self.consumer_worker_thread = threading.Thread(target=self._start_consumer_worker)
        self.consumer_worker_thread.daemon = True
        self.consumer_worker_thread.start()

    def _init_device_storage(self, storage_type: str, redis_config: Optional[Dict], max_queue_size: int):
        """初始化设备存储"""
        try:
            self.device_storage = DeviceQueueStorageFactory.create_storage(
                storage_type=storage_type,
                redis_config=redis_config,
                max_queue_size=max_queue_size
            )
            self.logger.info(f"设备存储初始化成功: {storage_type}")
            if storage_type == "redis":
                self.redis_device_storage = self.device_storage  
            else:
                self.redis_device_storage = DeviceQueueStorageFactory.create_storage(
                storage_type="redis",
                redis_config=redis_config,
                max_queue_size=max_queue_size
            )
        except Exception as e:
            self.logger.error(f"设备存储初始化失败: {e}, 回退到内存存储")
            # 回退到内存存储
            self.device_storage = DeviceQueueStorageFactory.create_storage(
                storage_type='memory',
                max_queue_size=max_queue_size
            )
            # ✅ 修复：尝试单独初始化 redis_device_storage，失败则设为 None
            try:
                self.redis_device_storage = DeviceQueueStorageFactory.create_storage(
                    storage_type="redis",
                    redis_config=redis_config,
                    max_queue_size=max_queue_size
                )
            except Exception as redis_e:
                self.logger.error(f"Redis 设备存储初始化也失败: {redis_e}")
                self.redis_device_storage = None


    def stop(self):
        self._is_running = False


    def set_consumer_tool_pool(self, consumer_tool_pool):
        self.consumer_tool_pool = consumer_tool_pool

    # ===== 设备数据管理方法 =====

    def put_device_data(self, device_id: str, data: Any) -> bool:
        """向指定设备添加数据"""
        return self.device_storage.put_device_data(device_id, data)

    def publish_redis_real_time_data(self, device_id: str, data: Any)-> bool:
        return self.redis_device_storage.publish_websocket_data(device_id, data)

    def get_device_data(self, device_id: str) -> Optional[Any]:
        """从指定设备获取一条数据"""
        return self.device_storage.get_device_data(device_id)


    def get_all_device_data(self, device_id: str) -> List[Any]:
        """获取指定设备的所有数据（不移除）"""
        return self.device_storage.get_all_device_data(device_id)


    def get_device_queue_size(self, device_id: str) -> int:
        """获取指定设备的队列大小"""
        return self.device_storage.get_device_queue_size(device_id)


    def get_all_devices(self) -> List[str]:
        """获取所有设备ID"""
        return self.device_storage.get_all_devices()


    def clear_device_queue(self, device_id: str):
        """清空指定设备的队列"""
        self.device_storage.clear_device_queue(device_id)


    def get_device_storage_stats(self) -> Dict[str, Any]:
        """获取设备存储统计信息"""
        return self.device_storage.get_storage_stats()


    def get_queue_info(self):
        """获取生产队列信息"""
        return {
            'backend_type': 'redis' if self.real_time_data_state.use_redis else 'memory',
            'queue_size': self.real_time_data_state.qsize(),
            'is_empty': self.real_time_data_state.empty(),
            'is_full': self.real_time_data_state.full()
        }


    def switch_device_storage(self, new_storage_type: str, new_redis_config: Optional[Dict] = None):
        """运行时切换设备存储类型"""
        try:
            # 备份当前所有设备数据
            current_devices = self.device_storage.get_all_devices()
            device_data_backup = {}
            
            for device_id in current_devices:
                device_data_backup[device_id] = self.device_storage.get_all_device_data(device_id)
            
            # 获取当前配置
            old_max_queue_size = getattr(self.device_storage, 'max_queue_size', 60)
            
            # 创建新的存储
            new_storage = DeviceQueueStorageFactory.create_storage(
                storage_type=new_storage_type,
                redis_config=new_redis_config,
                max_queue_size=old_max_queue_size
            )
            
            # 恢复数据到新存储
            for device_id, data_list in device_data_backup.items():
                for data in data_list:
                    new_storage.put_device_data(device_id, data)
            
            # 替换存储
            self.device_storage = new_storage
            
            self.logger.info(f"设备存储切换成功: {new_storage_type}")
            return True
            
        except Exception as e:
            self.logger.error(f"设备存储切换失败: {e}")
            return False


    @abstractmethod
    def start_produce_worker(self, *args, **kwargs):
        """start produce work implemented by inherited class"""


    @abstractmethod
    def stop_produce_worker(self, production_id):
        """stop produce work based on production id implemented by inherited class"""


    @abstractmethod
    def _start_consumer_worker(self):
        """start consumer worker implemented by inherited class"""


    @abstractmethod
    def shutdown(self):
        """shut dowm the manager and all thread pools"""


    async def execute(self):
        ...

