#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time    : 2025/08/21 16:54
@Author  : weiyutao
@File    : memory_device_queue_storage.py
"""
from typing import (
    Any, 
    Optional, 
    List,
    Dict
)


from base.lockfree_queue import AtomicDict, LockFreeQueue
from base.device_queue_storage_interface import DeviceQueueStorageInterface

from agent.base.base_tool import tool


@tool
class MemoryDeviceQueueStorage(DeviceQueueStorageInterface):
    """内存设备队列存储实现"""
    
    def __init__(self, max_queue_size: int = 60):
        """
        初始化内存存储
        
        Args:
            max_queue_size: 每个设备队列的最大大小（60秒数据）
        """
        self.max_queue_size = max_queue_size
        self.device_queues = AtomicDict() 
    
    
    def _get_or_create_queue(self, device_id: str) -> LockFreeQueue:
        """获取或创建设备队列"""
        return self.device_queues.get_or_create(
            device_id, 
            lambda: LockFreeQueue(capacity=self.max_queue_size)
        )
    
    
    def put_device_data(self, device_id: str, data: Any) -> bool:
        """向指定设备队列添加数据"""
        queue = self._get_or_create_queue(device_id)
        
        # 如果队列满了，先移除最老的数据
        if queue.full():
            queue.dequeue()  # 移除最老的数据
        
        success = queue.enqueue(data)
        if success:
            self.logger.debug(f"设备 {device_id} 添加数据成功")
        else:
            self.logger.warning(f"设备 {device_id} 添加数据失败")
        
        return success
    
    
    def get_device_data(self, device_id: str) -> Optional[Any]:
        """从指定设备队列获取数据"""
        if device_id not in self.device_queues:
            return None
        
        queue = self.device_queues.get(device_id)
        return queue.dequeue()
    
    
    def get_all_device_data(self, device_id: str) -> List[Any]:
        """获取指定设备的所有数据（不移除）"""
        if device_id not in self.device_queues:
            return []
        
        queue = self.device_queues.get(device_id)
        return queue.peek_all()
    
    
    def get_device_queue_size(self, device_id: str) -> int:
        """获取指定设备队列大小"""
        if device_id not in self.device_queues:
            return 0
        
        queue = self.device_queues.get(device_id)
        return queue.qsize()
    
    
    def get_all_devices(self) -> List[str]:
        """获取所有设备ID"""
        return self.device_queues.keys()
    
    
    def clear_device_queue(self, device_id: str):
        """清空指定设备的队列"""
        if device_id in self.device_queues:
            queue = self.device_queues.get(device_id)
            while not queue.empty():
                queue.dequeue()
    
    
    def get_storage_stats(self) -> Dict[str, Any]:
        """获取存储统计信息"""
        stats = {
            'storage_type': 'memory',
            'total_devices': len(self.get_all_devices()),
            'device_stats': {}
        }
        
        for device_id in self.get_all_devices():
            queue = self.device_queues.get(device_id)
            stats['device_stats'][device_id] = queue.get_stats()
        
        return stats