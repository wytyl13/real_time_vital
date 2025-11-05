#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time    : 2025/10/29 16:05
@Author  : weiyutao
@File    : data_processor.py
"""

import numpy as np
import statistics
from typing import List, Dict, Any
from .sleep_analyze_config import DataValidationConfig


class DataProcessor:
    """数据处理工具类"""
    
    def __init__(self):
        self.validation_config = DataValidationConfig()
    
    def validate_data_point(self, data_point: Dict) -> bool:
        """验证单个数据点的有效性"""
        try:
            # 检查必需字段
            required_fields = ['timestamp', 'heart_bpm', 'breath_bpm', 'state']
            for field in required_fields:
                if field not in data_point:
                    return False
            
            # 检查数值范围
            for field, (min_val, max_val) in self.validation_config.VALID_RANGES.items():
                if field in data_point:
                    value = data_point[field]
                    if not (min_val <= value <= max_val):
                        return False
            
            return True
        except (TypeError, ValueError):
            return False
    
    def clean_data(self, raw_data: List[Dict]) -> List[Dict]:
        """清洗数据，移除异常值"""
        # 1. 过滤无效数据点
        valid_data = [point for point in raw_data if self.validate_data_point(point)]
        
        if not valid_data:
            return []
        
        # 2. 按时间戳排序
        valid_data.sort(key=lambda x: x['timestamp'])
        
        # 3. 检测和处理异常值
        cleaned_data = self._handle_outliers(valid_data)
        
        return cleaned_data
    
    def _handle_outliers(self, data: List[Dict]) -> List[Dict]:
        """检测和处理异常值"""
        if len(data) < 4:
            return data
        
        # 使用IQR方法检测异常值
        heart_rates = [point['heart_bpm'] for point in data]
        breath_rates = [point['breath_bpm'] for point in data]
        
        heart_outliers = self._detect_outliers_iqr(heart_rates)
        breath_outliers = self._detect_outliers_iqr(breath_rates)
        
        cleaned_data = []
        for i, point in enumerate(data):
            new_point = point.copy()
            
            # 处理心率异常值
            if heart_outliers[i]:
                new_point['heart_bpm'] = self._get_replacement_value(
                    data, i, 'heart_bpm', 70
                )
            
            # 处理呼吸率异常值
            if breath_outliers[i]:
                new_point['breath_bpm'] = self._get_replacement_value(
                    data, i, 'breath_bpm', 16
                )
            
            cleaned_data.append(new_point)
        
        return cleaned_data
    
    def _detect_outliers_iqr(self, values: List[float]) -> List[bool]:
        """使用IQR方法检测异常值"""
        if len(values) < 4:
            return [False] * len(values)
        
        q1 = np.percentile(values, 25)
        q3 = np.percentile(values, 75)
        iqr = q3 - q1
        
        lower_bound = q1 - 1.5 * iqr
        upper_bound = q3 + 1.5 * iqr
        
        return [value < lower_bound or value > upper_bound for value in values]
    
    def _get_replacement_value(self, data: List[Dict], index: int, 
                             field: str, default: float) -> float:
        """获取异常值的替代值"""
        valid_values = []
        
        # 获取前后3个点的值
        for i in range(max(0, index - 3), min(len(data), index + 4)):
            if i != index and field in data[i]:
                valid_values.append(data[i][field])
        
        return statistics.mean(valid_values) if valid_values else default
    
    def analyze_data_quality(self, data: List[Dict]) -> Dict[str, Any]:
        """分析数据质量"""
        if not data:
            return {
                'total_points': 0,
                'quality_score': 0,
                'issues': ['无数据']
            }
        
        total_points = len(data)
        issues = []
        quality_score = 100
        
        # 检查数据完整性
        missing_fields = 0
        for point in data:
            for field in ['heart_bpm', 'breath_bpm', 'state']:
                if field not in point or point[field] is None:
                    missing_fields += 1
        
        missing_ratio = missing_fields / (total_points * 3)
        if missing_ratio > 0.1:
            issues.append(f'数据缺失率较高: {missing_ratio:.1%}')
            quality_score -= 20
        
        # 检查时间间隔一致性
        if len(data) > 1:
            time_gaps = [data[i]['timestamp'] - data[i-1]['timestamp'] 
                        for i in range(1, len(data))]
            
            if time_gaps:
                gap_std = statistics.stdev(time_gaps)
                gap_mean = statistics.mean(time_gaps)
                
                if gap_std > gap_mean * 0.5:
                    issues.append('时间间隔不规律')
                    quality_score -= 15
        
        return {
            'total_points': total_points,
            'quality_score': max(0, quality_score),
            'issues': issues if issues else ['数据质量良好'],
            'missing_ratio': missing_ratio,
            'coverage_hours': (data[-1]['timestamp'] - data[0]['timestamp']) / 3600 if len(data) > 1 else 0
        }


# 导出类
__all__ = ['DataProcessor']