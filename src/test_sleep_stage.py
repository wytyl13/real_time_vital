#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time    : 2025/10/29 16:09
@Author  : weiyutao
@File    : test_sleep_stage.py
"""
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime, timezone, timedelta
import numpy as np
import matplotlib.font_manager as fm
import matplotlib.patches as patches
import platform

import json
from datetime import datetime
from src.sleep_report import SleepReportGenerator
from src.data_processor import DataProcessor
from tools.utils import Utils


utils = Utils()

def setup_chinese_font():
    """设置中文字体"""
    plt.rcParams['font.sans-serif'] = ['WenQuanYi Zen Hei', 'Microsoft YaHei', 'DejaVu Sans']
    plt.rcParams['axes.unicode_minus'] = False
    plt.rcParams['figure.figsize'] = [16, 6]


def plot_gantt_from_processed_data(gantt_data):
    """绘制预处理后的甘特图数据"""
    setup_chinese_font()
    
    if not gantt_data or not gantt_data.get('segments'):
        print("❌ 没有数据可绘制")
        return
    
    segments = gantt_data['segments']
    
    # 状态颜色配置
    state_colors = {
        0: "#87CEEB",  # 在床
        1: "#FFB6C1",  # 离床
        2: "#FFA500",  # 体动
        3: "#4169E1",  # 深睡眠
        4: "#8B4513",  # 重物
        5: "#32CD32"   # 打鼾
    }
    
    # 创建图表
    fig, ax = plt.subplots(figsize=(16, 4))
    
    # 绘制甘特图条
    y_center = 0
    bar_height = 0.6
    
    for segment in segments:
        start_time = datetime.fromtimestamp(segment['start_timestamp'])
        end_time = datetime.fromtimestamp(segment['end_timestamp'])
        duration = end_time - start_time
        
        state = segment['state']
        color = state_colors.get(state, "#CCCCCC")
        
        # 绘制矩形条
        rect = patches.Rectangle(
            (start_time, y_center - bar_height/2),
            duration,
            bar_height,
            linewidth=0,
            facecolor=color,
            alpha=0.8
        )
        ax.add_patch(rect)
        
        # 添加状态标签(如果时间段足够长)
        duration_minutes = duration.total_seconds() / 60
        if duration_minutes > 3:  # 超过3分钟显示标签
            mid_time = start_time + duration / 2
            state_name = segment.get('state_name', f'状态{state}')
            ax.text(mid_time, y_center, state_name, 
                   ha='center', va='center', fontsize=10, fontweight='bold',
                   bbox=dict(boxstyle="round,pad=0.2", facecolor='white', alpha=0.8))
    
    # 设置y轴
    ax.set_ylim(-0.5, 0.5)
    ax.set_yticks([0])
    ax.set_yticklabels(['睡眠状态'], fontsize=12, fontweight='bold')
    
    # 设置x轴时间格式
    start_time = datetime.fromtimestamp(segments[0]['start_timestamp'])
    end_time = datetime.fromtimestamp(segments[-1]['end_timestamp'])
    
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
    ax.xaxis.set_major_locator(mdates.MinuteLocator(interval=10))
    ax.set_xlim(start_time, end_time)
    
    # 样式设置
    ax.grid(True, axis='x', alpha=0.3, linestyle='--')
    ax.set_facecolor('#f8f9fa')
    
    # 标题
    total_duration = (end_time - start_time).total_seconds() / 3600
    device_sn = gantt_data.get('device_sn', '设备')
    ax.set_title(f'{device_sn} 睡眠状态甘特图 - 时长: {total_duration:.1f}小时', 
                fontsize=14, fontweight='bold')
    ax.set_xlabel('时间', fontsize=12)
    
    # 创建图例
    unique_states = list(set(seg['state'] for seg in segments))
    legend_elements = []
    for state in sorted(unique_states):
        color = state_colors.get(state, "#CCCCCC")
        # 从segments中找到对应的state_name
        state_name = next((seg['state_name'] for seg in segments if seg['state'] == state), f'状态{state}')
        legend_elements.append(
            patches.Patch(color=color, label=state_name)
        )
    
    ax.legend(handles=legend_elements, loc='center left', bbox_to_anchor=(1, 0.5))
    
    plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha='right')
    plt.tight_layout()
    plt.subplots_adjust(right=0.85)
    plt.show()
    
    # 打印统计信息
    print_gantt_statistics(gantt_data)


def print_gantt_statistics(gantt_data):
    """打印甘特图统计信息"""
    segments = gantt_data['segments']
    
    print(f"\n📊 甘特图统计:")
    print(f"   设备: {gantt_data.get('device_sn', 'N/A')}")
    print(f"   时间段数量: {len(segments)}")
    
    # 统计各状态时长
    state_durations = {}
    total_duration = 0
    
    for segment in segments:
        state = segment['state']
        duration = segment['duration']
        state_name = segment.get('state_name', f'状态{state}')
        
        if state_name not in state_durations:
            state_durations[state_name] = 0
        state_durations[state_name] += duration
        total_duration += duration
    
    print(f"   总时长: {total_duration/3600:.2f} 小时")
    print(f"   各状态时长:")
    for state_name, duration in state_durations.items():
        percentage = (duration / total_duration) * 100 if total_duration > 0 else 0
        minutes = duration / 60
        if minutes >= 60:
            time_str = f"{minutes/60:.1f}小时"
        else:
            time_str = f"{minutes:.1f}分钟"
        print(f"     📈 {state_name}: {time_str} ({percentage:.1f}%)")


def preprocess_for_flutter_gantt(raw_data):
    """正确的预处理逻辑"""
    if not raw_data:
        return {"segments": []}
    
    sorted_data = sorted(raw_data, key=lambda x: x['timestamp'])
    segments = []
    
    for i in range(len(sorted_data) - 1):  # 注意：不包括最后一个点
        current = sorted_data[i]
        next_point = sorted_data[i + 1]
        
        segments.append({
            "start_timestamp": current['timestamp'],
            "end_timestamp": next_point['timestamp'], 
            "duration": next_point['timestamp'] - current['timestamp'],
            "state": current['state'],
            "state_name": get_state_name(current['state'])
        })
    
    return {"segments": segments}


def get_state_name(state):
    """获取状态名称"""
    state_names = {
        0: "在床",
        1: "离床", 
        2: "体动",
        3: "深睡眠",
        4: "重物",
        5: "打鼾"
    }
    return state_names.get(state, f"未知状态{state}")


def test_physiological_sleep_staging():
    """测试基于生理数据的睡眠分区"""
    
    sample_data = utils.request_url(
        url="https://ai.shunxikj.com:9039/api/real_time_vital_data",
        param_dict={
            "device_sn": "UART__TOPIC_SX_SLEEP_HEART_RATE_LG_02_ODATA",
            "start_timestamp": "1761713059",
            "end_timestamp": "1761717514"
        }
    )
    
    gantt_status_data = preprocess_for_flutter_gantt(raw_data=sample_data)

    print("=== 基于生理数据的睡眠分区测试 ===\n")
    
    # 初始化组件
    processor = DataProcessor()
    generator = SleepReportGenerator()
    
    print("1. 原始数据概览:")
    for i, point in enumerate(sample_data):
        state_names = {0: "在床", 1: "离床", 2: "体动", 3: "弱呼吸", 4: "重物", 5: "打鼾"}
        time_str = datetime.fromtimestamp(point['timestamp']).strftime('%H:%M:%S')
        print(f"   数据点{i+1}: {time_str} - 心率{point['heart_bpm']}bpm, 呼吸{point['breath_bpm']}bpm, {state_names[point['state']]}")
    print()
    
    # 数据清洗
    cleaned_data = processor.clean_data(sample_data)
    print(f"2. 数据清洗: {len(sample_data)} → {len(cleaned_data)} 个数据点\n")
    
    # 生成报告
    report = generator.generate_report(
        raw_data=cleaned_data,
        report_id=1,
        device_sn="UART__TOPIC_SX_SLEEP_HEART_RATE_LG_02_ODATA"
    )
    
    print("3. 睡眠分区结果:")
    if report.sleep_state_trend:
        phase_names = {
            "deep_sleep": "深睡眠",
            "light_sleep": "浅睡眠", 
            "rem_sleep": "REM睡眠",
            "awake": "清醒",
            "movement": "体动"
        }
        
        total_duration = 0
        for i, phase in enumerate(report.sleep_state_trend):
            phase_name = phase_names.get(phase['phase_type'], phase['phase_type'])
            duration = phase['duration']
            total_duration += duration
            percentage = (duration / max(sum(p['duration'] for p in report.sleep_state_trend), 1)) * 100
            
            print(f"   阶段{i+1}: {phase_name}")
            print(f"           时间: {phase['start_time_str']} - {phase['end_time_str']}")
            print(f"           时长: {phase['duration_str']} ({percentage:.1f}%)")
            print()
    
    print("4. 睡眠结构分析:")
    print(f"   - 深睡眠比例: {report.deep_sleep_ratio:.1%}")
    print(f"   - 浅睡眠比例: {report.light_sleep_ratio:.1%}")
    print(f"   - 平均心率: {report.avg_heart_rate} bpm")
    print(f"   - 平均呼吸率: {report.avg_breath_rate} bpm")
    print(f"   - 心率变异性: {report.heart_rate_variability:.4f}")
    print()
    
    print("5. 睡眠质量评分:")
    score = report.sleep_score
    print(f"   - 总评分: {score.total_score:.1f}/100")
    print(f"   - 睡眠效率评分: {score.sleep_efficiency_score:.1f}/15")
    print(f"   - 体动指数评分: {score.movement_index_score:.1f}/5")
    print(f"   - 心率评分: {score.heart_rate_score:.1f}/10")
    print(f"   - 呼吸率评分: {score.breath_rate_score:.1f}/10")
    print()

    plot_gantt_from_processed_data(gantt_status_data)
    
    return report




if __name__ == "__main__":
    # 测试改进后的睡眠分区
    report = test_physiological_sleep_staging()
    
    
    # 导出改进后的报告
    report_dict = {
        'sleep_phases': [
            {
                'phase_type': phase['phase_type'],
                'start_time_str': phase['start_time_str'],
                'end_time_str': phase['end_time_str'],
                'duration_str': phase['duration_str']
            }
            for phase in report.sleep_state_trend
        ],
        'sleep_summary': {
            'deep_sleep_ratio': report.deep_sleep_ratio,
            'light_sleep_ratio': report.light_sleep_ratio,
            'avg_heart_rate': report.avg_heart_rate,
            'avg_breath_rate': report.avg_breath_rate,
            'total_score': report.sleep_score.total_score
        }
    }
    
    with open("/work/ai/real_time_vital_analyze/out.json", 'w', encoding='utf-8') as f:
        json.dump(report_dict, f, ensure_ascii=False, indent=2)
    
    print("=== 测试完成 ===")
    print(f"改进后的睡眠分区已生成，总评分: {report.sleep_score.total_score:.1f}/100")
    print("现在睡眠分区基于真实的生理数据，而不是简单的状态映射！")