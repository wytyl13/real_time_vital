#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time    : 2025/10/29 19:02
@Author  : weiyutao
@File    : test_sleep.py
"""


import json
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.patches as patches
from datetime import datetime
from src.complete_sleep_pipline import complete_sleep_analysis_pipeline
from tools.utils import Utils
from datetime import timedelta
# 初始化工具
utils = Utils()

def setup_chinese_font():
    """设置中文字体"""
    # 设置多个备选字体
    plt.rcParams['font.sans-serif'] = ['SimHei', 'WenQuanYi Zen Hei', 'Microsoft YaHei', 'Arial Unicode MS', 'DejaVu Sans']
    plt.rcParams['axes.unicode_minus'] = False
    plt.rcParams['figure.figsize'] = [16, 6]
    
    # 强制刷新字体缓存
    import matplotlib
    matplotlib.font_manager._load_fontmanager(try_read_cache=False)


def plot_sleep_gantt(gantt_data):
    """绘制睡眠状态甘特图"""
    setup_chinese_font()
    # 添加这两行，强制设置图例字体
    if not gantt_data or not gantt_data.get('segments'):
        print("❌ 没有甘特图数据")
        return
    
    segments = gantt_data['segments']
    
    # 增强的状态颜色配置（包含睡眠分期状态）
    state_colors = {
        0: "#87CEEB",   # 在床（浅蓝）
        1: "#FFB6C1",   # 离床（粉红）
        2: "#FFA500",   # 体动（橙色）
        3: "#FF6347",   # 弱呼吸（番茄红）
        4: "#8B4513",   # 重物（棕色）
        5: "#32CD32",   # 打鼾（绿色）
        10: "#4169E1",  # 深睡眠（皇家蓝）
        11: "#87CEEB",  # 浅睡眠（天蓝）
        12: "#9370DB",  # REM睡眠（紫色）
        13: "#FFB6C1"   # 清醒（粉红）
    }
    
    state_name_map = {
        0: "In Bed", 
        1: "Out of Bed", 
        2: "Body Movement", 
        3: "Weak Breath", 
        4: "Heavy Object", 
        5: "Snoring",
        10: "Deep Sleep", 
        11: "Light Sleep", 
        12: "REM Sleep", 
        13: "Awake"
    } 
    
    # 创建图表 - 增加右边距给图例留空间
    fig, ax = plt.subplots(figsize=(18, 5))
    
    # 转换所有时间戳为datetime对象
    start_time = datetime.fromtimestamp(segments[0]['start_timestamp'])
    end_time = datetime.fromtimestamp(segments[-1]['end_timestamp'])
    
    print(f"\n📊 甘特图数据检查:")
    print(f"   总段数: {len(segments)}")
    print(f"   时间范围: {start_time.strftime('%H:%M:%S')} - {end_time.strftime('%H:%M:%S')}")
    
    # 收集所有独特的状态用于图例
    unique_states = {}
    
    # 绘制每个时间段
    y_position = 1
    bar_height = 0.8
    
    for i, segment in enumerate(segments):
        seg_start = datetime.fromtimestamp(segment['start_timestamp'])
        seg_end = datetime.fromtimestamp(segment['end_timestamp'])
        state = segment['state']
        
        # 记录状态用于图例
        if state not in unique_states:
            # state_name = segment.get('state_name', state_name_map.get(state, f'状态{state}'))
            state_name = state_name_map.get(state, f'State{state}')
            unique_states[state] = state_name
        
        color = state_colors.get(state, "#CCCCCC")
        duration_seconds = segment['duration']
        
        # 使用barh绘制横条 - 这样可以避免间隙
        ax.barh(
            y=y_position,
            width=duration_seconds,
            left=(seg_start - start_time).total_seconds(),
            height=bar_height,
            color=color,
            edgecolor='none',  # 移除边框避免间隙
            alpha=0.9
        )
        
        # 如果时间段足够长，添加标签
        if duration_seconds > 300:  # 超过5分钟
            mid_point = (seg_start - start_time).total_seconds() + duration_seconds / 2
            state_name = segment.get('state_name', state_name_map.get(state, ''))
            
            ax.text(
                mid_point, y_position, state_name,
                ha='center', va='center',
                fontsize=8, fontweight='bold',
                color='white' if state in [10, 2, 4] else 'black',
                bbox=dict(boxstyle="round,pad=0.2", 
                         facecolor='black' if state in [10, 2, 4] else 'white',
                         alpha=0.6, edgecolor='none')
            )
    
    # 设置x轴 - 使用秒数而不是datetime
    total_seconds = (end_time - start_time).total_seconds()
    ax.set_xlim(0, total_seconds)
    
    # 创建时间刻度标签
    num_ticks = 10
    tick_positions = [i * total_seconds / num_ticks for i in range(num_ticks + 1)]
    tick_labels = [
        (start_time + timedelta(seconds=pos)).strftime('%H:%M')
        for pos in tick_positions
    ]
    ax.set_xticks(tick_positions)
    ax.set_xticklabels(tick_labels, rotation=45, ha='right')
    
    # 设置y轴
    ax.set_ylim(0.5, 1.5)
    ax.set_yticks([1])
    ax.set_yticklabels(['睡眠状态'], fontsize=14, fontweight='bold')
    
    # 网格
    ax.grid(True, axis='x', alpha=0.3, linestyle='--', linewidth=0.5)
    ax.set_facecolor('#f9f9f9')
    
    # 标题
    total_hours = total_seconds / 3600
    ax.set_title(
        f'睡眠状态甘特图 - 总时长: {total_hours:.1f}小时',
        fontsize=16, fontweight='bold', pad=20
    )
    ax.set_xlabel('时间', fontsize=12, fontweight='bold')
    
    # 创建图例 - 确保显示
    legend_elements = []
    for state in sorted(unique_states.keys()):
        color = state_colors.get(state, "#CCCCCC")
        state_name = unique_states[state]
        legend_elements.append(
            patches.Patch(facecolor=color, edgecolor='black', linewidth=0.5, label=state_name)
        )
    
    # 图例放在右侧，确保可见
    legend = ax.legend(
        handles=legend_elements,
        loc='center left',
        bbox_to_anchor=(1.02, 0.5),
        frameon=True,
        shadow=True,
        prop={'family': 'DejaVu Sans', 'size': 11},
        fontsize=10,
        title='Sleep Stages',
        # title_fontsize=11,
        title_fontproperties={'family': 'DejaVu Sans', 'size': 12}
    )
    legend.get_frame().set_facecolor('white')
    legend.get_frame().set_alpha(0.95)
    
    # 调整布局确保图例可见
    plt.tight_layout()
    plt.subplots_adjust(right=0.85)
    
    # 保存图片
    plt.savefig('sleep_gantt_chart.png', dpi=300, bbox_inches='tight')
    print("✅ 甘特图已保存: sleep_gantt_chart.png")
    
    # 打印统计信息
    print(f"\n📈 状态统计:")
    state_durations = {}
    for seg in segments:
        state = seg['state']
        state_name = seg.get('state_name', state_name_map.get(state, f'状态{state}'))
        if state_name not in state_durations:
            state_durations[state_name] = 0
        state_durations[state_name] += seg['duration']
    
    for state_name, duration in sorted(state_durations.items(), key=lambda x: -x[1]):
        percentage = (duration / total_seconds) * 100
        hours = duration / 3600
        minutes = (duration % 3600) / 60
        print(f"   {state_name}: {hours:.0f}小时{minutes:.0f}分 ({percentage:.1f}%)")
    
    plt.show()


def plot_heart_rate_trend(heart_rate_data):
    """绘制心率趋势图"""
    setup_chinese_font()
    
    if not heart_rate_data:
        print("❌ 没有心率趋势数据")
        return
    
    # 提取数据
    timestamps = [datetime.fromtimestamp(d['timestamp']) for d in heart_rate_data]
    heart_rates = [d['value'] for d in heart_rate_data]
    
    # 创建图表
    fig, ax = plt.subplots(figsize=(16, 6))
    
    # 绘制心率曲线
    ax.plot(timestamps, heart_rates, 
            color='#E74C3C', linewidth=2, marker='o', 
            markersize=4, label='心率', alpha=0.8)
    
    # 填充区域
    ax.fill_between(timestamps, heart_rates, alpha=0.2, color='#E74C3C')
    
    # 添加正常范围参考线
    ax.axhline(y=60, color='green', linestyle='--', linewidth=1, alpha=0.5, label='正常下限(60)')
    ax.axhline(y=100, color='green', linestyle='--', linewidth=1, alpha=0.5, label='正常上限(100)')
    ax.axhline(y=80, color='blue', linestyle=':', linewidth=1, alpha=0.5, label='平均心率')
    
    # 标注最高和最低点
    max_hr = max(heart_rates)
    min_hr = min(heart_rates)
    max_idx = heart_rates.index(max_hr)
    min_idx = heart_rates.index(min_hr)
    
    ax.annotate(f'最高: {max_hr:.0f}', 
                xy=(timestamps[max_idx], max_hr),
                xytext=(10, 10), textcoords='offset points',
                bbox=dict(boxstyle='round,pad=0.5', facecolor='yellow', alpha=0.7),
                arrowprops=dict(arrowstyle='->', color='red', lw=1.5))
    
    ax.annotate(f'最低: {min_hr:.0f}', 
                xy=(timestamps[min_idx], min_hr),
                xytext=(10, -20), textcoords='offset points',
                bbox=dict(boxstyle='round,pad=0.5', facecolor='lightblue', alpha=0.7),
                arrowprops=dict(arrowstyle='->', color='blue', lw=1.5))
    
    # 设置标题和标签
    avg_hr = sum(heart_rates) / len(heart_rates)
    ax.set_title(f'心率趋势图 - 平均心率: {avg_hr:.1f} bpm', 
                fontsize=14, fontweight='bold', pad=15)
    ax.set_xlabel('时间', fontsize=12)
    ax.set_ylabel('心率 (bpm)', fontsize=12)
    
    # 设置x轴格式
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
    ax.xaxis.set_major_locator(mdates.MinuteLocator(interval=30))
    plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha='right')
    
    # 网格和样式
    ax.grid(True, alpha=0.3, linestyle='--')
    ax.set_facecolor('#f8f9fa')
    ax.legend(loc='upper right', frameon=True, shadow=True)
    
    plt.tight_layout()
    
    # 保存图片
    plt.savefig('heart_rate_trend.png', dpi=300, bbox_inches='tight')
    print("✅ 心率趋势图已保存: heart_rate_trend.png")
    plt.show()


def plot_breath_rate_trend(breath_rate_data):
    """绘制呼吸率趋势图"""
    setup_chinese_font()
    
    if not breath_rate_data:
        print("❌ 没有呼吸率趋势数据")
        return
    
    # 提取数据
    timestamps = [datetime.fromtimestamp(d['timestamp']) for d in breath_rate_data]
    breath_rates = [d['value'] for d in breath_rate_data]
    
    # 创建图表
    fig, ax = plt.subplots(figsize=(16, 6))
    
    # 绘制呼吸率曲线
    ax.plot(timestamps, breath_rates, 
            color='#3498DB', linewidth=2, marker='s', 
            markersize=4, label='呼吸率', alpha=0.8)
    
    # 填充区域
    ax.fill_between(timestamps, breath_rates, alpha=0.2, color='#3498DB')
    
    # 添加正常范围参考线
    ax.axhline(y=12, color='green', linestyle='--', linewidth=1, alpha=0.5, label='正常下限(12)')
    ax.axhline(y=20, color='green', linestyle='--', linewidth=1, alpha=0.5, label='正常上限(20)')
    ax.axhline(y=16, color='blue', linestyle=':', linewidth=1, alpha=0.5, label='理想呼吸率')
    
    # 标注最高和最低点
    max_br = max(breath_rates)
    min_br = min(breath_rates)
    max_idx = breath_rates.index(max_br)
    min_idx = breath_rates.index(min_br)
    
    ax.annotate(f'最高: {max_br:.1f}', 
                xy=(timestamps[max_idx], max_br),
                xytext=(10, 10), textcoords='offset points',
                bbox=dict(boxstyle='round,pad=0.5', facecolor='yellow', alpha=0.7),
                arrowprops=dict(arrowstyle='->', color='red', lw=1.5))
    
    ax.annotate(f'最低: {min_br:.1f}', 
                xy=(timestamps[min_idx], min_br),
                xytext=(10, -20), textcoords='offset points',
                bbox=dict(boxstyle='round,pad=0.5', facecolor='lightblue', alpha=0.7),
                arrowprops=dict(arrowstyle='->', color='blue', lw=1.5))
    
    # 设置标题和标签
    avg_br = sum(breath_rates) / len(breath_rates)
    ax.set_title(f'呼吸率趋势图 - 平均呼吸率: {avg_br:.1f} 次/分钟', 
                fontsize=14, fontweight='bold', pad=15)
    ax.set_xlabel('时间', fontsize=12)
    ax.set_ylabel('呼吸率 (次/分钟)', fontsize=12)
    
    # 设置x轴格式
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
    ax.xaxis.set_major_locator(mdates.MinuteLocator(interval=30))
    plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha='right')
    
    # 网格和样式
    ax.grid(True, alpha=0.3, linestyle='--')
    ax.set_facecolor('#f8f9fa')
    ax.legend(loc='upper right', frameon=True, shadow=True)
    
    plt.tight_layout()
    
    # 保存图片
    plt.savefig('breath_rate_trend.png', dpi=300, bbox_inches='tight')
    print("✅ 呼吸率趋势图已保存: breath_rate_trend.png")
    plt.show()


def run_sleep_analysis_pipeline():
    """运行完整的睡眠分析流水线"""
    
    # 1. 获取原始数据
    print("📥 正在获取睡眠数据...")
    raw_data = utils.request_url(
        url="https://ai.shunxikj.com:9039/api/real_time_vital_data",
        param_dict={
            "device_sn": "UART__TOPIC_SX_SLEEP_HEART_RATE_LG_02_ODATA",
            "start_timestamp": "1761713059",
            "end_timestamp": "1761717514"
        }
    )
    
    if not raw_data:
        print("❌ 获取数据失败")
        return
    
    print(f"✅ 获取到 {len(raw_data)} 条原始数据\n")
    
    # 2. 运行完整分析流水线
    print("🚀 开始运行睡眠分析流水线...\n")
    
    result = complete_sleep_analysis_pipeline(
        raw_data=raw_data,
        device_sn="UART__TOPIC_SX_SLEEP_HEART_RATE_LG_02_ODATA",
        report_id=1
    )
    
    # 3. 检查结果
    if "error" in result:
        print(f"❌ 分析失败: {result['error']}")
        return
    
    # 4. 输出分析结果
    print("\n" + "="*60)
    print("📊 睡眠分析结果")
    print("="*60 + "\n")
    
    # 睡眠报告
    sleep_report = result['sleep_report']
    print(f"🛏️  上床时间: {sleep_report.bed_time}")
    print(f"🌅 离床时间: {sleep_report.leave_bed_time}")
    print(f"⏱️  总时长: {sleep_report.total_duration}")
    print(f"💤 深睡眠: {sleep_report.deep_sleep_duration} ({sleep_report.deep_sleep_ratio:.1%})")
    print(f"😴 浅睡眠: {sleep_report.light_sleep_duration} ({sleep_report.light_sleep_ratio:.1%})")
    print(f"😵 清醒时长: {sleep_report.awake_duration}")
    print(f"❤️  平均心率: {sleep_report.avg_heart_rate} bpm")
    print(f"🫁 平均呼吸率: {sleep_report.avg_breath_rate} bpm")
    print(f"📈 心率变异性: {sleep_report.heart_rate_variability:.4f}")
    print(f"🏃 体动次数: {sleep_report.body_movement_count}")
    print(f"🚪 离床次数: {sleep_report.leave_bed_count}")
    print(f"\n⭐ 睡眠评分: {sleep_report.sleep_score.total_score:.1f}/100\n")
    
    # 睡眠阶段
    print("🧠 睡眠阶段分析:")
    for i, phase in enumerate(result['sleep_phases'], 1):
        phase_names = {
            "deep_sleep": "深睡眠",
            "light_sleep": "浅睡眠",
            "rem_sleep": "REM睡眠",
            "awake": "清醒"
        }
        phase_name = phase_names.get(phase.phase_type, phase.phase_type)
        start = datetime.fromtimestamp(phase.start_time).strftime('%H:%M')
        end = datetime.fromtimestamp(phase.end_time).strftime('%H:%M')
        duration_min = phase.duration / 60
        print(f"   {i}. {phase_name}: {start}-{end} ({duration_min:.0f}分钟)")
    
    # 数据质量
    print(f"\n📋 数据质量:")
    quality = result['data_quality']
    print(f"   - 数据点数: {quality['total_points']}")
    print(f"   - 质量评分: {quality['quality_score']}/100")
    print(f"   - 覆盖时长: {quality['coverage_hours']:.1f}小时")
    print(f"   - 问题: {', '.join(quality['issues'])}")
    
    # 5. 保存结果到JSON文件
    output_file = "sleep_analysis_result.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        output_data = {
            'sleep_report': {
                'bed_time': sleep_report.bed_time,
                'leave_bed_time': sleep_report.leave_bed_time,
                'total_duration': sleep_report.total_duration,
                'deep_sleep_duration': sleep_report.deep_sleep_duration,
                'light_sleep_duration': sleep_report.light_sleep_duration,
                'awake_duration': sleep_report.awake_duration,
                'avg_heart_rate': sleep_report.avg_heart_rate,
                'avg_breath_rate': sleep_report.avg_breath_rate,
                'sleep_score': sleep_report.sleep_score.total_score,
                'health_report': sleep_report.health_report
            },
            'gantt_data': result['gantt_data'],
            'statistics': result['statistics'],
            'data_quality': result['data_quality']
        }
        json.dump(output_data, f, ensure_ascii=False, indent=2)
    
    print(f"\n💾 结果已保存到: {output_file}")
    
    # 6. 绘制图表
    print("\n📊 开始绘制图表...\n")
    
    # 绘制甘特图
    print("🎨 绘制睡眠状态甘特图...")
    plot_sleep_gantt(result['gantt_data'])
    
    # 绘制心率趋势
    print("\n❤️  绘制心率趋势图...")
    plot_heart_rate_trend(sleep_report.heart_rate_trend)
    
    # 绘制呼吸率趋势
    print("\n🫁 绘制呼吸率趋势图...")
    plot_breath_rate_trend(sleep_report.breath_rate_trend)
    
    print("\n🎉 所有图表绘制完成!")
    
    return result


if __name__ == "__main__":
    print("🌙 睡眠分析系统启动\n")
    result = run_sleep_analysis_pipeline()
    print("\n✅ 分析完成!")