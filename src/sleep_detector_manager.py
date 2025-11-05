#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time    : 2025/10/29 10:43
@Author  : weiyutao
@File    : sleep_detector_manager.py
"""
import threading
from typing import (
    Dict,
    Callable,
    Optional,
    Any
)
import logging
import time

from src.sleep_detector import SleepDetector
from src.sleep_detector import SleepRecord

class SleepDetectorManager:
    """睡眠检测器管理器"""
    
    def __init__(self, 
                 sleep_end_timeout: int = 3,
                 min_sleep_duration: int = 30,
                 cleanup_interval: int = 86400,  # 24小时：检测器清理间隔
                 inactive_threshold: int = 43200):  # 12小时：非活跃设备阈值
        
        self.sleep_end_timeout = sleep_end_timeout
        self.min_sleep_duration = min_sleep_duration
        self.cleanup_interval = cleanup_interval
        self.inactive_threshold = inactive_threshold
        
        self.device_detectors: Dict[str, SleepDetector] = {}
        self.device_last_activity: Dict[str, float] = {}
        self.callbacks: Dict[str, Callable] = {}  # 事件回调
        
        self.lock = threading.Lock()
        self.logger = logging.getLogger("SleepDetectorManager")
        
        # 启动清理定时器
        self._start_cleanup_timer()
    
    def get_detector(self, device_id: str) -> SleepDetector:
        """获取或创建设备检测器"""
        with self.lock:
            if device_id not in self.device_detectors:
                self.device_detectors[device_id] = SleepDetector(
                    device_id=device_id,
                    sleep_end_timeout=self.sleep_end_timeout,
                    min_sleep_duration=self.min_sleep_duration,
                    callback=self._on_sleep_event
                )
                self.logger.info(f"为设备 {device_id} 创建睡眠检测器")
            
            # 更新活跃时间
            self.device_last_activity[device_id] = time.time()
            
            return self.device_detectors[device_id]
    
    def check_sleep_status(self, device_id: str, bed_state: int, timestamp: float):
        """检查指定设备的睡眠状态"""
        detector = self.get_detector(device_id)
        detector.check_sleep_status(bed_state, timestamp)
    
    def _on_sleep_event(self, event_type: str, data: Dict[str, Any]):
        """睡眠事件回调"""
        self.logger.info(f"睡眠事件: {event_type} - 设备: {data.get('device_id')}")
        
        # 调用注册的回调函数
        for callback_name, callback_func in self.callbacks.items():
            try:
                callback_func(event_type, data)
            except Exception as e:
                self.logger.error(f"回调函数 {callback_name} 执行失败: {e}")
    
    def register_callback(self, name: str, callback: Callable):
        """注册睡眠事件回调函数"""
        self.callbacks[name] = callback
        self.logger.info(f"注册回调函数: {name}")
    
    def unregister_callback(self, name: str):
        """取消注册回调函数"""
        if name in self.callbacks:
            del self.callbacks[name]
            self.logger.info(f"取消注册回调函数: {name}")
    
    def get_all_status(self) -> Dict[str, Any]:
        """获取所有设备的睡眠状态"""
        with self.lock:
            status = {
                'total_devices': len(self.device_detectors),
                'sleeping_devices': 0,
                'devices_status': {}
            }
            
            for device_id, detector in self.device_detectors.items():
                device_status = detector.get_current_status()
                status['devices_status'][device_id] = device_status
                
                if device_status['is_sleeping']:
                    status['sleeping_devices'] += 1
            
            return status
    
    def force_end_all_sleep(self) -> Dict[str, Optional[SleepRecord]]:
        """强制结束所有设备的睡眠"""
        results = {}
        with self.lock:
            for device_id, detector in self.device_detectors.items():
                record = detector.force_end_sleep()
                if record:
                    results[device_id] = record
        return results
    
    def _start_cleanup_timer(self):
        """启动清理定时器"""
        def cleanup():
            self._cleanup_inactive_detectors()
            # 重新启动定时器
            threading.Timer(self.cleanup_interval, cleanup).start()
        
        threading.Timer(self.cleanup_interval, cleanup).start()
        self.logger.info(f"启动检测器清理定时器，间隔: {self.cleanup_interval}秒")
    
    def _cleanup_inactive_detectors(self):
        """清理非活跃的检测器"""
        current_time = time.time()
        inactive_devices = []
        
        with self.lock:
            for device_id, last_activity in self.device_last_activity.items():
                if current_time - last_activity > self.inactive_threshold:
                    # 检查是否在睡眠中
                    detector = self.device_detectors.get(device_id)
                    if detector and not detector.is_sleeping:
                        inactive_devices.append(device_id)
            
            # 清理非活跃设备
            for device_id in inactive_devices:
                if device_id in self.device_detectors:
                    del self.device_detectors[device_id]
                if device_id in self.device_last_activity:
                    del self.device_last_activity[device_id]
                self.logger.info(f"清理非活跃设备检测器: {device_id}")
    
    def shutdown(self):
        """关闭管理器"""
        self.logger.info("关闭睡眠检测器管理器...")
        
        # 强制结束所有睡眠
        active_records = self.force_end_all_sleep()
        if active_records:
            self.logger.info(f"强制结束 {len(active_records)} 个活跃睡眠记录")
        
        # 清理所有检测器
        with self.lock:
            self.device_detectors.clear()
            self.device_last_activity.clear()
            self.callbacks.clear()
        
        self.logger.info("睡眠检测器管理器已关闭")


# 使用示例和集成代码
def example_callback(event_type: str, data: Dict[str, Any]):
    """示例回调函数"""
    if event_type == 'sleep_start':
        print(f"🌙 设备 {data['device_id']} 开始睡眠: {data['start_time_str']}")
    elif event_type == 'sleep_end':
        if data['is_valid']:
            record = data['sleep_record']
            print(f"☀️ 设备 {data['device_id']} 睡眠结束: {record.duration_hours}小时")
        else:
            print(f"❌ 设备 {data['device_id']} 睡眠无效: {data['reason']}")