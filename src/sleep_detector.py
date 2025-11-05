#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time    : 2025/10/29 10:35
@Author  : weiyutao
@File    : sleep_detector.py
"""
import time
import threading
from typing import Dict, Optional, Callable, Any
from dataclasses import dataclass
from enum import IntEnum
import logging
from datetime import datetime, timedelta

from src.sleep_data_storage import BedState



@dataclass
class SleepRecord:
    """睡眠记录"""
    device_id: str
    sleep_start_time: float
    sleep_end_time: float
    total_duration: float  # 秒
    out_bed_times: list  # 离床时间段列表 [(start, end), ...]
    
    def to_dict(self):
        return {
            'device_id': self.device_id,
            'sleep_start_time': self.sleep_start_time,
            'sleep_end_time': self.sleep_end_time,
            'total_duration': self.total_duration,
            'out_bed_times': self.out_bed_times,
            'sleep_date': datetime.fromtimestamp(self.sleep_start_time).strftime('%Y-%m-%d'),
            'start_time_str': datetime.fromtimestamp(self.sleep_start_time).strftime('%Y-%m-%d %H:%M:%S'),
            'end_time_str': datetime.fromtimestamp(self.sleep_end_time).strftime('%Y-%m-%d %H:%M:%S'),
            'duration_hours': round(self.total_duration / 3600, 2)
        }



class SleepDetector:
    """单个设备的睡眠检测器"""
    
    def __init__(self, 
                 device_id: str,
                 sleep_end_timeout: int = 30,  # 10分钟：离床超时时间
                 min_sleep_duration: int = 120,  # 30分钟：最小有效睡眠时长
                 callback: Optional[Callable] = None):
        
        self.device_id = device_id
        self.sleep_end_timeout = sleep_end_timeout
        self.min_sleep_duration = min_sleep_duration
        self.callback = callback  # 睡眠状态变化回调函数
        
        # 睡眠状态
        self.is_sleeping = False
        self.sleep_start_time: Optional[float] = None
        self.last_in_bed_time: Optional[float] = None
        self.current_out_bed_start: Optional[float] = None
        
        # 离床记录
        self.out_bed_periods = []  # [(start_time, end_time), ...]
        
        # 计时器
        self.out_bed_timer: Optional[threading.Timer] = None
        self.lock = threading.Lock()  # 线程安全
        
        # 日志
        from tools.utils import Utils
        utils = Utils()
        self.logger = utils.setup_logger(name=f"SleepDetector_{device_id}")
    
    def check_sleep_status(self, in_bed: int, timestamp: float):
        """
        检查睡眠状态
        
        Args:
            in_bed: 在床状态（1=在床，0=不在床）
            timestamp: 时间戳
        """
        with self.lock:
            if in_bed == 1:  # 在床状态
                self._handle_in_bed(timestamp)
            else:  # 不在床状态
                self._handle_out_bed(timestamp)
    
    def _handle_in_bed(self, timestamp: float):
        """处理在床状态"""
        # 取消离床计时器
        if self.out_bed_timer:
            self.out_bed_timer.cancel()
            self.out_bed_timer = None
            self.logger.info(f"设备 {self.device_id}: 用户回到床上，取消睡眠结束计时器")
        
        # 记录离床结束时间
        if self.current_out_bed_start:
            out_bed_duration = timestamp - self.current_out_bed_start
            self.out_bed_periods.append((self.current_out_bed_start, timestamp))
            self.current_out_bed_start = None
            self.logger.info(f"设备 {self.device_id}: 离床结束，离床时长: {out_bed_duration:.1f}秒")
        
        # 更新最后在床时间
        self.last_in_bed_time = timestamp
        
        # 如果还没开始睡眠，则开始睡眠
        if not self.is_sleeping:
            self._start_sleep(timestamp)
    
    def _handle_out_bed(self, timestamp: float):
        """处理离床状态"""
        if not self.is_sleeping:
            return
        
        # 记录离床开始时间
        if not self.current_out_bed_start:
            self.current_out_bed_start = timestamp
            self.logger.info(f"设备 {self.device_id}: 用户离床，开始计时")
        
        # ✅ 只在没有计时器时才启动新的
        if self.out_bed_timer is None:
            self.out_bed_timer = threading.Timer(
                self.sleep_end_timeout, 
                self._confirm_sleep_end
            )
            self.out_bed_timer.start()
            self.logger.info(f"设备 {self.device_id}: 启动睡眠结束计时器 ({self.sleep_end_timeout}秒)")
    
    def _start_sleep(self, timestamp: float):
        """开始睡眠"""
        self.is_sleeping = True
        self.sleep_start_time = timestamp
        self.last_in_bed_time = timestamp
        self.out_bed_periods = []
        
        self.logger.info(f"设备 {self.device_id}: 开始睡眠 - {datetime.fromtimestamp(timestamp)}")
        
        # # 通知回调
        # if self.callback:
        #     self.callback('sleep_start', {
        #         'device_id': self.device_id,
        #         'timestamp': timestamp,
        #         'start_time_str': datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
        #     })
    
    def _confirm_sleep_end(self):
        """确认睡眠结束"""
        with self.lock:
            if not self.is_sleeping:
                return
            
            end_time = time.time()
            sleep_duration = self.last_in_bed_time - self.sleep_start_time
            
            # 处理最后一次离床（如果还在进行中）
            if self.current_out_bed_start:
                self.out_bed_periods.append((self.current_out_bed_start, end_time))
                self.current_out_bed_start = None
            
            self.logger.info(f"设备 {self.device_id}: 确认睡眠结束 - 总时长: {sleep_duration:.1f}秒 - 睡眠开始时间：{self.sleep_start_time} - 睡眠结束时间：{self.last_in_bed_time}")
            
            # 检查是否为有效睡眠
            if sleep_duration >= self.min_sleep_duration:
                sleep_record = SleepRecord(
                    device_id=self.device_id,
                    sleep_start_time=self.sleep_start_time,
                    sleep_end_time=self.last_in_bed_time,
                    total_duration=sleep_duration,
                    out_bed_times=self.out_bed_periods.copy()
                )
                
                self.logger.info(f"设备 {self.device_id}: 有效睡眠记录生成")
                
                # 通知回调
                if self.callback:
                    self.callback(
                        "sleep_report_start_end_time", 
                        {"device_id": sleep_record.device_id, "sleep_start_time": sleep_record.sleep_start_time, "sleep_end_time": sleep_record.sleep_end_time}
                    )
            else:
                self.logger.info(f"设备 {self.device_id}: 睡眠时长不足，不生成记录 ({sleep_duration:.1f}s < {self.min_sleep_duration}s)")
                
                # 通知回调
                # if self.callback:
                #     self.callback('sleep_end', {
                #         'device_id': self.device_id,
                #         'sleep_record': None,
                #         'is_valid': False,
                #         'reason': f'睡眠时长不足 ({sleep_duration:.1f}s < {self.min_sleep_duration}s)'
                #     })
            
            # 重置状态
            self._reset_state()
    
    def _reset_state(self):
        """重置睡眠状态"""
        self.is_sleeping = False
        self.sleep_start_time = None
        self.last_in_bed_time = None
        self.current_out_bed_start = None
        self.out_bed_periods = []
        
        if self.out_bed_timer:
            self.out_bed_timer.cancel()
            self.out_bed_timer = None
    
    def force_end_sleep(self) -> Optional[SleepRecord]:
        """强制结束当前睡眠（用于程序关闭等场景）"""
        with self.lock:
            if not self.is_sleeping:
                return None
            
            end_time = time.time()
            sleep_duration = self.last_in_bed_time - self.sleep_start_time
            
            if self.current_out_bed_start:
                self.out_bed_periods.append((self.current_out_bed_start, end_time))
            
            sleep_record = None
            if sleep_duration >= self.min_sleep_duration:
                sleep_record = SleepRecord(
                    device_id=self.device_id,
                    sleep_start_time=self.sleep_start_time,
                    sleep_end_time=self.last_in_bed_time,
                    total_duration=sleep_duration,
                    out_bed_times=self.out_bed_periods.copy()
                )
            
            self._reset_state()
            return sleep_record
    
    def get_current_status(self) -> Dict[str, Any]:
        """获取当前睡眠状态"""
        with self.lock:
            status = {
                'device_id': self.device_id,
                'is_sleeping': self.is_sleeping,
                'sleep_start_time': self.sleep_start_time,
                'last_in_bed_time': self.last_in_bed_time,
                'current_out_bed_start': self.current_out_bed_start,
                'out_bed_periods_count': len(self.out_bed_periods),
                'has_out_bed_timer': self.out_bed_timer is not None
            }
            
            if self.is_sleeping and self.sleep_start_time:
                current_time = time.time()
                status['current_sleep_duration'] = current_time - self.sleep_start_time
                status['sleep_start_str'] = datetime.fromtimestamp(self.sleep_start_time).strftime('%Y-%m-%d %H:%M:%S')
            
            return status