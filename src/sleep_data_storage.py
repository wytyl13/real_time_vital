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
from typing import Optional, List, Callable, Dict, Any
from collections import defaultdict
from enum import IntEnum
import asyncio


from base.consumer_tool_pool import ConsumerToolPool
from api.table.base.real_time_vital_data import RealTimeVitalData
from agent.provider.sql_provider import SqlProvider
from agent.base.base_tool import tool
from tools.utils import Utils

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
        print("="*80)
        print("睡眠数据存储管理器初始化完成（支持离床首尾保存）")
        print(f"正常状态最大存储间隔: {max_normal_interval}秒")
        print(f"异常状态(全部存储): {[self.get_state_name(s) for s in self.anomaly_states]}")
        print(f"首尾存储状态(只保存开始和结束): {[self.get_state_name(s) for s in self.edge_only_states]}")
        print("="*80)
    
    
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
        
        # 处理数据
        return self.process_time_window(device_sn, data_points)
    
    
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
        
        # 获取或创建设备状态
        if device_sn not in self.device_states:
            self.device_states[device_sn] = DeviceState()
        
        state = self.device_states[device_sn]
        
        # 判断是否需要存储
        should_store, reason = self._should_store(latest_data, state)
        
        
        # 新增：预警检测（在存储判断之后）
        if self.alert_enabled:
            self._check_and_handle_alerts(device_sn, latest_data, state.last_stored_state)
        
        
        
        if should_store:
            # 更新设备状态
            state.update(latest_data)
        else:
            state.last_stored_state = latest_data.state
        return should_store, reason, latest_data
    
    
    def _check_and_handle_alerts(self, device_sn: str, current_data: DataPoint, last_state: Optional[int]):
        """检查并处理预警"""
        current_state = current_data.state
        
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
                self.logger.info(f"{device_sn}: -------------------- 开始预警 {alert_type}")
                self._start_alert(device_sn, alert_type, current_data)
                
            elif not current_is_alert and last_was_alert:
                # 预警结束
                self.logger.info(f"{device_sn}: -------------------- 结束预警 {alert_type}")
                self._end_alert(device_sn, alert_type, current_data)


    def _start_alert(self, device_sn: str, alert_type: str, data: DataPoint) -> int:
        """开始预警"""
        # 实现预警开始逻辑
        self.logger.info(f"{device_sn}: -------------------- 开始预警")


    def _end_alert(self, device_sn: str, alert_type: str, data: DataPoint):
        """结束预警"""  
        # 实现预警结束逻辑
        self.logger.info(f"{device_sn}: -------------------- 结束预警")
    
    
    def _should_store(self, 
                     data: DataPoint, 
                     state: 'DeviceState') -> tuple[bool, str]:
        """
        判断是否应该存储数据
        
        规则:
        1. 首次数据 → 存储
        2. 状态变化 → 存储
        3. 异常状态(体动、弱呼吸) → 全部存储
        4. 首尾存储状态(离床) → 只在状态变化时存储，持续期间不存储
        5. 其他状态 → 按最大间隔存储
        """
        current_state = data.state
        is_anomaly = current_state in self.anomaly_states
        is_edge_only = current_state in self.edge_only_states
        
        # 规则1: 首次数据
        if state.last_stored_timestamp is None:
            return True, "首次数据"
        
        # 规则2: 状态变化（包括离床状态的开始和结束）
        if current_state != state.last_stored_state:
            if is_edge_only:
                return True, f"离床状态变化: {self.get_state_name(state.last_stored_state)} → {self.get_state_name(current_state)}"
            else:
                return True, f"状态变化: {self.get_state_name(state.last_stored_state)} → {self.get_state_name(current_state)}"
        
        # 规则3: 异常状态（全部存储）
        if is_anomaly:
            return True, f"异常状态({self.get_state_name(current_state)})"
        
        # 规则4: 首尾存储状态（离床状态持续期间不存储）
        if is_edge_only:
            return False, f"{self.get_state_name(current_state)}持续期间不存储"
        
        # 规则5: 其他状态（按间隔存储）
        time_gap = data.timestamp - state.last_stored_timestamp
        if time_gap >= self.max_normal_interval:
            return True, f"{self.get_state_name(current_state)}最大间隔({time_gap:.1f}秒)"
        
        return False, f"{self.get_state_name(current_state)}间隔不足({time_gap:.1f}秒)"
    
    
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
            "last_state": self.get_state_name(device_state.last_stored_state) if device_state.last_stored_state is not None else "未知"
        }



class DeviceState:
    """设备状态（轻量级）"""
    __slots__ = ['last_stored_timestamp', 'last_stored_state']
    
    def __init__(self):
        self.last_stored_timestamp: Optional[float] = None
        self.last_stored_state: Optional[int] = None
    
    def update(self, data: DataPoint):
        """更新状态"""
        self.last_stored_timestamp = data.timestamp
        self.last_stored_state = data.state


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
        uart_data = generate_uart_data(timestamp, state, device_id)
        
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