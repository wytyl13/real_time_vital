#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time    : 2025/08/21 16:59
@Author  : weiyutao
@File    : hybrid_device_queue_storage.py
"""
from typing import (
    Dict, 
    Any,
    Optional,
    List
)


from base.device_queue_storage_interface import DeviceQueueStorageInterface
from base.memory_device_queue_storage import MemoryDeviceQueueStorage
from base.redis_device_queue_storage import RedisDeviceQueueStorage

from agent.base.base_tool import tool

@tool
class HybridDeviceQueueStorage(DeviceQueueStorageInterface):
    """混合设备队列存储（内存+Redis双写）"""
    
    def __init__(self, redis_config: Dict[str, Any], max_queue_size: int = 60):
        """
        初始化混合存储
        
        Args:
            redis_config: Redis连接配置
            max_queue_size: 每个设备队列的最大大小
        """
        self.memory_storage = MemoryDeviceQueueStorage(max_queue_size)
        try:
            self.redis_storage = RedisDeviceQueueStorage(redis_config, max_queue_size)
            self.redis_available = True
        except Exception as e:
            self.logger.warning(f"Redis不可用，将只使用内存存储: {e}")
            self.redis_storage = None
            self.redis_available = False
        
    
    def put_device_data(self, device_id: str, data: Any) -> bool:
        """双写：同时写入内存和Redis"""
        # 内存写入（主要）
        memory_success = self.memory_storage.put_device_data(device_id, data)
        
        # Redis写入（备份）
        redis_success = True
        if self.redis_available:
            try:
                redis_success = self.redis_storage.put_device_data(device_id, data)
            except Exception as e:
                self.logger.warning(f"Redis写入失败，仅使用内存: {e}")
                redis_success = False
        
        return memory_success  # 以内存为准
    
    
    def get_device_data(self, device_id: str) -> Optional[Any]:
        """优先从内存读取"""
        return self.memory_storage.get_device_data(device_id)
    
    
    def get_all_device_data(self, device_id: str) -> List[Any]:
        """优先从内存读取"""
        return self.memory_storage.get_all_device_data(device_id)
    
    
    def get_device_queue_size(self, device_id: str) -> int:
        """优先从内存读取"""
        return self.memory_storage.get_device_queue_size(device_id)
    
    
    def get_all_devices(self) -> List[str]:
        """优先从内存读取"""
        return self.memory_storage.get_all_devices()
    
    
    def clear_device_queue(self, device_id: str):
        """清空内存和Redis"""
        self.memory_storage.clear_device_queue(device_id)
        if self.redis_available:
            try:
                self.redis_storage.clear_device_queue(device_id)
            except Exception as e:
                self.logger.warning(f"清空Redis队列失败: {e}")
    
    
    def get_storage_stats(self) -> Dict[str, Any]:
        """获取混合存储统计"""
        memory_stats = self.memory_storage.get_storage_stats()
        
        stats = {
            'storage_type': 'hybrid',
            'memory_stats': memory_stats,
            'redis_available': self.redis_available
        }
        
        if self.redis_available:
            try:
                redis_stats = self.redis_storage.get_storage_stats()
                stats['redis_stats'] = redis_stats
            except Exception as e:
                stats['redis_error'] = str(e)
        
        return stats