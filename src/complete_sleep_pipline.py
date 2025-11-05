#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time    : 2025/10/29 18:52
@Author  : weiyutao
@File    : complete_sleep_pipline.py
"""


#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time    : 2025/10/29 16:08
@Author  : weiyutao
@File    : complete_sleep_pipeline.py
"""

import json
import statistics
from datetime import datetime
from typing import Dict, List, Any
from .data_processor import DataProcessor
from .sleep_report import SleepDataAnalyzer, SleepReportGenerator, SleepReport


def complete_sleep_analysis_pipeline(raw_data: List[Dict], device_sn: str, report_id: int) -> Dict[str, Any]:
    """完整的睡眠分析流水线 - 核心处理流程"""
    
    # ============ 第一步：数据预处理 ============
    print("🔧 第一步：数据清洗和验证")
    processor = DataProcessor()
    cleaned_data = processor.clean_data(raw_data)
    
    if not cleaned_data:
        return {"error": "数据清洗后为空"}
    
    # ============ 第二步：睡眠分期分析 ============
    print("🧠 第二步：基于生理数据进行睡眠分期")
    analyzer = SleepDataAnalyzer()
    analyzer.load_data(cleaned_data)
    
    # 核心：智能睡眠阶段分析
    sleep_phases = analyzer.analyze_sleep_phases()
    
    # ============ 第三步：状态增强 ============
    print("✨ 第三步：用睡眠阶段替换在床状态")
    enhanced_data = replace_in_bed_with_sleep_stages(cleaned_data, sleep_phases)
    
    # ============ 第四步：指标计算（基于睡眠分期结果）============
    print("📊 第四步：基于睡眠分期计算各项指标")
    statistics_data = calculate_enhanced_statistics(enhanced_data, sleep_phases, cleaned_data)
    
    # ============ 第五步：报告生成 ============
    print("📋 第五步：生成睡眠报告")
    sleep_report = generate_enhanced_report(statistics_data, sleep_phases, analyzer, device_sn, report_id)
    
    # ============ 第六步：甘特图数据生成 ============
    print("🎨 第六步：生成甘特图数据")
    gantt_data = preprocess_for_flutter_gantt(enhanced_data)
    
    # 绘制甘特图
    
    
    # 绘制心率趋势
    
    # 绘制呼吸率趋势
    
    # ============ 返回完整结果 ============
    return {
        "sleep_report": sleep_report,
        "gantt_data": gantt_data,
        "sleep_phases": sleep_phases,
        "statistics": statistics_data,
        "data_quality": processor.analyze_data_quality(cleaned_data)
    }


def replace_in_bed_with_sleep_stages(raw_data: List[Dict], sleep_phases: List) -> List[Dict]:
    """用睡眠阶段替换在床状态 - 智能状态增强"""
    enhanced_data = []
    
    # 创建时间点到睡眠阶段的映射
    phase_map = create_phase_time_mapping(sleep_phases)
    
    for point in raw_data:
        new_point = point.copy()
        
        if point['state'] == 0:  # 在床状态需要替换
            sleep_stage = phase_map.get(point['timestamp'], 'light_sleep')
            new_point['state'] = map_sleep_stage_to_state(sleep_stage)
            new_point['original_state'] = 0
            new_point['sleep_stage'] = sleep_stage
            new_point['state_name'] = get_sleep_stage_name(sleep_stage)
        else:
            # 非在床状态保持原样
            new_point['original_state'] = point['state']
            new_point['sleep_stage'] = 'awake' if point['state'] == 1 else 'movement'
            new_point['state_name'] = get_original_state_name(point['state'])
        
        enhanced_data.append(new_point)
    
    return enhanced_data


def create_phase_time_mapping(sleep_phases: List) -> Dict[int, str]:
    """创建时间点到睡眠阶段的映射"""
    phase_map = {}
    
    for phase in sleep_phases:
        # 将浮点时间戳转换为整数
        start_time = int(phase.start_time)
        end_time = int(phase.end_time)
        
        for timestamp in range(start_time, end_time + 1):
            phase_map[timestamp] = phase.phase_type
    
    return phase_map


def map_sleep_stage_to_state(sleep_stage: str) -> int:
    """睡眠阶段到状态码映射"""
    return {
        'deep_sleep': 10,
        'light_sleep': 11, 
        'rem_sleep': 12,
        'awake': 13
    }.get(sleep_stage, 11)


def get_sleep_stage_name(sleep_stage: str) -> str:
    """获取睡眠阶段名称"""
    return {
        'deep_sleep': '深睡眠',
        'light_sleep': '浅睡眠',
        'rem_sleep': 'REM睡眠',
        'awake': '清醒'
    }.get(sleep_stage, '浅睡眠')


def get_original_state_name(state: int) -> str:
    """获取原始状态名称"""
    return {
        1: "离床",
        2: "体动",
        3: "弱呼吸",
        4: "重物",
        5: "打鼾"
    }.get(state, "未知")


def calculate_enhanced_statistics(enhanced_data: List[Dict], sleep_phases: List, original_data: List[Dict]) -> Dict[str, Any]:
    """基于睡眠分期计算增强统计指标"""
    
    # ========== 基础时间统计 ==========
    start_time = original_data[0]['timestamp']
    end_time = original_data[-1]['timestamp']
    total_duration = end_time - start_time
    
    # ========== 睡眠阶段时长统计 ==========
    phase_durations = {}
    for phase in sleep_phases:
        phase_type = phase.phase_type
        if phase_type not in phase_durations:
            phase_durations[phase_type] = 0
        phase_durations[phase_type] += phase.duration
    
    # ========== 生理指标统计（基于原始数据）==========
    valid_points = [p for p in original_data if p.get('heart_bpm', 0) > 0 and p.get('breath_bpm', 0) > 0]
    
    # 整体生理指标
    overall_stats = {
        'avg_heart_rate': statistics.mean([p['heart_bpm'] for p in valid_points]) if valid_points else 0,
        'avg_breath_rate': statistics.mean([p['breath_bpm'] for p in valid_points]) if valid_points else 0,
        'heart_rate_variability': calculate_hrv([p['heart_bpm'] for p in valid_points]),
    }
    
    # 分阶段生理指标
    phase_physiological_stats = calculate_phase_physiological_stats(original_data, sleep_phases)
    
    # ========== 异常事件统计 ==========
    anomaly_stats = calculate_anomaly_statistics(original_data, enhanced_data)
    
    # ========== 睡眠质量指标 ==========
    quality_metrics = calculate_quality_metrics(phase_durations, total_duration, anomaly_stats)
    
    return {
        'basic_info': {
            'start_timestamp': start_time,
            'end_timestamp': end_time,
            'total_duration': total_duration
        },
        'phase_durations': phase_durations,
        'overall_physiological': overall_stats,
        'phase_physiological': phase_physiological_stats,
        'anomaly_statistics': anomaly_stats,
        'quality_metrics': quality_metrics
    }


def calculate_hrv(heart_rates: List[float]) -> float:
    """计算心率变异性"""
    if len(heart_rates) < 2:
        return 0.0
    
    # 计算相邻心率差值的标准差
    rr_intervals = []
    for i in range(1, len(heart_rates)):
        # 将心率转换为RR间期 (60/心率)
        rr1 = 60 / heart_rates[i-1] if heart_rates[i-1] > 0 else 0
        rr2 = 60 / heart_rates[i] if heart_rates[i] > 0 else 0
        if rr1 > 0 and rr2 > 0:
            rr_intervals.append(abs(rr2 - rr1))
    
    if len(rr_intervals) < 2:
        return 0.0
    
    # RMSSD (Root Mean Square of Successive Differences)
    mean_square = statistics.mean([interval ** 2 for interval in rr_intervals])
    return mean_square ** 0.5


def calculate_phase_physiological_stats(original_data: List[Dict], sleep_phases: List) -> Dict[str, Any]:
    """计算各睡眠阶段的生理指标"""
    phase_stats = {}
    
    for phase in sleep_phases:
        # 获取该阶段内的原始数据点
        phase_points = [
            p for p in original_data 
            if phase.start_time <= p['timestamp'] < phase.end_time
            and p.get('heart_bpm', 0) > 0 and p.get('breath_bpm', 0) > 0
        ]
        
        if phase_points:
            phase_stats[phase.phase_type] = {
                'avg_heart_rate': statistics.mean([p['heart_bpm'] for p in phase_points]),
                'avg_breath_rate': statistics.mean([p['breath_bpm'] for p in phase_points]),
                'heart_rate_range': (min(p['heart_bpm'] for p in phase_points), 
                                   max(p['heart_bpm'] for p in phase_points)),
                'breath_rate_range': (min(p['breath_bpm'] for p in phase_points),
                                    max(p['breath_bpm'] for p in phase_points)),
                'data_points': len(phase_points)
            }
    
    return phase_stats


def calculate_anomaly_statistics(original_data: List[Dict], enhanced_data: List[Dict]) -> Dict[str, Any]:
    """计算异常事件统计"""
    return {
        # 基于原始状态的异常
        'movement_episodes': count_movement_episodes(original_data),
        'out_bed_episodes': count_out_bed_episodes(original_data),
        'weak_breath_count': sum(1 for p in original_data if p.get('state') == 3),
        'snoring_episodes': count_snoring_episodes(original_data),
        
        # 基于生理指标的异常
        'heart_rate_anomalies': detect_heart_rate_anomalies(original_data),
        'breath_rate_anomalies': detect_breath_rate_anomalies(original_data),
        
        # 睡眠结构异常
        'sleep_fragmentation': calculate_sleep_fragmentation(enhanced_data),
        'phase_transitions': count_phase_transitions(enhanced_data)
    }


def count_movement_episodes(data: List[Dict]) -> int:
    """统计体动次数"""
    movement_count = 0
    in_movement = False
    
    for point in data:
        if point.get('state') == 2:  # 体动状态
            if not in_movement:
                movement_count += 1
                in_movement = True
        else:
            in_movement = False
            
    return movement_count


def count_out_bed_episodes(data: List[Dict]) -> int:
    """统计离床次数"""
    out_bed_count = 0
    in_out_bed = False
    
    for point in data:
        if point.get('state') == 1:  # 离床状态
            if not in_out_bed:
                out_bed_count += 1
                in_out_bed = True
        else:
            in_out_bed = False
            
    return out_bed_count


def count_snoring_episodes(data: List[Dict]) -> int:
    """统计打鼾次数"""
    snoring_count = 0
    in_snoring = False
    
    for point in data:
        if point.get('state') == 5:  # 打鼾状态
            if not in_snoring:
                snoring_count += 1
                in_snoring = True
        else:
            in_snoring = False
            
    return snoring_count


def detect_heart_rate_anomalies(data: List[Dict]) -> int:
    """检测心率异常"""
    anomaly_count = 0
    for point in data:
        heart_rate = point.get('heart_bpm', 0)
        if heart_rate > 0 and (heart_rate < 40 or heart_rate > 120):
            anomaly_count += 1
    return anomaly_count


def detect_breath_rate_anomalies(data: List[Dict]) -> int:
    """检测呼吸率异常"""
    anomaly_count = 0
    for point in data:
        breath_rate = point.get('breath_bpm', 0)
        if breath_rate > 0 and (breath_rate < 8 or breath_rate > 25):
            anomaly_count += 1
    return anomaly_count


def calculate_sleep_fragmentation(data: List[Dict]) -> float:
    """计算睡眠碎片化指数"""
    if not data:
        return 0.0
    
    # 统计状态转换次数
    transitions = 0
    for i in range(1, len(data)):
        if data[i].get('state') != data[i-1].get('state'):
            transitions += 1
    
    # 归一化为每小时转换次数
    total_duration = data[-1]['timestamp'] - data[0]['timestamp']
    return transitions / (total_duration / 3600) if total_duration > 0 else 0


def count_phase_transitions(data: List[Dict]) -> int:
    """统计阶段转换次数"""
    transitions = 0
    for i in range(1, len(data)):
        if data[i].get('sleep_stage') != data[i-1].get('sleep_stage'):
            transitions += 1
    return transitions


def calculate_quality_metrics(phase_durations: Dict, total_duration: int, anomaly_stats: Dict) -> Dict[str, Any]:
    """计算睡眠质量指标"""
    sleep_duration = phase_durations.get('deep_sleep', 0) + phase_durations.get('light_sleep', 0) + phase_durations.get('rem_sleep', 0)
    
    return {
        'sleep_efficiency': sleep_duration / total_duration if total_duration > 0 else 0,
        'deep_sleep_percentage': phase_durations.get('deep_sleep', 0) / total_duration if total_duration > 0 else 0,
        'rem_percentage': phase_durations.get('rem_sleep', 0) / total_duration if total_duration > 0 else 0,
        'awake_percentage': phase_durations.get('awake', 0) / total_duration if total_duration > 0 else 0,
        'movement_index': anomaly_stats.get('movement_episodes', 0) / (total_duration / 3600) if total_duration > 0 else 0
    }


def generate_enhanced_report(statistics: Dict, sleep_phases: List, analyzer: SleepDataAnalyzer, 
                           device_sn: str, report_id: int) -> SleepReport:
    """生成增强的睡眠报告"""
    
    # 创建报告对象
    report = SleepReport(id=report_id, device_sn=device_sn)
    
    # ========== 基础信息填充 ==========
    basic_info = statistics['basic_info']
    report.bed_time = format_timestamp(basic_info['start_timestamp'])
    report.leave_bed_time = format_timestamp(basic_info['end_timestamp'])
    report.total_duration = format_duration(basic_info['total_duration'])
    
    # ========== 睡眠阶段时长填充 ==========
    phase_durations = statistics['phase_durations']
    report.deep_sleep_duration = format_duration(phase_durations.get('deep_sleep', 0))
    report.light_sleep_duration = format_duration(phase_durations.get('light_sleep', 0))
    report.awake_duration = format_duration(phase_durations.get('awake', 0))
    
    # 计算睡眠比例
    total_duration = basic_info['total_duration']
    if total_duration > 0:
        report.deep_sleep_ratio = phase_durations.get('deep_sleep', 0) / total_duration
        report.light_sleep_ratio = phase_durations.get('light_sleep', 0) / total_duration
    
    # ========== 生理指标填充 ==========
    physio = statistics['overall_physiological']
    report.avg_heart_rate = round(physio['avg_heart_rate'])
    report.avg_breath_rate = round(physio['avg_breath_rate'], 1)
    report.heart_rate_variability = round(physio['heart_rate_variability'], 4)
    
    # ========== 异常统计填充 ==========
    anomalies = statistics['anomaly_statistics']
    report.body_movement_count = anomalies['movement_episodes']
    report.leave_bed_count = anomalies['out_bed_episodes']
    report.rapid_breathing_count = anomalies['weak_breath_count']
    
    # ========== 生成趋势数据 ==========
    report.heart_rate_trend = analyzer.generate_heart_rate_trend()
    report.breath_rate_trend = analyzer.generate_breath_rate_trend()
    report.sleep_state_trend = convert_phases_to_trend(sleep_phases)
    report.sleep_quality_trend = analyzer.generate_sleep_quality_trend()
    
    # ========== 计算睡眠评分 ==========
    report.sleep_score = calculate_enhanced_sleep_score(statistics)
    
    # ========== 生成健康报告 ==========
    report.health_report = generate_enhanced_health_report(report, statistics)
    
    # 设置时间戳
    now = datetime.now().isoformat()
    report.create_time = now
    report.update_time = now
    
    return report


def format_timestamp(timestamp: int) -> str:
    """格式化时间戳"""
    return datetime.fromtimestamp(timestamp).strftime('%Y-%m-%dT%H:%M:%S')


def format_duration(seconds: int) -> str:
    """格式化时长"""
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    seconds = seconds % 60
    return f"{hours}小时{minutes}分{seconds}秒"


def convert_phases_to_trend(sleep_phases: List) -> List[Dict]:
    """将睡眠阶段转换为趋势数据"""
    trend_data = []
    for phase in sleep_phases:
        start_dt = datetime.fromtimestamp(phase.start_time)
        end_dt = datetime.fromtimestamp(phase.end_time)
        
        trend_data.append({
            'phase_type': phase.phase_type,
            'start_time': phase.start_time,
            'end_time': phase.end_time,
            'start_time_str': start_dt.strftime('%H:%M'),
            'end_time_str': end_dt.strftime('%H:%M'),
            'duration': phase.duration,
            'duration_str': format_duration(phase.duration)
        })
    
    return trend_data


def calculate_enhanced_sleep_score(statistics: Dict) -> Dict:
    """计算增强的睡眠评分"""
    from .sleep_report import SleepScoreCalculator
    
    # 转换统计数据格式以匹配评分器期望的格式
    stats_for_score = {
        'total_duration': statistics['basic_info']['total_duration'],
        'state_durations': statistics['phase_durations'],
        'avg_heart_rate': statistics['overall_physiological']['avg_heart_rate'],
        'avg_breath_rate': statistics['overall_physiological']['avg_breath_rate'],
        'heart_rate_variability': statistics['overall_physiological']['heart_rate_variability'],
        'movement_count': statistics['anomaly_statistics']['movement_episodes'],
        'weak_breath_count': statistics['anomaly_statistics']['weak_breath_count'],
        'out_bed_count': statistics['anomaly_statistics']['out_bed_episodes']
    }
    
    return SleepScoreCalculator.calculate_score(stats_for_score)


def generate_enhanced_health_report(report: SleepReport, statistics: Dict) -> str:
    """生成增强的健康报告"""
    total_score = report.sleep_score.total_score
    
    if total_score >= 80:
        quality_level = "优秀"
    elif total_score >= 60:
        quality_level = "良好"
    elif total_score >= 40:
        quality_level = "一般"
    else:
        quality_level = "较差"
    
    report_text = f"""### 睡眠质量评估
本次睡眠质量评级为**{quality_level}**，总评分为{total_score:.1f}分。

### 睡眠结构分析
- **深睡眠时长**: {report.deep_sleep_duration}，占比{report.deep_sleep_ratio:.1%}
- **浅睡眠时长**: {report.light_sleep_duration}，占比{report.light_sleep_ratio:.1%}
- **清醒时长**: {report.awake_duration}

### 生理指标分析
- **平均心率**: {report.avg_heart_rate}次/分钟
- **平均呼吸率**: {report.avg_breath_rate}次/分钟
- **心率变异性**: {report.heart_rate_variability:.4f}

### 行为表现分析
- **体动次数**: {report.body_movement_count}次
- **呼吸异常次数**: {report.rapid_breathing_count}次
- **离床次数**: {report.leave_bed_count}次

### 综合建议
根据本次睡眠数据分析，建议关注睡眠环境优化和作息规律调整。"""
    
    return report_text


def preprocess_for_flutter_gantt(enhanced_data: List[Dict]) -> Dict[str, Any]:
    """为Flutter甘特图预处理数据"""
    if not enhanced_data:
        return {"segments": []}
    
    sorted_data = sorted(enhanced_data, key=lambda x: x['timestamp'])
    segments = []
    
    for i in range(len(sorted_data) - 1):
        current = sorted_data[i]
        next_point = sorted_data[i + 1]
        
        segments.append({
            "start_timestamp": current['timestamp'],
            "end_timestamp": next_point['timestamp'], 
            "duration": next_point['timestamp'] - current['timestamp'],
            "state": current.get('state', 0),
            "state_name": current.get('state_name', get_original_state_name(current.get('state', 0))),
            "sleep_stage": current.get('sleep_stage', 'light_sleep')
        })
    
    return {
        "segments": segments,
        "device_sn": sorted_data[0].get('device_sn', '') if sorted_data else '',
        "total_segments": len(segments)
    }


def get_enhanced_state_config() -> Dict[int, Dict[str, str]]:
    """获取增强的状态配置"""
    return {
        # 原始状态
        1: {"name": "离床", "color": "#FFB6C1"},
        2: {"name": "体动", "color": "#FFA500"}, 
        3: {"name": "弱呼吸", "color": "#FF6347"},
        4: {"name": "重物", "color": "#8B4513"},
        5: {"name": "打鼾", "color": "#32CD32"},
        
        # 睡眠分期状态
        10: {"name": "深睡眠", "color": "#4169E1"},
        11: {"name": "浅睡眠", "color": "#87CEEB"},
        12: {"name": "REM睡眠", "color": "#9370DB"},
        13: {"name": "清醒", "color": "#FFB6C1"}
    }


# 导出函数
__all__ = [
    'complete_sleep_analysis_pipeline',
    'replace_in_bed_with_sleep_stages',
    'calculate_enhanced_statistics',
    'generate_enhanced_report',
    'preprocess_for_flutter_gantt',
    'get_enhanced_state_config'
]