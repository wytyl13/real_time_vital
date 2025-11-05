#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time    : 2025/10/28 18:46
@Author  : weiyutao
@File    : message_center.py
"""


from sqlalchemy import Column, Integer, String, DateTime, Boolean, BigInteger, Text, JSON
from sqlalchemy.sql import func

from api.table.base.base import Base


class MessageCenter(Base):
    """
    消息中心表
    对应 MESSAGE_CENTER 表
    """
    __tablename__ = 'message_center'
    
    id = Column(BigInteger, primary_key=True, autoincrement=True, comment='主键id')
    device_sn = Column(String(128), nullable=False, comment='设备编号')
    message_type = Column(Integer, nullable=False, comment='消息类型(1:预警,2:设备状态,3:睡眠报告,4:系统通知)')
    title = Column(String(200), nullable=False, comment='消息标题')
    content = Column(Text, nullable=False, comment='消息内容')
    is_read = Column(Boolean, default=False, nullable=False, comment='是否已读')
    trigger_time = Column(BigInteger, nullable=False, comment='触发时间戳')
    duration = Column(Integer, nullable=True, comment='持续时长(秒,适用于预警类型)')
    extra_data = Column(JSON, nullable=True, comment='额外数据(心率值、睡眠评分等)')
    user_name = Column(String(64), nullable=False, comment='用户名')
    creator = Column(String(64), nullable=True, comment='创建者')
    create_time = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, comment='创建时间')
    updater = Column(String(64), nullable=True, comment='更新者')
    update_time = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False, comment='更新时间')
    tenant_id = Column(BigInteger, default=0, nullable=False, comment='租户编号')
    deleted = Column(Boolean, default=False, nullable=False, comment='是否删除')

# 消息类型枚举
class MessageType:
    ALERT = 1           # 预警（心率异常、呼吸健康等）
    DEVICE_STATUS = 2   # 设备状态（在线/离线）
    SLEEP_REPORT = 3    # 睡眠报告
    SYSTEM_NOTICE = 4   # 系统通知