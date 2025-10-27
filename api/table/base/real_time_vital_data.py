#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time    : 2025/10/27 15:40
@Author  : weiyutao
@File    : real_time_vital_data.py
"""
from sqlalchemy import Column, Integer, Float, String, DateTime, BigInteger, Index, UniqueConstraint, Boolean
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.sql import func

from api.table.base.base import Base


class RealTimeVitalData(Base):
    """
    设备实时数据表
    存储设备采集的实时监测数据（呼吸、心率等）
    """
    __tablename__ = 'real_time_vital_data'
    
    # 主键
    id = Column(BigInteger, primary_key=True, autoincrement=True, comment='主键id')
    
    # 关联字段
    device_sn = Column(
        String(128), 
        nullable=False, 
        index=True, 
        comment='设备编号(关联device_info.device_sn)'
    )
    
    # 时间戳
    timestamp = Column(
        Float, 
        nullable=False, 
        comment='数据采集时间戳(Unix时间戳，秒级浮点数)'
    )
    
    # 呼吸相关数据
    breath_bpm = Column(
        Float, 
        nullable=True, 
        comment='呼吸频率(次/分钟)'
    )
    breath_curve = Column(
        JSON, 
        nullable=True, 
        comment='呼吸曲线数据(JSON数组，存储波形数据点)'
    )
    
    # 心率相关数据
    heart_bpm = Column(
        Float, 
        nullable=True, 
        comment='心率(次/分钟)'
    )
    heart_curve = Column(
        JSON, 
        nullable=True, 
        comment='心跳曲线数据(JSON数组，存储波形数据点)'
    )
    
    # 状态
    state = Column(
        Integer, 
        nullable=True, 
        comment='设备状态码(0-正常, 1-异常等，根据业务定义)'
    )
    
    # 系统字段
    tenant_id = Column(BigInteger, default=0, nullable=False, comment='租户编号')
    deleted = Column(Boolean, default=False, nullable=False, comment='是否删除')
    creator = Column(String(64), nullable=True, comment='创建者')
    create_time = Column(DateTime, default=func.now(), nullable=False, comment='创建时间')
    updater = Column(String(64), nullable=True, comment='更新者')
    update_time = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False, comment='更新时间')
    
    
    # 索引和约束定义
    __table_args__ = (
        # 唯一约束:设备编号 + 时间戳(确保同一设备同一时间只有一条记录)
        UniqueConstraint('device_sn', 'timestamp', name='uq_device_sn_timestamp'),
        # 复合索引:设备编号 + 时间戳(用于按设备查询时间范围内的数据)
        Index('idx_device_sn_timestamp', 'device_sn', 'timestamp'),
        # 单独的时间戳索引(用于数据清理、时间范围查询)
        Index('idx_timestamp', 'timestamp'),
    )