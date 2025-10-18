#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time    : 2025/08/21 16:57
@Author  : weiyutao
@File    : redis_device_queue_storage.py
"""
from typing import (
    Dict,
    Any,
    List,
    Optional
)
import redis
import json
import time

from base.device_queue_storage_interface import DeviceQueueStorageInterface

from agent.base.base_tool import tool


@tool
class RedisDeviceQueueStorage(DeviceQueueStorageInterface):
    """Redis设备队列存储实现"""
    
    def __init__(self, redis_config: Dict[str, Any], max_queue_size: int = 60):
        """
        初始化Redis存储
        
        Args:
            redis_config: Redis连接配置
            max_queue_size: 每个设备队列的最大大小（60秒数据）
        """
        self.max_queue_size = max_queue_size
        self.logger.info(f"redis_config: ------------------------------------- {redis_config}")
        self.redis_client = redis.Redis(
            host=redis_config.host,
            port=redis_config.port,
            db=redis_config.database,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5
        )
        self.key_prefix = "device_queue"
        self.device_set_key = f"{self.key_prefix}:devices"
        
        # 测试连接
        try:
            self.redis_client.ping()
            self.logger.info("Redis连接成功")
        except Exception as e:
            self.logger.error(f"Redis连接失败: {e}")
            raise
    
    
    def _get_device_key(self, device_id: str) -> str:
        """获取设备在Redis中的键名"""
        return f"{self.key_prefix}:{device_id}"
    
    
    def put_device_data(self, device_id: str, data: Any) -> bool:
        """向指定设备队列添加数据（使用Redis List）"""
        try:
            device_key = self._get_device_key(device_id)
            
            # 序列化数据
            serialized_data = json.dumps({
                'data': data,
                'timestamp': time.time()
            })
            
            # 使用Redis管道提高性能
            pipe = self.redis_client.pipeline()
            
            # 添加到设备集合
            pipe.sadd(self.device_set_key, device_id)
            
            # 左推入数据到列表头部（最新数据在前）
            pipe.lpush(device_key, serialized_data)
            
            # 保持队列大小不超过最大值（保留最新的N条数据）
            pipe.ltrim(device_key, 0, self.max_queue_size - 1)
            
            # 设置过期时间（防止数据积累）
            pipe.expire(device_key, 3600)  # 1小时过期
            
            # 执行管道
            pipe.execute()
            
            self.logger.debug(f"设备 {device_id} 添加数据到Redis成功")
            return True
            
        except Exception as e:
            self.logger.error(f"设备 {device_id} 添加数据到Redis失败: {e}")
            return False
    
    
    def publish_websocket_data(self, device_id: str, websocket_data: Any) -> bool:
        """
        发布设备数据到WebSocket频道
        
        Args:
            device_id: 设备ID
            data: 设备数据（元组格式）
        
        Returns:
            bool: 发布是否成功
        """
            
        try:
            # 发布到Redis频道
            if hasattr(self, 'redis_client') and self.redis_client:
                # 后续随着设备数量增加需要使用单独的主题
                self.redis_client.publish(f'websocket_realtime', json.dumps(websocket_data))
                self.logger.debug(f"设备 {device_id} WebSocket数据发布成功")
                return True
            else:
                self.logger.warning("Redis客户端未初始化，无法发布WebSocket数据")
                return False
                
        except Exception as e:
            self.logger.error(f"设备 {device_id} WebSocket数据发布失败: {e}")
            return False
    
    
    
    def get_device_data(self, device_id: str) -> Optional[Any]:
        """从指定设备队列获取数据（FIFO，从列表尾部弹出）"""
        try:
            device_key = self._get_device_key(device_id)
            
            # 从列表尾部弹出（最老的数据）
            serialized_data = self.redis_client.rpop(device_key)
            
            if serialized_data is None:
                return None
            
            # 反序列化数据
            data_obj = json.loads(serialized_data)
            return data_obj['data']
            
        except Exception as e:
            self.logger.error(f"从Redis获取设备 {device_id} 数据失败: {e}")
            return None
    
    
    def get_all_device_data(self, device_id: str) -> List[Any]:
        """获取指定设备的所有数据（不移除）"""
        try:
            device_key = self._get_device_key(device_id)
            
            # 获取整个列表（0到-1表示全部）
            serialized_data_list = self.redis_client.lrange(device_key, 0, -1)
            
            if not serialized_data_list:
                return []
            
            # 反序列化所有数据
            result = []
            for serialized_data in reversed(serialized_data_list):  # 反转以保持时间顺序
                try:
                    data_obj = json.loads(serialized_data)
                    result.append(data_obj['data'])
                except json.JSONDecodeError:
                    continue
            
            return result
            
        except Exception as e:
            self.logger.error(f"从Redis获取设备 {device_id} 所有数据失败: {e}")
            return []
    
    
    def get_device_queue_size(self, device_id: str) -> int:
        """获取指定设备队列大小"""
        try:
            device_key = self._get_device_key(device_id)
            return self.redis_client.llen(device_key)
        except Exception as e:
            self.logger.error(f"获取设备 {device_id} 队列大小失败: {e}")
            return 0
    
    
    def get_all_devices(self) -> List[str]:
        """获取所有设备ID"""
        try:
            return list(self.redis_client.smembers(self.device_set_key))
        except Exception as e:
            self.logger.error(f"从Redis获取设备列表失败: {e}")
            return []
    
    
    def clear_device_queue(self, device_id: str):
        """清空指定设备的队列"""
        try:
            device_key = self._get_device_key(device_id)
            self.redis_client.delete(device_key)
            self.redis_client.srem(self.device_set_key, device_id)
            self.logger.info(f"清空设备 {device_id} 队列成功")
        except Exception as e:
            self.logger.error(f"清空设备 {device_id} 队列失败: {e}")
    
    
    def get_storage_stats(self) -> Dict[str, Any]:
        """获取存储统计信息"""
        try:
            devices = self.get_all_devices()
            stats = {
                'storage_type': 'redis',
                'total_devices': len(devices),
                'device_stats': {}
            }
            
            for device_id in devices:
                queue_size = self.get_device_queue_size(device_id)
                stats['device_stats'][device_id] = {
                    'size': queue_size,
                    'utilization': queue_size / self.max_queue_size * 100
                }
            
            return stats
            
        except Exception as e:
            self.logger.error(f"获取Redis存储统计失败: {e}")
            return {'storage_type': 'redis', 'error': str(e)}