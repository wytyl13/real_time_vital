#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time    : 2025/10/16 16:12
@Author  : weiyutao
@File    : device_info.py
"""


from sqlalchemy import Column, Integer, String, DateTime, Boolean, BigInteger
from sqlalchemy.sql import func

from api.table.base.base import Base


class DeviceInfo(Base):
    """
    设备信息表 - 异步版本
    对应 DEVICE_INFO 表
    """
    __tablename__ = 'device_info'
    
    id = Column(BigInteger, primary_key=True, autoincrement=True, comment='主键id')
    device_sn = Column(String(128), nullable=False, unique=True, comment='设备编号')
    device_type = Column(String(64), nullable=False, comment='设备类型')
    device_name = Column(String(128), nullable=False, comment='设备名称')
    device_location = Column(String(256), nullable=True, comment='设备位置')
    wifi_name = Column(String(128), nullable=True, comment='WiFi名称')
    wifi_password = Column(String(256), nullable=True, comment='WiFi密码')
    topic = Column(String(256), nullable=True, unique=True, comment='订阅主题')
    device_status = Column(String(30), default='active', nullable=False, comment='设备状态: online-在线, offline-离线')
    offline_time = Column(BigInteger, nullable=True, comment='离线时间（毫秒级时间戳，NULL表示未离线）')
    user_name = Column(String(64), nullable=False, unique=False, comment='用户名')
    creator = Column(String(64), nullable=True, comment='创建者')
    create_time = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, comment='创建时间')
    updater = Column(String(64), nullable=True, comment='更新者')
    update_time = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False, comment='更新时间')
    tenant_id = Column(BigInteger, default=0, nullable=False, comment='租户编号')
    deleted = Column(Boolean, default=False, nullable=False, comment='是否删除')
    
    subscription_status = Column(
        String(20), 
        default='pending',
        nullable=False,
        comment='订阅状态: pending-待订阅, subscribed-已订阅, failed-失败, unsubscribed-已取消'
    )