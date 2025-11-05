#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time    : 2025/10/29 16:07
@Author  : weiyutao
@File    : sleep_analyze_config.py
"""

from typing import Dict, Any


class SleepAnalysisConfig:
    """睡眠分析配置类"""
    
    # 时间相关配置
    TIME_CONFIG = {
        'trend_interval': 300,  # 趋势图时间间隔（秒），5分钟
        'quality_interval': 3600,  # 质量评估时间间隔（秒），1小时
        'sampling_rate': 1,  # 数据采样率（秒）
    }
    
    # 睡眠状态映射
    STATE_MAPPING = {
        0: {'name': '在床', 'phase': 'light_sleep', 'color': '#87CEEB'},      # 浅睡眠
        1: {'name': '离床', 'phase': 'awake', 'color': '#FFB6C1'},           # 清醒
        2: {'name': '体动', 'phase': 'movement', 'color': '#FFA500'},        # 体动
        3: {'name': '弱呼吸', 'phase': 'deep_sleep', 'color': '#4169E1'},    # 深睡眠
        4: {'name': '重物', 'phase': 'awake', 'color': '#DC143C'},           # 清醒
        5: {'name': '打鼾', 'phase': 'light_sleep', 'color': '#98FB98'},     # 浅睡眠
    }
    
    # 生理指标正常范围
    PHYSIOLOGICAL_RANGES = {
        'heart_rate': {
            'normal': (60, 100),      # 正常心率范围
            'sleep': (50, 80),        # 睡眠时心率范围
            'nap': (65, 85),          # 午睡心率范围
        },
        'breath_rate': {
            'normal': (12, 20),       # 正常呼吸率范围
            'sleep': (10, 16),        # 睡眠时呼吸率范围
            'nap': (12, 20),          # 午睡呼吸率范围
        }
    }
    
    # 睡眠评分标准
    SCORING_STANDARDS = {
        'awake_duration': {
            'min': 0,         # 最小值（秒）
            'max': 1860,      # 最大值（秒，31分钟）
            'max_score': 20,  # 满分
            'reverse': True   # 数值越小越好
        },
        'sleep_efficiency': {
            'min': 0.8,       # 最小效率
            'max': 1.0,       # 最大效率
            'max_score': 15,  # 满分
            'reverse': False  # 数值越大越好
        },
        'sleep_duration_ratio': {
            'min': 0.2,       # 最小睡眠时长比例
            'max': 0.6,       # 最大睡眠时长比例
            'max_score': 15,  # 满分
            'reverse': False
        },
        'leave_bed_count': {
            'min': 0,         # 最小离床次数
            'max': 2,         # 最大可接受次数
            'max_score': 5,   # 满分
            'reverse': True
        },
        'sleep_latency': {
            'min': 0,         # 最小入睡时长（秒）
            'max': 1800,      # 最大可接受时长（30分钟）
            'max_score': 10,  # 满分
            'reverse': True
        },
        'movement_index': {
            'min': 1.25,      # 最小体动指数（次/小时）
            'max': 15,        # 最大可接受指数
            'max_score': 5,   # 满分
            'reverse': True
        },
        'breath_rate': {
            'min': 12,        # 最小呼吸率
            'max': 20,        # 最大呼吸率
            'max_score': 10,  # 满分
            'reverse': False
        },
        'heart_rate': {
            'min': 60,        # 最小心率
            'max': 100,       # 最大心率
            'max_score': 10,  # 满分
            'reverse': False
        },
        'breath_abnormal_index': {
            'min': 0,         # 最小异常指数
            'max': 5,         # 最大可接受指数
            'max_score': 5,   # 满分
            'reverse': True
        }
    }


# 异常值处理配置
class DataValidationConfig:
    """数据验证配置"""
    
    VALID_RANGES = {
        'heart_bpm': (30, 200),      # 心率有效范围
        'breath_bpm': (5, 40),       # 呼吸率有效范围
        'timestamp': (0, 2147483647), # 时间戳有效范围
        'state': (0, 5)              # 状态值有效范围
    }
    
    OUTLIER_DETECTION = {
        'heart_rate': {
            'method': 'iqr',         # 使用IQR方法检测异常值
            'multiplier': 1.5        # IQR倍数
        },
        'breath_rate': {
            'method': 'iqr',
            'multiplier': 1.5
        }
    }


# 导出配置
__all__ = [
    'SleepAnalysisConfig',
    'DataValidationConfig'
]