#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time    : 2025/08/21 15:09
@Author  : weiyutao
@File    : queue_storage_interface.py
"""
from abc import ABC, abstractmethod
from typing import (
    Optional, 
    Any,
    List,
    Dict
)
from agent.base.base_tool import tool


@tool
class DeviceQueueStorageInterface:

    def __init__(self,  **kwargs):
        super().__init__(**kwargs)
    
    """设备队列存储抽象接口"""
    
    @abstractmethod
    def put_device_data(self, device_id: str, data: Any) -> bool:
        """向指定设备队列添加数据"""
        pass
    
    @abstractmethod
    def get_device_data(self, device_id: str) -> Optional[Any]:
        """从指定设备队列获取数据"""
        pass
    
    @abstractmethod
    def get_all_device_data(self, device_id: str) -> List[Any]:
        """获取指定设备的所有数据（不移除）"""
        pass
    
    @abstractmethod
    def get_device_queue_size(self, device_id: str) -> int:
        """获取指定设备队列大小"""
        pass
    
    @abstractmethod
    def get_all_devices(self) -> List[str]:
        """获取所有设备ID"""
        pass
    
    @abstractmethod
    def clear_device_queue(self, device_id: str):
        """清空指定设备的队列"""
        pass
    
    @abstractmethod
    def get_storage_stats(self) -> Dict[str, Any]:
        """获取存储统计信息"""
        pass
    
    async def execute(self):
        pass
    
if __name__ == '__main__':
    device_ = DeviceQueueStorageInterface()
    print(device_)
    