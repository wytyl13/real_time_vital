#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time    : 2025/08/21 17:02
@Author  : weiyutao
@File    : device_queue_storage_factory.py
"""
from  typing import (
    Dict,
    Optional, 
    Any
)


from base.device_queue_storage_interface import DeviceQueueStorageInterface
from base.memory_device_queue_storage import MemoryDeviceQueueStorage
from base.redis_device_queue_storage import RedisDeviceQueueStorage
from base.hybrid_device_queue_storage import HybridDeviceQueueStorage


from agent.base.base_tool import tool


@tool
class DeviceQueueStorageFactory:
    """设备队列存储工厂类"""
    
    @staticmethod
    def create_storage(storage_type: str, 
                      redis_config: Optional[Dict[str, Any]] = None,
                      max_queue_size: int = 60) -> DeviceQueueStorageInterface:
        """
        创建存储实例
        
        Args:
            storage_type: 存储类型 ('memory', 'redis', 'hybrid')
            redis_config: Redis配置
            max_queue_size: 最大队列大小
            
        Returns:
            DeviceQueueStorageInterface: 存储实例
        """
        if storage_type == 'memory':
            return MemoryDeviceQueueStorage(max_queue_size=max_queue_size)
        
        elif storage_type == 'redis':
            if not redis_config:
                raise ValueError("Redis配置不能为空")
            return RedisDeviceQueueStorage(redis_config=redis_config, max_queue_size=max_queue_size)
        
        elif storage_type == 'hybrid':
            if not redis_config:
                raise ValueError("混合存储需要Redis配置")
            return HybridDeviceQueueStorage(redis_config=redis_config, max_queue_size=max_queue_size)
        
        else:
            raise ValueError(f"不支持的存储类型: {storage_type}")