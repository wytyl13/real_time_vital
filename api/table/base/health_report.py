#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time    : 2025/09/26
@Author  : weiyutao
@File    : health_report.py
"""

from sqlalchemy import Column, BigInteger, String, DateTime, Float, Integer, Text, func
from datetime import datetime
from api.table.base.base import Base

class HealthReport(Base):
    """
    睡眠统计数据表
    对应 SX_SLEEP_STATISTICS 表
    """
    __tablename__ = 'health_report'
    
    # 主键
    id = Column(BigInteger, primary_key=True, autoincrement=True, comment='主键id')
    
    # 设备信息
    device_sn = Column(String(64), nullable=False, comment='设备序列号')
    device_type = Column(String(32), nullable=True, comment='设备类型')
    
    # 睡眠区间
    sleep_start_time = Column(DateTime, nullable=False, comment='睡眠区间起始时间')
    sleep_end_time = Column(DateTime, nullable=False, comment='睡眠区间终止时间')
    
    # 生理指标
    avg_breath_rate = Column(Float, nullable=True, comment='平均呼吸率')
    avg_heart_rate = Column(Float, nullable=True, comment='平均心率')
    heart_rate_variability = Column(Float, nullable=True, comment='心率变异性系数')
    
    # 行为统计
    body_movement_count = Column(Integer, nullable=True, comment='体动次数')
    apnea_count = Column(Integer, nullable=True, comment='呼吸暂停次数')
    rapid_breathing_count = Column(Integer, nullable=True, comment='呼吸急促次数')
    leave_bed_count = Column(Integer, nullable=True, comment='离床次数')
    
    # 时长统计 (以小时字符串格式存储，如"6小时49分22秒")
    total_duration = Column(String(32), nullable=True, comment='统计总时长(小时字符串格式)')
    in_bed_duration = Column(String(32), nullable=True, comment='在床时长(小时字符串格式)')
    out_bed_duration = Column(String(32), nullable=True, comment='离床时长(小时字符串格式)')
    deep_sleep_duration = Column(String(32), nullable=True, comment='深睡眠时长(小时字符串格式)')
    light_sleep_duration = Column(String(32), nullable=True, comment='浅睡眠时长(小时字符串格式)')
    awake_duration = Column(String(32), nullable=True, comment='清醒时长(小时字符串格式)')
    
    # 关键时间点
    bed_time = Column(DateTime, nullable=True, comment='上床时间')
    sleep_time = Column(DateTime, nullable=True, comment='入睡时间')
    wake_time = Column(DateTime, nullable=True, comment='醒来时间')
    leave_bed_time = Column(DateTime, nullable=True, comment='离床时间')
    
    deep_sleep_ratio = Column(Float, nullable=True, comment='深睡眠比例')
    light_sleep_ratio = Column(Float, nullable=True, comment='浅睡眠比例')
    
    # 健康报告
    health_report = Column(Text, nullable=True, comment='健康报告详情')
    
    # 系统字段
    creator = Column(String(64), nullable=True, comment='创建者')
    create_time = Column(DateTime, default=func.now(), nullable=False, comment='创建时间')
    updater = Column(String(64), nullable=True, comment='更新者')
    update_time = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False, comment='更新时间')
    
    def __repr__(self):
        return f"<SleepStatistics(device_sn='{self.device_sn}', device_type='{self.device_type}', sleep_start_time='{self.sleep_start_time}')>"
    
    def to_dict(self):
        """转换为字典格式"""
        return {
            'id': self.id,
            'device_sn': self.device_sn,
            'device_type': self.device_type,
            'sleep_start_time': self.sleep_start_time.isoformat() if self.sleep_start_time else None,
            'sleep_end_time': self.sleep_end_time.isoformat() if self.sleep_end_time else None,
            
            # 生理指标
            'avg_breath_rate': self.avg_breath_rate,
            'avg_heart_rate': self.avg_heart_rate,
            'heart_rate_variability': self.heart_rate_variability,
            
            # 行为统计
            'body_movement_count': self.body_movement_count,
            'apnea_count': self.apnea_count,
            'rapid_breathing_count': self.rapid_breathing_count,
            'leave_bed_count': self.leave_bed_count,
            
            # 时长统计
            'total_duration': self.total_duration,
            'in_bed_duration': self.in_bed_duration,
            'out_bed_duration': self.out_bed_duration,
            'deep_sleep_duration': self.deep_sleep_duration,
            'light_sleep_duration': self.light_sleep_duration,
            'awake_duration': self.awake_duration,
            
            # 关键时间点
            'bed_time': self.bed_time.isoformat() if self.bed_time else None,
            'sleep_time': self.sleep_time.isoformat() if self.sleep_time else None,
            'wake_time': self.wake_time.isoformat() if self.wake_time else None,
            'leave_bed_time': self.leave_bed_time.isoformat() if self.leave_bed_time else None,
            
            'deep_sleep_ratio': self.deep_sleep_ratio,
            'light_sleep_ratio': self.light_sleep_ratio,
            
            # 健康报告
            'health_report': self.health_report,
            
            # 系统字段
            'creator': self.creator,
            'create_time': self.create_time.isoformat() if self.create_time else None,
            'updater': self.updater,
            'update_time': self.update_time.isoformat() if self.update_time else None,
        }
    
    @classmethod
    def from_dict(cls, data_dict):
        """从字典创建实例"""
        return cls(
            device_sn=data_dict.get('device_sn'),
            device_type=data_dict.get('device_type'),
            sleep_start_time=datetime.fromisoformat(data_dict.get('sleep_start_time')) 
                            if data_dict.get('sleep_start_time') else None,
            sleep_end_time=datetime.fromisoformat(data_dict.get('sleep_end_time'))
                          if data_dict.get('sleep_end_time') else None,
            
            # 生理指标
            avg_breath_rate=data_dict.get('avg_breath_rate'),
            avg_heart_rate=data_dict.get('avg_heart_rate'),
            heart_rate_variability=data_dict.get('heart_rate_variability'),
            
            # 行为统计
            body_movement_count=data_dict.get('body_movement_count'),
            apnea_count=data_dict.get('apnea_count'),
            rapid_breathing_count=data_dict.get('rapid_breathing_count'),
            leave_bed_count=data_dict.get('leave_bed_count'),
            
            # 时长统计
            total_duration=data_dict.get('total_duration'),
            in_bed_duration=data_dict.get('in_bed_duration'),
            out_bed_duration=data_dict.get('out_bed_duration'),
            deep_sleep_duration=data_dict.get('deep_sleep_duration'),
            light_sleep_duration=data_dict.get('light_sleep_duration'),
            awake_duration=data_dict.get('awake_duration'),
            deep_sleep_ratio=data_dict.get('deep_sleep_ratio'),
            light_sleep_ratio=data_dict.get('light_sleep_ratio'),
            
            # 关键时间点
            bed_time=datetime.fromisoformat(data_dict.get('bed_time')) 
                     if data_dict.get('bed_time') else None,
            sleep_time=datetime.fromisoformat(data_dict.get('sleep_time'))
                       if data_dict.get('sleep_time') else None,
            wake_time=datetime.fromisoformat(data_dict.get('wake_time'))
                      if data_dict.get('wake_time') else None,
            leave_bed_time=datetime.fromisoformat(data_dict.get('leave_bed_time'))
                           if data_dict.get('leave_bed_time') else None,
            
            # 健康报告
            health_report=data_dict.get('health_report'),
            
            # 系统字段
            creator=data_dict.get('creator'),
            updater=data_dict.get('updater'),
        )