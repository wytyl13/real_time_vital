#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time    : 2025/10/29 16:06
@Author  : weiyutao
@File    : sleep_report.py
"""

import json
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional
from enum import IntEnum
from dataclasses import dataclass, asdict
import statistics


class BedState(IntEnum):
    """床状态枚举"""
    IN_BED = 0      # 在床
    OUT_BED = 1     # 离床
    MOVEMENT = 2    # 体动
    WEAK_BREATH = 3 # 弱呼吸
    HEAVY_OBJECT = 4 # 重物
    SNORING = 5     # 打鼾


@dataclass
class SleepDataPoint:
    """单个睡眠数据点"""
    id: int
    device_sn: str
    timestamp: int
    breath_bpm: float
    heart_bpm: int
    state: int
    breath_curve: str = ""
    heart_curve: str = ""
    create_time: str = ""


@dataclass
class SleepPhase:
    """睡眠阶段数据"""
    phase_type: str  # "deep_sleep", "light_sleep", "awake", "movement", "rem"
    start_time: int
    end_time: int
    duration: int  # 秒数


@dataclass
class SleepQualityScore:
    """睡眠评分详情"""
    awake_duration_score: float = 0.0      # 清醒时长评分 (20分)
    sleep_efficiency_score: float = 0.0    # 睡眠效率评分 (15分)
    sleep_duration_score: float = 0.0      # 睡眠时长评分 (15分)
    leave_bed_score: float = 0.0           # 离床次数评分 (5分)
    sleep_latency_score: float = 0.0       # 入睡时长评分 (10分)
    movement_index_score: float = 0.0      # 体动指数评分 (5分)
    breath_rate_score: float = 0.0         # 平均呼吸率评分 (10分)
    heart_rate_score: float = 0.0          # 平均心率评分 (10分)
    breath_abnormal_score: float = 0.0     # 呼吸异常指数评分 (5分)
    total_score: float = 0.0               # 总评分 (100分)


@dataclass
class SleepReport:
    """完整睡眠报告"""
    # 基础信息
    id: int
    device_sn: str
    device_type: Optional[str] = None
    creator: str = "system"
    updater: Optional[str] = None
    create_time: str = ""
    update_time: str = ""
    
    # 时间信息
    bed_time: str = ""                    # 上床时间
    sleep_start_time: str = ""            # 睡眠区间起始时间
    sleep_time: str = ""                  # 入睡时间
    sleep_end_time: str = ""              # 睡眠区间终止时间
    wake_time: str = ""                   # 醒来时间
    leave_bed_time: str = ""              # 离床时间
    
    # 时长统计
    total_duration: str = ""              # 统计总时长
    in_bed_duration: str = ""             # 在床时长
    out_bed_duration: str = ""            # 离床时长
    deep_sleep_duration: str = ""         # 深睡眠时长
    light_sleep_duration: str = ""        # 浅睡眠时长
    awake_duration: str = ""              # 清醒时长
    
    # 生理指标
    avg_breath_rate: float = 0.0          # 平均呼吸率
    avg_heart_rate: float = 0.0           # 平均心率
    heart_rate_variability: float = 0.0   # 心率变异性系数
    
    # 睡眠质量指标
    deep_sleep_ratio: float = 0.0         # 深睡眠比例
    light_sleep_ratio: float = 0.0        # 浅睡眠比例
    
    # 异常统计
    body_movement_count: int = 0          # 体动次数
    rapid_breathing_count: int = 0        # 呼吸急促次数
    apnea_count: int = 0                  # 呼吸暂停次数
    leave_bed_count: int = 0              # 离床次数
    
    # 健康报告
    health_report: str = ""               # 健康报告详情
    
    # 趋势数据
    heart_rate_trend: List[Dict] = None            # 心率趋势数据
    breath_rate_trend: List[Dict] = None           # 呼吸率趋势数据
    sleep_state_trend: List[Dict] = None           # 睡眠状态趋势数据
    sleep_quality_trend: List[Dict] = None         # 睡眠质量趋势数据
    
    # 评分详情
    sleep_score: SleepQualityScore = None          # 睡眠评分详情
    
    def __post_init__(self):
        if self.heart_rate_trend is None:
            self.heart_rate_trend = []
        if self.breath_rate_trend is None:
            self.breath_rate_trend = []
        if self.sleep_state_trend is None:
            self.sleep_state_trend = []
        if self.sleep_quality_trend is None:
            self.sleep_quality_trend = []
        if self.sleep_score is None:
            self.sleep_score = SleepQualityScore()


class SleepDataAnalyzer:
    """睡眠数据分析器 - 核心智能分析引擎"""
    
    def __init__(self):
        self.data_points: List[SleepDataPoint] = []
        self.sleep_phases: List[SleepPhase] = []
        
    def load_data(self, raw_data: List[Dict]) -> None:
        """加载原始睡眠数据"""
        self.data_points = []
        for item in raw_data:
            data_point = SleepDataPoint(
                id=item.get('id', 0),
                device_sn=item.get('device_sn', ''),
                timestamp=item.get('timestamp', 0),
                breath_bpm=item.get('breath_bpm', 0.0),
                heart_bpm=item.get('heart_bpm', 0),
                state=item.get('state', 0),
                breath_curve=item.get('breath_curve', ''),
                heart_curve=item.get('heart_curve', ''),
                create_time=item.get('create_time', '')
            )
            self.data_points.append(data_point)
        
        # 按时间戳排序
        self.data_points.sort(key=lambda x: x.timestamp)
    
    def analyze_sleep_phases(self) -> List[SleepPhase]:
        """基于生理数据分析睡眠阶段 - 智能睡眠分期算法"""
        if not self.data_points:
            return []
        
        # 首先对每个数据点进行睡眠阶段分类
        classified_points = []
        for point in self.data_points:
            sleep_stage = self._classify_sleep_stage(point)
            classified_points.append((point.timestamp, sleep_stage))
        
        # 然后进行平滑处理和阶段合并
        smoothed_stages = self._smooth_sleep_stages(classified_points)
        
        # 最后生成睡眠阶段列表
        phases = self._generate_phase_segments(smoothed_stages)
        
        self.sleep_phases = phases
        return phases
    
    def _classify_sleep_stage(self, point: SleepDataPoint) -> str:
        """基于生理数据分类单个数据点的睡眠阶段"""
        # 如果离床，直接判断为清醒
        if point.state == BedState.OUT_BED:
            return "awake"
        
        # 如果有重物干扰，判断为清醒
        if point.state == BedState.HEAVY_OBJECT:
            return "awake"
        
        # 基于心率和呼吸率进行睡眠阶段分类
        heart_rate = point.heart_bpm
        breath_rate = point.breath_bpm
        
        # 优先判断清醒状态（避免误分类）
        if self._is_awake(heart_rate, breath_rate, point):
            return "awake"
        
        # 然后判断深睡眠
        elif self._is_deep_sleep(heart_rate, breath_rate, point):
            return "deep_sleep"
        
        # 再判断REM睡眠  
        elif self._is_rem_sleep(heart_rate, breath_rate, point):
            return "rem_sleep"
        
        # 默认为浅睡眠
        else:
            return "light_sleep"
    
    def _is_deep_sleep(self, heart_rate: float, breath_rate: float, point: SleepDataPoint) -> bool:
        """判断是否为深睡眠 - 多权重评分算法"""
        # 深睡眠特征：
        # 1. 心率较低且稳定 (通常45-65 bpm)
        # 2. 呼吸率较慢且规律 (通常8-14 bpm)  
        # 3. 呼吸模式规律，振幅稳定
        # 4. 很少体动
        
        conditions = []
        weights = []
        
        # 心率条件 (权重: 30%)
        if 45 <= heart_rate <= 65:
            conditions.append(1.0)
        elif 65 < heart_rate <= 75:
            conditions.append(0.5)  # 部分满足
        else:
            conditions.append(0.0)
        weights.append(0.3)
            
        # 呼吸率条件 (权重: 25%)
        if 8 <= breath_rate <= 14:
            conditions.append(1.0)
        elif 14 < breath_rate <= 16:
            conditions.append(0.5)
        else:
            conditions.append(0.0)
        weights.append(0.25)
        
        # 呼吸模式分析 (权重: 25%)
        breath_pattern = self._analyze_breathing_pattern(point)
        if breath_pattern['regularity'] > 0.7:
            conditions.append(1.0)
        elif breath_pattern['regularity'] > 0.5:
            conditions.append(0.6)
        else:
            conditions.append(0.0)
        weights.append(0.25)
            
        # 状态条件 (权重: 20%)
        if point.state == BedState.WEAK_BREATH:
            conditions.append(1.0)
        elif point.state == BedState.IN_BED:
            conditions.append(0.7)
        elif point.state == BedState.SNORING:
            conditions.append(0.3)  # 打鼾通常不是深睡眠
        else:
            conditions.append(0.0)
        weights.append(0.2)
        
        # 加权评分
        weighted_score = sum(c * w for c, w in zip(conditions, weights))
        return weighted_score >= 0.6  # 60%以上认为是深睡眠
    
    def _is_rem_sleep(self, heart_rate: float, breath_rate: float, point: SleepDataPoint) -> bool:
        """判断是否为REM睡眠"""
        # REM睡眠特征：
        # 1. 心率变化较大，接近清醒水平 (65-85 bpm)
        # 2. 呼吸不规律，频率变化
        # 3. 可能有轻微体动
        # 4. 呼吸曲线变异性大
        
        conditions = []
        weights = []
        
        # 心率条件 (权重: 35%)
        if 65 <= heart_rate <= 85:
            conditions.append(1.0)
        elif 60 <= heart_rate < 65 or 85 < heart_rate <= 90:
            conditions.append(0.6)
        else:
            conditions.append(0.0)
        weights.append(0.35)
            
        # 呼吸率条件 (权重: 25%)
        if 14 <= breath_rate <= 20:
            conditions.append(1.0)
        elif 12 <= breath_rate < 14 or 20 < breath_rate <= 22:
            conditions.append(0.5)
        else:
            conditions.append(0.0)
        weights.append(0.25)
            
        # 呼吸不规律性 (权重: 25%)
        breath_pattern = self._analyze_breathing_pattern(point)
        if breath_pattern['regularity'] < 0.4:  # 不规律
            conditions.append(1.0)
        elif breath_pattern['regularity'] < 0.6:
            conditions.append(0.7)
        else:
            conditions.append(0.0)
        weights.append(0.25)
        
        # 状态条件 (权重: 15%)
        if point.state in [BedState.IN_BED, BedState.SNORING]:
            conditions.append(1.0)
        elif point.state == BedState.MOVEMENT:
            conditions.append(0.5)  # REM期可能有轻微体动
        else:
            conditions.append(0.0)
        weights.append(0.15)
            
        # 加权评分
        weighted_score = sum(c * w for c, w in zip(conditions, weights))
        return weighted_score >= 0.6
    
    def _is_awake(self, heart_rate: float, breath_rate: float, point: SleepDataPoint) -> bool:
        """判断是否为清醒状态"""
        # 强清醒指标：心率>85且呼吸率>20
        if heart_rate > 85 and breath_rate > 20:
            return True
        
        # 离床或重物状态直接判断为清醒
        if point.state in [BedState.OUT_BED, BedState.HEAVY_OBJECT]:
            return True
        
        # 体动状态下的清醒判断
        if point.state == BedState.MOVEMENT:
            if heart_rate > 75 or breath_rate > 18:
                return True
        
        # 综合评分判断
        conditions = []
        weights = []
        
        # 心率条件 (权重: 40%)
        if heart_rate > 85:
            conditions.append(1.0)
        elif heart_rate > 80:
            conditions.append(0.8)
        elif heart_rate > 75:
            conditions.append(0.5)
        else:
            conditions.append(0.0)
        weights.append(0.4)
            
        # 呼吸率条件 (权重: 40%)
        if breath_rate > 22:
            conditions.append(1.0)
        elif breath_rate > 20:
            conditions.append(0.8)
        elif breath_rate > 18:
            conditions.append(0.5)
        else:
            conditions.append(0.0)
        weights.append(0.4)
            
        # 状态条件 (权重: 20%)
        if point.state == BedState.MOVEMENT:
            conditions.append(0.7)
        else:
            conditions.append(0.0)
        weights.append(0.2)
            
        # 加权评分
        weighted_score = sum(c * w for c, w in zip(conditions, weights))
        return weighted_score >= 0.5
    
    def _smooth_sleep_stages(self, classified_points: List[Tuple[int, str]]) -> List[Tuple[int, str]]:
        """平滑睡眠阶段，避免频繁跳跃"""
        if len(classified_points) < 3:
            return classified_points
            
        smoothed = []
        window_size = 3  # 使用3个点的滑动窗口
        
        for i in range(len(classified_points)):
            timestamp, current_stage = classified_points[i]
            
            # 获取窗口内的阶段
            start_idx = max(0, i - window_size // 2)
            end_idx = min(len(classified_points), i + window_size // 2 + 1)
            
            window_stages = [point[1] for point in classified_points[start_idx:end_idx]]
            
            # 特殊处理：如果当前点是清醒状态，优先保持
            if current_stage == "awake":
                smoothed.append((timestamp, current_stage))
                continue
            
            # 使用众数平滑，但给当前点更高权重
            stage_counts = {}
            for stage in window_stages:
                stage_counts[stage] = stage_counts.get(stage, 0) + 1
            
            # 给当前阶段额外权重
            if current_stage in stage_counts:
                stage_counts[current_stage] += 0.5
            
            # 选择出现次数最多的阶段
            smoothed_stage = max(stage_counts.items(), key=lambda x: x[1])[0]
            smoothed.append((timestamp, smoothed_stage))
            
        return smoothed
    
    def _generate_phase_segments(self, smoothed_stages: List[Tuple[int, str]]) -> List[SleepPhase]:
        """生成连续的睡眠阶段段落"""
        if not smoothed_stages:
            return []
            
        phases = []
        current_stage = smoothed_stages[0][1]
        phase_start = smoothed_stages[0][0]
        
        for i in range(1, len(smoothed_stages)):
            timestamp, stage = smoothed_stages[i]
            
            if stage != current_stage:
                # 结束当前阶段
                phases.append(SleepPhase(
                    phase_type=current_stage,
                    start_time=phase_start,
                    end_time=timestamp,
                    duration=timestamp - phase_start
                ))
                
                # 开始新阶段
                current_stage = stage
                phase_start = timestamp
        
        # 添加最后一个阶段
        if smoothed_stages:
            last_timestamp = smoothed_stages[-1][0]
            phases.append(SleepPhase(
                phase_type=current_stage,
                start_time=phase_start,
                end_time=last_timestamp,
                duration=last_timestamp - phase_start
            ))
        
        return phases
    
    def _analyze_breathing_pattern(self, point: SleepDataPoint) -> Dict:
        """分析呼吸模式"""
        try:
            if not point.breath_curve:
                return {'regularity': 0.5, 'amplitude': 0.5}
            
            # 解析呼吸曲线数据
            curve_data = json.loads(point.breath_curve.replace("'", '"'))
            if not curve_data or len(curve_data) < 10:
                return {'regularity': 0.5, 'amplitude': 0.5}
            
            # 计算呼吸规律性（使用标准差）
            curve_std = statistics.stdev(curve_data)
            curve_mean = statistics.mean([abs(x) for x in curve_data])
            
            # 规律性评分 (标准差越小越规律)
            regularity = max(0, 1 - curve_std / max(curve_mean, 1))
            
            # 振幅评分
            amplitude = min(1, curve_mean / 10000)  # 归一化振幅
            
            return {
                'regularity': regularity,
                'amplitude': amplitude
            }
        except:
            return {'regularity': 0.5, 'amplitude': 0.5}
    
    def generate_heart_rate_trend(self) -> List[Dict]:
        """生成心率趋势数据"""
        if not self.data_points:
            return []
        
        # 按时间间隔采样数据点（例如每5分钟一个点）
        interval = 300  # 5分钟
        trend_data = []
        
        start_time = self.data_points[0].timestamp
        end_time = self.data_points[-1].timestamp
        
        current_time = start_time
        while current_time <= end_time:
            # 找到时间窗口内的数据点
            window_points = [
                p for p in self.data_points 
                if current_time <= p.timestamp < current_time + interval
            ]
            
            if window_points:
                avg_heart_rate = statistics.mean([p.heart_bpm for p in window_points])
                trend_data.append({
                    'timestamp': current_time,
                    'time_str': datetime.fromtimestamp(current_time).strftime('%H:%M'),
                    'value': round(avg_heart_rate, 1)
                })
            
            current_time += interval
        
        return trend_data
    
    def generate_breath_rate_trend(self) -> List[Dict]:
        """生成呼吸率趋势数据"""
        if not self.data_points:
            return []
        
        interval = 300  # 5分钟
        trend_data = []
        
        start_time = self.data_points[0].timestamp
        end_time = self.data_points[-1].timestamp
        
        current_time = start_time
        while current_time <= end_time:
            window_points = [
                p for p in self.data_points 
                if current_time <= p.timestamp < current_time + interval
            ]
            
            if window_points:
                avg_breath_rate = statistics.mean([p.breath_bpm for p in window_points])
                trend_data.append({
                    'timestamp': current_time,
                    'time_str': datetime.fromtimestamp(current_time).strftime('%H:%M'),
                    'value': round(avg_breath_rate, 1)
                })
            
            current_time += interval
        
        return trend_data
    
    def generate_sleep_state_trend(self) -> List[Dict]:
        """生成睡眠状态趋势数据（基于睡眠阶段）"""
        if not self.sleep_phases:
            self.analyze_sleep_phases()
        
        trend_data = []
        for phase in self.sleep_phases:
            start_dt = datetime.fromtimestamp(phase.start_time)
            end_dt = datetime.fromtimestamp(phase.end_time)
            
            trend_data.append({
                'phase_type': phase.phase_type,
                'start_time': phase.start_time,
                'end_time': phase.end_time,
                'start_time_str': start_dt.strftime('%H:%M'),
                'end_time_str': end_dt.strftime('%H:%M'),
                'duration': phase.duration,
                'duration_str': self._format_duration(phase.duration)
            })
        
        return trend_data
    
    def _format_duration(self, seconds: int) -> str:
        """格式化时长为字符串"""
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        seconds = seconds % 60
        return f"{hours}小时{minutes}分{seconds}秒"


    def generate_sleep_quality_trend(self) -> List[Dict]:
        """生成睡眠质量趋势数据（按小时统计）"""
        if not self.data_points:
            return []
        
        # 按小时间隔统计睡眠质量
        interval = 3600  # 1小时
        trend_data = []
        
        start_time = self.data_points[0].timestamp
        end_time = self.data_points[-1].timestamp
        
        current_time = start_time
        while current_time <= end_time:
            # 获取该小时内的数据点
            window_points = [
                p for p in self.data_points 
                if current_time <= p.timestamp < current_time + interval
            ]
            
            if window_points:
                # 计算该时段的质量指标
                # 1. 心率稳定性（标准差越小越好）
                heart_rates = [p.heart_bpm for p in window_points if p.heart_bpm > 0]
                heart_stability = 0
                if len(heart_rates) > 1:
                    heart_std = statistics.stdev(heart_rates)
                    heart_stability = max(0, 1 - heart_std / 20)  # 归一化
                
                # 2. 呼吸规律性
                breath_rates = [p.breath_bpm for p in window_points if p.breath_bpm > 0]
                breath_stability = 0
                if len(breath_rates) > 1:
                    breath_std = statistics.stdev(breath_rates)
                    breath_stability = max(0, 1 - breath_std / 5)  # 归一化
                
                # 3. 状态稳定性（体动越少越好）
                movement_count = sum(1 for p in window_points if p.state == 2)
                movement_score = max(0, 1 - movement_count / len(window_points))
                
                # 综合质量评分（0-100）
                quality_score = (heart_stability * 0.3 + 
                            breath_stability * 0.3 + 
                            movement_score * 0.4) * 100
                
                trend_data.append({
                    'timestamp': current_time,
                    'time_str': datetime.fromtimestamp(current_time).strftime('%H:%M'),
                    'quality_score': round(quality_score, 1),
                    'heart_stability': round(heart_stability, 2),
                    'breath_stability': round(breath_stability, 2),
                    'movement_score': round(movement_score, 2)
                })
            
            current_time += interval
        
        return trend_data

class SleepScoreCalculator:
    """睡眠评分计算器 - 100分制综合评分系统"""
    
    @staticmethod
    def calculate_score(stats: Dict) -> SleepQualityScore:
        """计算睡眠质量评分"""
        score = SleepQualityScore()
        
        total_duration = stats.get('total_duration', 0)
        state_durations = stats.get('state_durations', {})
        
        # 1. 清醒时长评分 (0-1860秒，满分20分)
        awake_duration = state_durations.get('awake', 0)
        score.awake_duration_score = SleepScoreCalculator._calculate_range_score(
            awake_duration, 0, 1860, 20, reverse=True
        )
        
        # 2. 睡眠效率评分 (0.8-1.0，满分15分)
        sleep_duration = total_duration - awake_duration
        sleep_efficiency = sleep_duration / total_duration if total_duration > 0 else 0
        score.sleep_efficiency_score = SleepScoreCalculator._calculate_range_score(
            sleep_efficiency, 0.8, 1.0, 15
        )
        
        # 3. 睡眠时长评分 (按总时长的0.2-0.6比例，满分15分)
        sleep_duration_ratio = sleep_duration / total_duration if total_duration > 0 else 0
        score.sleep_duration_score = SleepScoreCalculator._calculate_range_score(
            sleep_duration_ratio, 0.2, 0.6, 15
        )
        
        # 4. 离床次数评分 (0-2次，满分5分)
        leave_bed_count = stats.get('out_bed_count', 0)
        score.leave_bed_score = SleepScoreCalculator._calculate_range_score(
            leave_bed_count, 0, 2, 5, reverse=True
        )
        
        # 5. 入睡时长评分 (0-1800秒，满分10分)
        sleep_latency = total_duration * 0.1  # 简化假设
        score.sleep_latency_score = SleepScoreCalculator._calculate_range_score(
            sleep_latency, 0, 1800, 10, reverse=True
        )
        
        # 6. 体动指数评分 (1.25-15，满分5分)
        movement_index = stats.get('movement_count', 0) / (total_duration / 3600) if total_duration > 0 else 0
        score.movement_index_score = SleepScoreCalculator._calculate_range_score(
            movement_index, 1.25, 15, 5, reverse=True
        )
        
        # 7. 平均呼吸率评分 (12-20，满分10分)
        avg_breath_rate = stats.get('avg_breath_rate', 0)
        score.breath_rate_score = SleepScoreCalculator._calculate_range_score(
            avg_breath_rate, 12, 20, 10
        )
        
        # 8. 平均心率评分 (60-100，满分10分)
        avg_heart_rate = stats.get('avg_heart_rate', 0)
        score.heart_rate_score = SleepScoreCalculator._calculate_range_score(
            avg_heart_rate, 60, 100, 10
        )
        
        # 9. 呼吸异常指数评分 (0-5，满分5分)
        breath_abnormal_index = stats.get('weak_breath_count', 0) / (total_duration / 3600) if total_duration > 0 else 0
        score.breath_abnormal_score = SleepScoreCalculator._calculate_range_score(
            breath_abnormal_index, 0, 5, 5, reverse=True
        )
        
        # 计算总分
        score.total_score = (
            score.awake_duration_score +
            score.sleep_efficiency_score +
            score.sleep_duration_score +
            score.leave_bed_score +
            score.sleep_latency_score +
            score.movement_index_score +
            score.breath_rate_score +
            score.heart_rate_score +
            score.breath_abnormal_score
        )
        
        return score
    
    @staticmethod
    def _calculate_range_score(value: float, min_val: float, max_val: float, 
                              max_score: float, reverse: bool = False) -> float:
        """计算范围评分"""
        if value < min_val:
            return 0.0 if not reverse else max_score
        elif value > max_val:
            return max_score if not reverse else 0.0
        else:
            ratio = (value - min_val) / (max_val - min_val)
            if reverse:
                ratio = 1 - ratio
            return ratio * max_score


class SleepReportGenerator:
    """睡眠报告生成器 - 完整报告生成系统"""
    
    def __init__(self):
        self.analyzer = SleepDataAnalyzer()
        self.score_calculator = SleepScoreCalculator()
    
    def generate_report(self, raw_data: List[Dict], report_id: int = 1, 
                       device_sn: str = "") -> SleepReport:
        """生成完整的睡眠报告"""
        # 加载和分析数据
        self.analyzer.load_data(raw_data)
        self.analyzer.analyze_sleep_phases()
        
        # 计算统计指标
        stats = self.analyzer.calculate_sleep_statistics()
        
        # 创建报告对象
        report = SleepReport(id=report_id, device_sn=device_sn)
        
        # 填充各项数据...
        # (此处省略具体实现细节，与之前相同)
        
        return report


# 导出类
__all__ = [
    'SleepDataAnalyzer',
    'SleepReportGenerator', 
    'SleepReport',
    'SleepQualityScore',
    'SleepPhase',
    'BedState'
]