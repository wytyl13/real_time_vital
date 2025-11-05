#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time    : 2025/03/04 11:01
@Author  : weiyutao
@File    : consumer_tool_pool.py
"""
import threading
import queue
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
    List,
    Callable
)
import time
from abc import ABC, abstractmethod
from queue import Queue, Empty
from contextlib import contextmanager


from base.base_tool import BaseTool


class ConsumerToolPool(BaseTool):

    pools: dict = None
    locks: dict = None
    total_instances: int = 0
    default_instances: int = 0
    regular_instances: int = 0
    topic_instances: Dict = {}
    last_log_time: float = 0
    log_interval: float = 10.0
    tool_factories: Dict = {}
    
    def __init__(self, model_paths: Dict[str, Any], total_pool_size=30, default_ratio=0.88):
        super().__init__()
        """
        初始化检测器对象池
        
        :param model_paths: 模型路径字典 {topic: model_info}
        :param max_pool_size: 每个模型最大实例数
        """
        self.last_log_time = 0
        self.log_interval = 10.0
        
        self.pools = {}
        self.locks = {}
        
        # 添加这一行
        self.tool_factories = {}  # 存储工具工厂函数

        # 统计default和regular主题的数量
        default_topics = [topic for topic in model_paths.keys() if topic.startswith("default")]
        regular_topics = [topic for topic in model_paths.keys() if not topic.startswith("default")]
        
        default_topic_count = len(default_topics)
        regular_topic_count = len(regular_topics)
        
        
        # 初始化实例计数器
        self.total_instances = 0
        self.default_instances = 0
        self.regular_instances = 0
        self.topic_instances = {}
        
        # 根据比例计算default和regular主题池的总大小
        total_default_size = int(total_pool_size * default_ratio)
        total_regular_size = total_pool_size - total_default_size
        
        # 计算每个default主题的池大小
        default_pool_size = total_default_size // default_topic_count if default_topic_count > 0 else 0
        # 处理余数
        default_remainder = total_default_size % default_topic_count if default_topic_count > 0 else 0
        
        
        # 计算每个regular主题的池大小
        regular_pool_size = total_regular_size // regular_topic_count if regular_topic_count > 0 else 0
        # 处理余数
        regular_remainder = total_regular_size % regular_topic_count if regular_topic_count > 0 else 0
        
        # 为每个模型创建线程安全的对象池
        for i, (topic, model_info) in enumerate(model_paths.items()):
            if topic.startswith("default"):
                # 为第一个default主题分配额外的余数
                extra = default_remainder if i == 0 and default_remainder > 0 else 0
                pool_size = default_pool_size + extra
                self.logger.info(f"Creating default pool for {topic} with size {pool_size}")
            else:
                # 为第一个regular主题分配额外的余数
                is_first_regular = topic == regular_topics[0] if regular_topics else False
                extra = regular_remainder if is_first_regular and regular_remainder > 0 else 0
                pool_size = regular_pool_size + extra
                self.logger.info(f"Creating regular pool for {topic} with size {pool_size}")
                
            self.pools[topic] = Queue(maxsize=pool_size)
            self.locks[topic] = threading.Lock()
            
            # 记录当前主题的实例数
            self.topic_instances[topic] = pool_size
            # 根据主题类型更新计数器
            if topic.startswith("default"):
                self.default_instances += pool_size
            else:
                self.regular_instances += pool_size
            
            self.total_instances += pool_size
            # 预先创建实例
            for _ in range(pool_size):
                consumer_tool = model_info.init_model()
                self.pools[topic].put(consumer_tool)
                
        # 打印实例创建统计信息
        self.logger.info(f"线程池总实例数: {self.total_instances}")
        self.logger.info(f"默认实例数: {self.default_instances} (目标比例: {default_ratio:.0%})")
        self.logger.info(f"个性化实例数: {self.regular_instances} (目标比例: {(1-default_ratio):.0%})")
        self.logger.info(f"主题实例数详情: {self.topic_instances}")
    
    
    @contextmanager
    def get_tool(self, tool_name: str):
        """
        上下文管理器方式获取工具
        
        使用示例:
            with pool.get_tool("sleep_data_storage") as tool:
                result = tool.execute(...)
        
        自动处理获取和释放
        """
        tool = None
        try:
            # 获取工具
            tool = self.get_consumer_tool(tool_name)
            if tool is None:
                raise ValueError(f"无法获取工具: {tool_name}")
            
            yield tool
            
        finally:
            # 自动释放工具
            if tool is not None:
                try:
                    self.release_consumer_tool(tool_name, tool)
                    self.logger.debug(f"🔄 工具 {tool_name} 已自动放回池")
                except Exception as e:
                    self.logger.error(f"❌ 释放工具 {tool_name} 失败: {e}")
    
    
    def add_tool(self, tool_name: str, tool_factory: Callable, pool_size: int = 1):
        """添加工具到池"""
        self.pools[tool_name] = Queue(maxsize=pool_size)
        self.locks[tool_name] = threading.Lock()
        self.tool_factories[tool_name] = tool_factory
        
        for _ in range(pool_size):
            independent_instance = tool_factory()
            self.pools[tool_name].put(independent_instance)
        
        self.topic_instances[tool_name] = pool_size
        self.total_instances += pool_size
        print(f"✅ 工具已添加: {tool_name} (池大小: {pool_size})")
    
    
    def get_consumer_tool_name(self, topic_model_key):
        default_topic = topic_model_key
        try:
            if topic_model_key not in self.pools:
                default_topic = "default" + "/" + topic_model_key.split("/", 1)[1]
        except Exception as e:
            error_info = f"Fail to get_consumer_tool_name {str(e)}"
            self.logger.error(error_info)
            raise ValueError(error_info) from e
        return default_topic
    
    
    def get_consumer_tool(self, topic_model_key):
        """
        获取指定主题的检测器实例
        
        :param topic: 检测器主题
        :return: 检测器实例
        """
        
        if topic_model_key not in self.pools:
            # 使用 "default" + topic 的第一部分（以问号分割）作为默认主题
            
            default_topic = "default" + "/" + topic_model_key.split("/", 1)[1]
            self.logger.info(f"No detector pool for topic: {topic_model_key}, using default topic: {default_topic}")
            if default_topic in self.pools:
                # 尝试非阻塞方式获取实例
                try:
                    detector = self.pools[default_topic].get(block=False)
                    self._log_pool_status()
                    return detector
                except Empty:
                    self.logger.warning(f"Default pool {default_topic} is empty, returning None")
                    return None
            else:
                self.logger.error(f"No detector pool for topic_model_key: {topic_model_key}. No default detector pool {default_topic}.")
                return None
        
        # 从池中获取实例
        # detector: Detector = self.pools[topic_model_key].get()
        detector: Any = self.pools[topic_model_key].get()
        
        # 记录获取实例后的线程池状态
        self._log_pool_status()
        
        return detector
    
    
    def release_consumer_tool(self, topic_model_key, consumer_tool):
        """
        将检测器实例返回到池中
        
        :param topic: 检测器主题
        :param detector: 检测器实例
        """
        if topic_model_key not in self.pools:
            # 尝试使用默认主题规则
            default_topic = "default" + "/" + topic_model_key.split("/", 1)[1]
            if default_topic in self.pools:
                # 将实例放回默认主题的池中
                self.pools[default_topic].put(consumer_tool)
                # self.logger.info(f"Released tool for {topic_model_key} back to default pool: {default_topic}")
                # 记录释放实例后的线程池状态
                self._log_pool_status()
                return
            else:
                raise ValueError(f"No detector pool for topic: {topic_model_key}")
        
        # 将实例放回池中
        self.pools[topic_model_key].put(consumer_tool)
        # self.logger.info(f"Released tool for {topic_model_key} back to pool")
        
        # 记录释放实例后的线程池状态
        self._log_pool_status()
    
    
    def _run(self, *args, **kwargs):
        pass
    
    
    def _log_pool_status(self):
        """
        记录所有线程池的当前状态
        """
        current_time = time.time()
        if current_time - self.last_log_time < self.log_interval:
            return  # 未到间隔时间，跳过打印
        self.last_log_time = current_time
        
        
        default_available = 0
        regular_available = 0
        total_available = 0
        
        pool_status = {}
        
        for topic, pool in self.pools.items():
            available = pool.qsize()
            total = self.topic_instances.get(topic, 0)
            usage_percentage = 0 if total == 0 else (1 - available / total) * 100
            
            pool_status[topic] = {
                "available": available,
                "total": total,
                "usage": f"{usage_percentage:.1f}%"
            }
            
            total_available += available
            if topic.startswith("default"):
                default_available += available
            else:
                regular_available += available
        
        # 计算总体使用情况
        default_total = self.default_instances
        regular_total = self.regular_instances
        all_total = self.total_instances
        
        default_usage = 0 if default_total == 0 else (1 - default_available / default_total) * 100
        regular_usage = 0 if regular_total == 0 else (1 - regular_available / regular_total) * 100
        total_usage = 0 if all_total == 0 else (1 - total_available / all_total) * 100
        
        # self.logger.info("当前线程池状态 ===========================")
        # self.logger.info(f"默认主题池: 可用 {default_available}/{default_total} 实例, 使用率 {default_usage:.1f}%")
        # self.logger.info(f"个性化主题池: 可用 {regular_available}/{regular_total} 实例, 使用率 {regular_usage:.1f}%")
        # self.logger.info(f"总体: 可用 {total_available}/{all_total} 实例, 使用率 {total_usage:.1f}%")
        # self.logger.info(f"详细状态: {pool_status}")
        # self.logger.info("================================================")
