#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time    : 2025/10/27 10:38
@Author  : weiyutao
@File    : sleep_data_storage.py
@Modified: 2025/10/27 - 添加离床状态首尾保存逻辑
"""

import time
import json
from dataclasses import dataclass
from typing import Optional, List, Callable, Dict, Any, Set
from collections import defaultdict
from enum import IntEnum
import asyncio
import threading
# import redis.asyncio as redis
import redis

from base.consumer_tool_pool import ConsumerToolPool
from api.table.base.real_time_vital_data import RealTimeVitalData
from agent.provider.sql_provider import SqlProvider
from agent.base.base_tool import tool
from tools.utils import Utils
from agent.provider.sql_provider import SqlConfig

utils = Utils()

class BedState(IntEnum):
    """床状态枚举"""
    IN_BED = 0
    OUT_BED = 1
    MOVEMENT = 2
    WEAK_BREATH = 3
    HEAVY_OBJECT = 4
    SNORING = 5


@dataclass
class DataPoint:
    """数据点"""
    device_sn: str
    timestamp: float
    breath_bpm: float
    breath_curve: List[float]
    heart_bpm: float
    heart_curve: List[float]
    state: int

    def to_db_dict(self, creator: str = "system", tenant_id: int = 0) -> Dict[str, Any]:
        return {
            'device_sn': self.device_sn,
            'timestamp': self.timestamp,
            'breath_bpm': self.breath_bpm,
            'breath_curve': json.dumps(self.breath_curve) if isinstance(self.breath_curve, list) else self.breath_curve,
            'heart_bpm': self.heart_bpm,
            'heart_curve': json.dumps(self.heart_curve) if isinstance(self.heart_curve, list) else self.heart_curve,
            'state': self.state,
            'creator': creator,
            'tenant_id': tenant_id
        }

    @classmethod
    def from_uart_data(cls, uart_data: tuple) -> 'DataPoint':
        return cls(
            timestamp=uart_data[0],
            breath_bpm=uart_data[1],
            breath_curve=uart_data[2] if isinstance(uart_data[2], list) else [],
            heart_bpm=uart_data[3],
            heart_curve=uart_data[4] if isinstance(uart_data[4], list) else [],
            state=uart_data[7],
            device_sn=uart_data[11]
        )


class SleepDataStorage:
    """
    睡眠数据存储管理器 - 支持离床状态首尾保存
    
    核心逻辑:
    1. 每次输入60秒数据，只判断最新1秒是否需要存储
    2. 体动、弱呼吸状态：全部存储
    3. 离床状态：只保存首尾，中间不保存
    4. 其他状态：按规则存储
    5. 状态变化：必须存储
    """
    
    def __init__(self, 
                 alert_enabled: bool = True,
                 max_normal_interval: float = 60.0,
                 redis_config: SqlConfig = None,  # 新增参数
                 websocket_alert_enabled: bool = True,  # 新增参数
    ):
        self.alert_enabled = alert_enabled
        self.max_normal_interval = max_normal_interval
        
        
        self.alert_types = {
            BedState.WEAK_BREATH: 'WEAK_BREATH',
            BedState.MOVEMENT: 'MOVEMENT',
            # 可以扩展更多
        }
        self.active_alerts: Dict[str, Dict[str, int]] = {}
        
        
        # 异常状态定义（需要全部存储）
        self.anomaly_states = {BedState.MOVEMENT, BedState.WEAK_BREATH}
        
        # 首尾存储状态定义（只保存开始和结束）
        self.edge_only_states = {BedState.OUT_BED}
        
        # 每个设备的存储状态
        self.device_states: Dict[str, DeviceState] = {}
        
        self.logger = utils.setup_logger(name="SleepDataStorage")

        self.websocket_alert_enabled = websocket_alert_enabled
        self.redis_client = None
        self.redis_alert_channel = 'websocket_alerts'

        # 初始化Redis连接
        if websocket_alert_enabled and redis_config:
            self._init_redis_client(redis_config)
        
        self.last_storage_times = {}
        print("="*80)
        print("睡眠数据存储管理器初始化完成（支持离床首尾保存）")
        print(f"正常状态最大存储间隔: {max_normal_interval}秒")
        print(f"异常状态(全部存储): {[self.get_state_name(s) for s in self.anomaly_states]}")
        print(f"首尾存储状态(只保存开始和结束): {[self.get_state_name(s) for s in self.edge_only_states]}")
        print("="*80)
    
    
    
    def _init_redis_client(self, redis_config: SqlConfig):
        """初始化Redis客户端"""
        try:
            # ✅ 使用同步Redis客户端
            self.redis_client = redis.Redis(
                host=redis_config.host,
                port=redis_config.port,
                db=redis_config.database,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_keepalive=True,
                health_check_interval=30
            )
            self.logger.info("✅ Redis客户端初始化成功（用于WebSocket预警）")
        except Exception as e:
            self.logger.error(f"❌ Redis客户端初始化失败: {e}")
            self.redis_client = None
    
    
    
    def _send_websocket_alert(self, device_sn: str, alert_type: str, action: str, 
                               data: DataPoint, duration: float = None):
        """发送WebSocket预警消息"""
        if not self.websocket_alert_enabled or not self.redis_client:
            return
        
        try:
            message = {
                "type": "alert",
                "device_id": device_sn,
                "alert_type": alert_type,
                "action": action,  # "start" 或 "end"
                "timestamp": int(data.timestamp * 1000),  # 转为毫秒
                "data": {
                    "state": data.state,
                    "breath_bpm": data.breath_bpm,
                    "heart_bpm": data.heart_bpm
                }
            }
            
            if duration is not None:
                message["duration"] = duration
                
            # 发布到Redis
            self.redis_client.publish(
                self.redis_alert_channel, 
                json.dumps(message)
            )
            
            self.logger.info(f"📤 WebSocket预警已发送: {device_sn} {alert_type} {action}")
            
        except Exception as e:
            self.logger.error(f"❌ WebSocket预警发送失败: {e}")
    
    
    
    def process_uart_data_window(self, 
                                 device_sn: str,
                                 uart_data_list: List[tuple]) -> tuple[bool, str]:
        """
        处理UART数据窗口
        
        Args:
            device_sn: 设备ID
            uart_data_list: 最近60秒的UART数据列表
        
        Returns:
            (是否存储, 原因)
        """
        if not uart_data_list:
            return False, "无数据"
        
        # 转换为DataPoint列表
        data_points = [DataPoint.from_uart_data(d) for d in uart_data_list]
        result = self.process_time_window(device_sn, data_points)
        
        # 处理数据
        return result
    
    
    def process_time_window(self, 
                           device_sn: str,
                           data_points: List[DataPoint]) -> tuple[bool, str]:
        """
        处理时间窗口数据，判断最新1秒是否需要存储
        
        Args:
            device_sn: 设备ID
            data_points: 最近60秒的数据列表（按时间戳升序）
        
        Returns:
            (是否存储, 原因)
        """
        if not data_points:
            return False, "无数据"
        
        # 按时间戳排序
        sorted_data = sorted(data_points, key=lambda x: x.timestamp)
        
        # 获取最新数据点
        latest_data = sorted_data[-1]
        
        # 获取上一秒的数据点（如果存在）
        previous_data = sorted_data[-2] if len(sorted_data) >= 2 else None
        
        
        # 获取或创建设备状态  
        # if device_sn not in self.device_states:
        #     self.device_states[device_sn] = DeviceState()
        
        
        # state = self.device_states[device_sn]
        # 防重复处理：检查是否已经处理过这个时间戳
        # if (state.last_processed_timestamp is not None and 
        #     latest_data.timestamp <= state.last_processed_timestamp):
        #     return False, f"已处理过时间戳{latest_data.timestamp}", latest_data
        # 更新最后处理时间戳
        # state.last_processed_timestamp = latest_data.timestamp
        # 判断是否需要存储
        should_store, reason = self._should_store(latest_data, previous_data)
        # should_store, reason = self._should_store_hybrid(latest_data, previous_data, state)

        # 更新存储时间戳
        if should_store:
            self.last_storage_times[device_sn] = latest_data.timestamp
        # if should_store:
        #     state.update_storage_time(latest_data.timestamp)
        
        # 新增：预警检测（在存储判断之后）
        if self.alert_enabled:
            previous_state = previous_data.state if previous_data else None
            # self._check_and_handle_alerts_with_duration(device_sn, data_points, latest_data, previous_state, state)
            self._check_and_handle_alerts(device_sn, latest_data, previous_state)
        
        return should_store, reason, latest_data
    
    
    def _check_and_handle_alerts(self, device_sn: str, current_data: DataPoint, last_state: Optional[int]):
        """检查并处理预警"""
        current_state = current_data.state
        
        if last_state == current_state:
            return
        
        
        # 调试日志
        # self.logger.info(f"设备 {device_sn}: 当前状态={self.get_state_name(current_state)}, 上次状态={self.get_state_name(last_state) if last_state is not None else '无'}")
        
        # 检查每种预警类型
        for state_enum, alert_type in self.alert_types.items():
            current_is_alert = (current_state == state_enum)
            last_was_alert = (last_state == state_enum) if last_state is not None else False
            
            # 调试日志
            # self.logger.info(f"预警类型 {alert_type}: 当前={current_is_alert}, 之前={last_was_alert}")
            
            if current_is_alert and not last_was_alert:
                # 预警开始
                # self.logger.info(f"{device_sn}: -------------------- 开始预警 {alert_type}")
                self._start_alert_(device_sn, alert_type, current_data)
                
            elif not current_is_alert and last_was_alert:
                # 预警结束
                # self.logger.info(f"{device_sn}: -------------------- 结束预警 {alert_type}")
                self._end_alert_(device_sn, alert_type, current_data, 1.1111)


    def _check_and_handle_alerts_with_duration(self, device_sn: str, data_points:  List[DataPoint], current_data: DataPoint, 
                              previous_state: Optional[int], state: 'DeviceState'):
        """简化的预警处理逻辑 - 防止重复触发"""
        current_state = current_data.state
        current_time = current_data.timestamp
        
        # 预警配置
        configs = {
            'MOVEMENT': {'min_duration': 2.0, 'max_gap': 5.0, 'cooldown': 10.0},
            'WEAK_BREATH': {'min_duration': 3.0, 'max_gap': 8.0, 'cooldown': 15.0},
        }
        
        # 处理体动预警 - 每次只调用一次
        is_movement = (current_state == BedState.MOVEMENT)
        self._handle_alert_simple(device_sn, data_points, current_data, 'MOVEMENT', is_movement, current_time, state, configs['MOVEMENT'])
        
        # 处理弱呼吸预警 - 每次只调用一次
        is_weak_breath = (current_state == BedState.WEAK_BREATH)
        self._handle_alert_simple(device_sn, data_points, current_data, 'WEAK_BREATH', is_weak_breath, current_time, state, configs['WEAK_BREATH'])


    # def _handle_smart_alert(self, device_sn: str,  current_data: DataPoint, alert_type: str, is_current_state: bool,
    #                    current_time: float, state: 'DeviceState', config: dict):
    #     """智能预警处理"""
    #     if alert_type not in state.alert_states:
    #         state.alert_states[alert_type] = {
    #             'is_detecting': False, 'is_active': False, 'start_time': 0,
    #             'last_detection_time': 0, 'last_alert_end_time': 0
    #         }
        
    #     alert_state = state.alert_states[alert_type]
        
    #     if is_current_state:
    #         # 当前是预警状态
    #         if not alert_state['is_detecting'] and not alert_state['is_active']:
    #             # 检查冷却期
    #             if (alert_state['last_alert_end_time'] == 0 or 
    #                 current_time - alert_state['last_alert_end_time'] >= config['cooldown']):
    #                 alert_state['is_detecting'] = True
    #                 alert_state['start_time'] = current_time
    #                 alert_state['last_detection_time'] = current_time
    #                 self.logger.info(f"{device_sn}: 开始{alert_type}检测...")
    #         else:
    #             # 更新最后检测时间
    #             alert_state['last_detection_time'] = current_time
    #     else:
    #         # 当前不是预警状态
    #         if alert_state['is_detecting'] or alert_state['is_active']:
    #             gap = current_time - alert_state['last_detection_time']
    #             if gap > config['max_gap']:
    #                 # 间隔太长，结束预警
    #                 if alert_state['is_active']:
    #                     duration = current_time - alert_state['start_time']
    #                     self._end_alert(device_sn, alert_type, current_data, duration)
    #                     # self.logger.info(f"{device_sn}: ==================== 结束{alert_type}预警 (持续{duration:.1f}秒)")
    #                     alert_state['last_alert_end_time'] = current_time
                    
    #                 # 重置状态
    #                 alert_state['is_detecting'] = False
    #                 alert_state['is_active'] = False
        
    #     # 检查是否应该激活预警
    #     if (alert_state['is_detecting'] and not alert_state['is_active'] and 
    #         current_time - alert_state['start_time'] >= config['min_duration']):
    #         alert_state['is_active'] = True
    #         self._start_alert(device_sn, alert_type, current_data)
    #         # self.logger.info(f"{device_sn}: ==================== 开始{alert_type}预警")
    
    
    def _handle_alert_simple(self, device_sn: str, data_points: List[DataPoint], current_data: DataPoint, alert_type: str, 
                        is_current_state: bool, current_time: float, state: 'DeviceState', config: dict):
        """简化的预警处理 - 避免重复触发（线程安全版本）"""
        
        # 加锁保护整个预警处理过程
        if not hasattr(state, 'lock'):
            state.lock = threading.Lock()
        
        with state.lock:
            if alert_type not in state.alert_states:
                state.alert_states[alert_type] = {
                    'is_active': False, 
                    'start_time': 0,
                    'first_detection': 0,
                    'last_detection': 0,
                    'last_end_time': 0,
                    'processing': False  # 防重复处理标志
                }
            
            alert_state = state.alert_states[alert_type]
            
            # 防重复：如果正在处理中，直接返回
            if alert_state.get('processing', False):
                return
            
            # 防重复：检查时间戳是否已处理过
            if alert_state.get('last_processed_time') == current_time:
                return
                
            # 设置处理标志和时间戳
            alert_state['processing'] = True
            alert_state['last_processed_time'] = current_time
            
            try:
                if is_current_state:
                    # 当前是预警状态
                    if not alert_state['is_active']:
                        # 检查冷却期
                        if (alert_state['last_end_time'] == 0 or 
                            current_time - alert_state['last_end_time'] >= config['cooldown']):
                            
                            if alert_state['first_detection'] == 0:
                                alert_state['first_detection'] = current_time
                                self.logger.info(f"{device_sn}: 开始{alert_type}检测...")
                            
                            alert_state['last_detection'] = current_time
                            
                            # 检查是否达到最小持续时间
                            if current_time - alert_state['first_detection'] >= config['min_duration']:
                                # 再次检查是否已经激活（双重检查）
                                if not alert_state['is_active']:
                                    alert_state['is_active'] = True
                                    alert_state['start_time'] = current_time
                                    self._start_alert(device_sn, data_points, alert_type, current_data)
                                    self.logger.info(f"{device_sn}: ==================== 开始{alert_type}预警")
                    else:
                        # 已经激活，更新检测时间
                        alert_state['last_detection'] = current_time
                
                else:
                    # 不是预警状态
                    if alert_state['is_active']:
                        # 检查间隔
                        gap = current_time - alert_state['last_detection']
                        if gap > config['max_gap']:
                            # 再次检查是否仍然激活（双重检查）
                            if alert_state['is_active']:
                                # 结束预警
                                duration = current_time - alert_state['start_time']
                                self._end_alert(device_sn, data_points, alert_type, current_data, duration)
                                self.logger.info(f"{device_sn}: ==================== 结束{alert_type}预警 (持续{duration:.1f}秒)")
                                
                                # 重置状态
                                alert_state['is_active'] = False
                                alert_state['last_end_time'] = current_time
                                alert_state['first_detection'] = 0
                                alert_state['start_time'] = 0
                    elif alert_state['first_detection'] > 0:
                        # 未激活但在检测中，检查是否重置
                        gap = current_time - alert_state['last_detection']
                        if gap > config['max_gap']:
                            alert_state['first_detection'] = 0
                            alert_state['last_detection'] = 0
            
            finally:
                # 清除处理标志
                alert_state['processing'] = False
    
    


    # def _check_and_handle_alerts_with_duration(self, device_sn: str, current_data: DataPoint, 
    #                                       previous_state: Optional[int], state: 'DeviceState'):
    #     """检查预警并计算持续时间"""
    #     current_state = current_data.state
        
    #     # 如果状态没变化，不需要处理预警变化
    #     if previous_state is not None and current_state == previous_state:
    #         return
        
    #     # 检查每种预警类型
    #     for state_enum, alert_type in self.alert_types.items():
    #         current_is_alert = (current_state == state_enum)
    #         last_was_alert = (previous_state == state_enum) if previous_state is not None else False
            
    #         if current_is_alert and not last_was_alert:
    #             # 预警开始
    #             state.alert_start_times[alert_type] = current_data.timestamp
    #             state.active_alerts.add(alert_type)
    #             self._start_alert(device_sn, alert_type, current_data)
    #         elif not current_is_alert and last_was_alert:
    #             # 预警结束，计算持续时间
    #             if alert_type in state.alert_start_times:
    #                 duration = current_data.timestamp - state.alert_start_times[alert_type]
    #                 del state.alert_start_times[alert_type]
    #                 state.active_alerts.discard(alert_type)
    #                 self._end_alert(device_sn, alert_type, current_data, duration)


    def _start_alert(self, device_sn: str, data_points: List[DataPoint], alert_type: str, data: DataPoint) -> int:
        """开始预警 - 防重复调用"""
        if device_sn not in self.device_states:
            return
        
        state = self.device_states[device_sn]
        
        # 防重复：检查是否已经记录过这次开始
        alert_key = f"{alert_type}_start_{data.timestamp}"
        
        if not hasattr(state, 'logged_alerts'):
            state.logged_alerts = set()
        
        if alert_key in state.logged_alerts:
            return  # 已经记录过，直接返回
        
        # 记录这次预警开始
        state.logged_alerts.add(alert_key)
        
        # 清理过期的记录（保留最近100个）
        if len(state.logged_alerts) > 100:
            state.logged_alerts = set(list(state.logged_alerts)[-50:])
        data_ = data_points[-2:]
        self.logger.info(f"{device_sn}: -------------------- 开始预警 {data_} {alert_type}")


    def _end_alert(self, device_sn: str, data_points: List[DataPoint], alert_type: str, data: DataPoint, duration: Any):
        """结束预警 - 防重复调用"""
        if device_sn not in self.device_states:
            return
        
        state = self.device_states[device_sn]
        
        # 防重复：检查是否已经记录过这次结束
        alert_key = f"{alert_type}_end_{data.timestamp}"
        
        if not hasattr(state, 'logged_alerts'):
            state.logged_alerts = set()
        
        if alert_key in state.logged_alerts:
            return  # 已经记录过，直接返回
        
        # 记录这次预警结束
        state.logged_alerts.add(alert_key)
        
        # 清理过期的记录（保留最近100个）
        if len(state.logged_alerts) > 100:
            state.logged_alerts = set(list(state.logged_alerts)[-50:])
        data_ = data_points[-2:]
        self.logger.info(f"{device_sn}: -------------------- 结束预警 {alert_type}，持续时间: {duration:.1f}秒 {data_}")




    def _start_alert_(self, device_sn: str, alert_type: str, data: DataPoint) -> int:
        """开始预警"""
        # 实现预警开始逻辑
        # 1. 先发送WebSocket预警
        if self.websocket_alert_enabled:
            self._send_websocket_alert(device_sn, alert_type, "start", data)
        
        # 2. 再存储到数据库（现有代码保持不变）
        utils.request_url(
            url="https://ai.shunxikj.com:9039/api/message_center/save",
            param_dict={
                "title": "title",
                "device_sn": device_sn, 
                "message_type": 1, 
                "user_name": "user_name", 
                "trigger_time": data.timestamp,
                "content": alert_type
            }
        )
        self.logger.info(f"{device_sn}: -------------------- 开始预警 {data} {alert_type}")


    def _end_alert_(self, device_sn: str, alert_type: str, data: DataPoint, duration: Any):
        """结束预警"""  
        # 实现预警结束逻辑
        # 1. 先发送WebSocket预警
        if self.websocket_alert_enabled:
            self._send_websocket_alert(device_sn, alert_type, "end", data, duration)
        
        # 2. 再存储到数据库（现有代码保持不变）
        utils.request_url(
            url="https://ai.shunxikj.com:9039/api/message_center/save",
            param_dict={
                "title": "title",
                "device_sn": device_sn, 
                "message_type": 1, 
                "user_name": "user_name", 
                "trigger_time": data.timestamp,
                "content": alert_type
            }
        )
        self.logger.info(f"{device_sn}: -------------------- 结束预警 {alert_type}，持续时间: {duration:.1f}秒 {data}")
    
    
    def _should_store(self, current_data: DataPoint, previous_data: Optional[DataPoint]) -> tuple[bool, str]:
        """
        简化版存储判断
        
        Args:
            current_data: 当前秒数据
            previous_data: 上一秒数据（可能为None）
        """
        current_state = current_data.state
        is_anomaly = current_state in self.anomaly_states
        is_edge_only = current_state in self.edge_only_states
        
        # 规则1: 首次数据（没有上一秒数据）
        if previous_data is None:
            return True, "首次数据"
        
        previous_state = previous_data.state
        
        # 规则2: 状态变化
        if current_state != previous_state:
            if is_edge_only:
                return True, f"离床状态变化: {self.get_state_name(previous_state)} → {self.get_state_name(current_state)}"
            else:
                return True, f"状态变化: {self.get_state_name(previous_state)} → {self.get_state_name(current_state)}"
        
        # 规则3: 异常状态（全部存储）
        if is_anomaly:
            return True, f"异常状态({self.get_state_name(current_state)})"
        
        # 规则4: 首尾存储状态（离床状态持续期间不存储）
        if is_edge_only:
            return False, f"{self.get_state_name(current_state)}持续期间不存储"
        
        # 规则5: 其他状态（按间隔存储）
        if current_data.device_sn in self.last_storage_times:
            time_gap = current_data.timestamp - self.last_storage_times[current_data.device_sn]
        else:
            time_gap = float('inf')  # 首次数据，设为无限大
        # time_gap = current_data.timestamp - previous_data.timestamp
        if time_gap >= self.max_normal_interval:
            return True, f"{self.get_state_name(current_state)}最大间隔({time_gap:.1f}秒)"
        
        return False, f"{self.get_state_name(current_state)}间隔不足({time_gap:.1f}秒)"
    
    
    def _should_store_hybrid(self, current_data: DataPoint, previous_data: Optional[DataPoint], 
                        state: 'DeviceState') -> tuple[bool, str]:
        """
        混合判断：状态变化用窗口数据，时间间隔用缓存状态
        """
        current_state = current_data.state
        is_anomaly = current_state in self.anomaly_states
        is_edge_only = current_state in self.edge_only_states
        
        # 规则1: 首次数据
        if state.last_storage_timestamp is None:
            return True, "首次数据"
        
        # 规则2: 状态变化（用窗口数据判断）
        if previous_data and current_state != previous_data.state:
            if is_edge_only:
                return True, f"离床状态变化: {self.get_state_name(previous_data.state)} → {self.get_state_name(current_state)}"
            else:
                return True, f"状态变化: {self.get_state_name(previous_data.state)} → {self.get_state_name(current_state)}"
        
        # 规则3: 异常状态（全部存储）
        if is_anomaly:
            return True, f"异常状态({self.get_state_name(current_state)})"
        
        # 规则4: 首尾存储状态（离床状态持续期间不存储）
        if is_edge_only:
            return False, f"{self.get_state_name(current_state)}持续期间不存储"
        
        # 规则5: 时间间隔判断（用缓存的上次存储时间）
        time_gap = current_data.timestamp - state.last_storage_timestamp
        if time_gap >= self.max_normal_interval:
            return True, f"{self.get_state_name(current_state)}最大间隔({time_gap:.1f}秒)"
        
        return False, f"{self.get_state_name(current_state)}间隔不足({time_gap:.1f}秒)"
    
    
    # def _should_store(self, 
    #                  data: DataPoint, 
    #                  state: 'DeviceState') -> tuple[bool, str]:
    #     """
    #     判断是否应该存储数据
        
    #     规则:
    #     1. 首次数据 → 存储
    #     2. 状态变化 → 存储
    #     3. 异常状态(体动、弱呼吸) → 全部存储
    #     4. 首尾存储状态(离床) → 只在状态变化时存储，持续期间不存储
    #     5. 其他状态 → 按最大间隔存储
    #     """
    #     current_state = data.state
    #     is_anomaly = current_state in self.anomaly_states
    #     is_edge_only = current_state in self.edge_only_states
        
    #     # 规则1: 首次数据
    #     if state.last_stored_timestamp is None:
    #         return True, "首次数据"
        
    #     # 规则2: 状态变化（包括离床状态的开始和结束）
    #     if current_state != state.last_stored_state:
    #         if is_edge_only:
    #             return True, f"离床状态变化: {self.get_state_name(state.last_stored_state)} → {self.get_state_name(current_state)}"
    #         else:
    #             return True, f"状态变化: {self.get_state_name(state.last_stored_state)} → {self.get_state_name(current_state)}"
        
    #     # 规则3: 异常状态（全部存储）
    #     if is_anomaly:
    #         return True, f"异常状态({self.get_state_name(current_state)})"
        
    #     # 规则4: 首尾存储状态（离床状态持续期间不存储）
    #     if is_edge_only:
    #         return False, f"{self.get_state_name(current_state)}持续期间不存储"
        
    #     # 规则5: 其他状态（按间隔存储）
    #     time_gap = data.timestamp - state.last_stored_timestamp
    #     if time_gap >= self.max_normal_interval:
    #         return True, f"{self.get_state_name(current_state)}最大间隔({time_gap:.1f}秒)"
        
    #     return False, f"{self.get_state_name(current_state)}间隔不足({time_gap:.1f}秒)"
    
    
    def get_state_name(self, state: int) -> str:
        """获取状态名称"""
        state_names = {
            0: "在床", 1: "离床", 2: "体动",
            3: "弱呼吸", 4: "重物", 5: "打鼾"
        }
        return state_names.get(state, f"未知({state})")


    def get_device_stats(self, device_sn: str) -> Dict:
        """获取设备统计信息"""
        device_state = self.device_states.get(device_sn)
        if not device_state:
            return {"device_sn": device_sn, "status": "未处理"}
        
        return {
            "device_sn": device_sn,
            "last_storage_time": device_state.last_stored_timestamp,
            # "last_state": self.get_state_name(device_state.last_stored_state) if device_state.last_stored_state is not None else "未知"
        }


class AlertState:
    is_detecting: bool = False      # 是否在检测中
    is_active: bool = False         # 是否激活预警
    start_time: float = 0          # 开始检测时间
    last_detection_time: float = 0  # 最后检测时间
    last_alert_end_time: float = 0  # 上次预警结束时间



class DeviceState:
    """设备状态"""
    def __init__(self):
        self.last_storage_timestamp: Optional[float] = None
        self.alert_states: Dict[str, AlertState] = {}
        self.last_processed_timestamp: Optional[float] = None  # 防重复处理
        self.lock = threading.Lock()  # 线程安全
    
    def update_storage_time(self, timestamp: float):
        """更新存储时间"""
        self.last_storage_timestamp = timestamp
    
    def get_alert_state(self, alert_type: str) -> AlertState:
        """获取预警状态"""
        if alert_type not in self.alert_states:
            self.alert_states[alert_type] = AlertState()
        return self.alert_states[alert_type]


# class DeviceState:
#     """设备状态（轻量级）"""
#     __slots__ = ['last_stored_timestamp', 'last_stored_state']
    
#     def __init__(self):
#         self.last_stored_timestamp: Optional[float] = None
#         self.last_stored_state: Optional[int] = None
    
#     def update(self, data: DataPoint):
#         """更新状态"""
#         self.last_stored_timestamp = data.timestamp
#         self.last_stored_state = data.state


# ========== 测试代码 ==========
if __name__ == "__main__":
    import numpy as np
    from collections import deque
    
    def mock_single_insert(data_dict):
        """模拟单条插入"""
        pass  # 实际插入由存储管理器内部打印
    
    def generate_uart_data(timestamp, state, device_sn="TEST_DEVICE"):
        """生成模拟UART数据"""
        breath_curve = [1300 + np.random.randint(-50, 50) for _ in range(25)]
        heart_curve = [1300 + np.random.randint(-50, 50) for _ in range(25)]
        
        return (
            timestamp,                          # 0: timestamp
            15.0 + np.random.random() * 5,     # 1: breath_bpm
            breath_curve,                       # 2: breath_curve
            70.0 + np.random.random() * 10,    # 3: heart_bpm
            heart_curve,                        # 4: heart_curve
            0.0,                                # 5: unused
            0.0,                                # 6: unused
            state,                              # 7: state
            0.0,                                # 8: unused
            0.0,                                # 9: unused
            0,                                  # 10: unused
            device_sn                           # 11: device_id
        )
    
    # 创建存储管理器
    storage = SleepDataStorage(
        single_insert_db=mock_single_insert,
        max_normal_interval=60.0
    )
    
    device_sn = "TEST_DEVICE"
    base_time = time.time()
    
    # ========== 离床状态首尾保存测试 ==========
    print("\n" + "="*80)
    print("测试场景: 离床状态首尾保存")
    print("="*80)
    
    # 维护60秒滑动窗口
    window = deque(maxlen=60)
    
    # 场景定义: (秒数, 状态, 说明)
    test_scenarios = [
        # 在床状态
        *[(i, BedState.IN_BED, "在床") for i in range(20)],       # 0-19秒: 在床
        
        # 离床状态（重点测试区域）
        *[(i, BedState.OUT_BED, "离床") for i in range(20, 80)],  # 20-79秒: 离床（60秒）
        
        # 回到在床
        *[(i, BedState.IN_BED, "在床") for i in range(80, 100)],  # 80-99秒: 在床
        
        # 短暂离床
        *[(i, BedState.OUT_BED, "短暂离床") for i in range(100, 110)], # 100-109秒: 短暂离床（10秒）
        
        # 再次在床
        *[(i, BedState.IN_BED, "再次在床") for i in range(110, 130)], # 110-129秒: 在床
    ]
    
    stored_count = 0
    total_count = 0
    out_bed_stored_count = 0
    out_bed_total_count = 0
    
    print(f"\n{'秒数':<6} {'状态':<12} {'存储?':<6} {'原因':<50} {'说明':<20}")
    print("-"*100)
    
    for offset, state, desc in test_scenarios:
        timestamp = base_time + offset
        
        # 生成UART数据
        uart_data = generate_uart_data(timestamp, state, device_sn)
        
        # 添加到窗口
        window.append(uart_data)
        
        # 每秒处理一次（只判断最新1秒）
        should_store, reason = storage.process_uart_data_window(
            device_sn, 
            list(window)
        )
        
        total_count += 1
        if should_store:
            stored_count += 1
        
        # 统计离床状态
        if state == BedState.OUT_BED:
            out_bed_total_count += 1
            if should_store:
                out_bed_stored_count += 1
        
        # 显示关键时间点和状态变化
        if (offset % 20 == 0 or 
            offset in [20, 21, 79, 80, 100, 101, 109, 110] or  # 状态变化点
            should_store):
            stored_str = "✅ 是" if should_store else "⏭️  否"
            print(f"{offset:<6} {storage.get_state_name(state):<12} {stored_str:<6} {reason:<50} {desc:<20}")
    
    # 统计结果
    print("\n" + "="*80)
    print("统计结果")
    print("="*80)
    print(f"总数据点: {total_count}")
    print(f"总存储次数: {stored_count}")
    print(f"总存储比例: {stored_count/total_count*100:.2f}%")
    print()
    print(f"离床数据点: {out_bed_total_count}")
    print(f"离床存储次数: {out_bed_stored_count}")
    print(f"离床存储比例: {out_bed_stored_count/out_bed_total_count*100:.2f}%")
    
    # 验证离床状态首尾保存
    print("\n" + "="*80)
    print("离床状态首尾保存验证")
    print("="*80)
    
    print("✅ 预期结果:")
    print("   - 第一次离床(20-79秒): 只存储第20秒(开始)和第80秒(结束)")
    print("   - 第二次离床(100-109秒): 只存储第100秒(开始)和第110秒(结束)")
    print("   - 离床持续期间的所有中间数据点都不存储")
    
    # 设备统计
    stats = storage.get_device_stats(device_sn)
    print(f"\n📊 设备统计: {stats}")
    
    print("="*80)
    print("✅ 离床状态首尾保存测试完成")