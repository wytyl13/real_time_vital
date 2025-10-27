#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time    : 2024/12/23 17:47
@Author  : weiyutao
@File    : utils.py
"""
import traceback
import os
import shutil
import re
import yaml
from typing import (
    Optional,
    Dict
)
import sys
from enum import Enum
import jieba
import numpy as np
import requests
import json

from agent.utils.log import Logger
from rich.console import Console
from rich.table import Table
from io import StringIO
import logging

logger = Logger('Utils')



TAG_PATTERNS = {
    'data_frame': r'<data_frame(?:\s+[^>]*)?>(.*?)</data_frame>',
    'card': r'<card(?:\s+[^>]*)?>(.*?)</card>', 
    'confirm': r'<confirm(?:\s+[^>]*)?>(.*?)</confirm>',
    'image': r'<image(?:\s+[^>]*)?>(.*?)</image>', 
    'preview': r'<preview(?:\s+[^>]*)?>(.*?)</preview>',
    'suggestions': r'<suggestions(?:\s+[^>]*)?>(.*?)</suggestions>',
    'real_time_vital': r'<real_time_vital(?:\s+[^>]*)?>(.*?)</real_time_vital>',
}


class StrEnum(str, Enum):
    def __str__(self) -> str:
        # overwrite the __str__ method to implement enum_instance.attribution == enum_instance.attribution.value
        return self.value
    
    def __repr__(self) -> str:
        return f"'{str(self)}'"



class Utils:
    """Utils class what aims to code some generation tools what can be used in all tool, agent or other function.
    """
    def __init__(self) -> None:
        pass
        
    def get_error_info(self, error_info: str, e: Exception):
        """get the error information that involved the error code line and reason.

        Args:
            error_info (str): the error information that you want to raise.
            e (Exception): the error reason.

        Returns:
            _type_: error infomation.
        """
        error_info = traceback.format_exc()
        error = f"{error_info}{str(e)}！\n{error_info}"
        return error


    def chinese_to_pinyin(self, text):
        """
        将汉语转换为全拼的简单函数
        注意：这是一个基础版本，对于多音字可能不够准确
        建议在生产环境中使用 pypinyin 库
        """
        # 简化的拼音映射表（仅包含常用汉字）
        pinyin_dict = {
            # 常用汉字拼音映射
            '一': 'yi', '二': 'er', '三': 'san', '四': 'si', '五': 'wu', 
            '六': 'liu', '七': 'qi', '八': 'ba', '九': 'jiu', '十': 'shi',
            '零': 'ling', '百': 'bai', '千': 'qian', '万': 'wan',
            
            # 姓名常用字
            '张': 'zhang', '王': 'wang', '李': 'li', '赵': 'zhao', '刘': 'liu',
            '陈': 'chen', '杨': 'yang', '黄': 'huang', '周': 'zhou', '吴': 'wu',
            '徐': 'xu', '孙': 'sun', '马': 'ma', '朱': 'zhu', '胡': 'hu',
            '林': 'lin', '郭': 'guo', '何': 'he', '高': 'gao', '罗': 'luo',
            
            # 名字常用字
            '明': 'ming', '华': 'hua', '建': 'jian', '文': 'wen', '军': 'jun',
            '志': 'zhi', '勇': 'yong', '伟': 'wei', '强': 'qiang', '磊': 'lei',
            '超': 'chao', '鹏': 'peng', '涛': 'tao', '松': 'song', '浩': 'hao',
            '亮': 'liang', '政': 'zheng', '谦': 'qian', '诚': 'cheng', '先': 'xian',
            '敬': 'jing', '振': 'zhen', '壮': 'zhuang', '会': 'hui', '思': 'si',
            '群': 'qun', '豪': 'hao', '心': 'xin', '邦': 'bang', '承': 'cheng',
            '乐': 'le', '绍': 'shao', '功': 'gong', '松': 'song', '善': 'shan',
            '厚': 'hou', '庆': 'qing', '磊': 'lei', '民': 'min', '友': 'you',
            '裕': 'yu', '河': 'he', '哲': 'zhe', '江': 'jiang', '超': 'chao',
            '浩': 'hao', '亮': 'liang', '政': 'zheng', '谦': 'qian', '诚': 'cheng',
            
            # 地名常用字
            '北': 'bei', '京': 'jing', '上': 'shang', '海': 'hai', '广': 'guang',
            '州': 'zhou', '深': 'shen', '圳': 'zhen', '天': 'tian', '津': 'jin',
            '重': 'chong', '庆': 'qing', '成': 'cheng', '都': 'du', '西': 'xi',
            '安': 'an', '南': 'nan', '宁': 'ning', '武': 'wu', '汉': 'han',
            '长': 'chang', '沙': 'sha', '哈': 'ha', '尔': 'er', '滨': 'bin',
            '沈': 'shen', '阳': 'yang', '大': 'da', '连': 'lian', '青': 'qing',
            '岛': 'dao', '济': 'ji', '郑': 'zheng', '福': 'fu', '厦': 'xia',
            '门': 'men', '昆': 'kun', '山': 'shan', '太': 'tai', '原': 'yuan',
            
            # 菜品常用字
            '宫': 'gong', '保': 'bao', '鸡': 'ji', '丁': 'ding', '麻': 'ma',
            '婆': 'po', '豆': 'dou', '腐': 'fu', '糖': 'tang', '醋': 'cu',
            '里': 'li', '脊': 'ji', '红': 'hong', '烧': 'shao', '肉': 'rou',
            '鱼': 'yu', '香': 'xiang', '锅': 'guo', '菜': 'cai', '汤': 'tang',
            '饭': 'fan', '面': 'mian', '粥': 'zhou', '蛋': 'dan', '虾': 'xia',
            '蟹': 'xie', '牛': 'niu', '羊': 'yang', '猪': 'zhu', '排': 'pai',
            '骨': 'gu', '翅': 'chi', '腿': 'tui', '胸': 'xiong', '肚': 'du',
            '片': 'pian', '丝': 'si', '块': 'kuai', '条': 'tiao', '粒': 'li',
            
            # 其他常用字
            '的': 'de', '是': 'shi', '在': 'zai', '了': 'le', '不': 'bu',
            '和': 'he', '有': 'you', '人': 'ren', '这': 'zhe', '中': 'zhong',
            '来': 'lai', '说': 'shuo', '为': 'wei', '子': 'zi', '时': 'shi',
            '要': 'yao', '可': 'ke', '以': 'yi', '她': 'ta', '他': 'ta',
            '我': 'wo', '你': 'ni', '们': 'men', '好': 'hao', '吗': 'ma',
            '年': 'nian', '月': 'yue', '日': 'ri', '今': 'jin', '明': 'ming',
            '后': 'hou', '前': 'qian', '现': 'xian', '让': 'rang', '给': 'gei',
            '每': 'mei', '很': 'hen', '还': 'hai', '就': 'jiu', '那': 'na',
            '从': 'cong', '能': 'neng', '两': 'liang', '开': 'kai', '关': 'guan',
            '问': 'wen', '题': 'ti', '工': 'gong', '作': 'zuo', '学': 'xue',
            '校': 'xiao', '家': 'jia', '公': 'gong', '司': 'si', '车': 'che',
            '房': 'fang', '钱': 'qian', '买': 'mai', '卖': 'mai', '东': 'dong',
            '路': 'lu', '走': 'zou', '跑': 'pao', '看': 'kan', '听': 'ting',
            '话': 'hua', '书': 'shu', '水': 'shui', '火': 'huo', '电': 'dian',
            '风': 'feng', '雨': 'yu', '雪': 'xue', '云': 'yun', '花': 'hua',
            '树': 'shu', '草': 'cao', '山': 'shan', '河': 'he', '湖': 'hu',
            '色': 'se', '白': 'bai', '黑': 'hei', '红': 'hong', '绿': 'lv',
            '蓝': 'lan', '黄': 'huang', '紫': 'zi', '粉': 'fen', '灰': 'hui',
        }
        
        result = []
        for char in text:
            if char in pinyin_dict:
                result.append(pinyin_dict[char])
            elif char.isascii():  # 保留英文字符和数字
                result.append(char.lower())
            else:
                # 对于未知汉字，返回原字符或使用占位符
                result.append(f"[{char}]")
        
        return ''.join(result)


    def parse_server_return(self, response):
        print(f"response: ---------------------------------- {response}")
        if hasattr(response, 'body'):
            content = json.loads(response.body.decode())
            if content.get("success"):
                result = content.get("data", [])
                print(f"查询到 {len(result)} 条菜品记录")
            else:
                result = []
                print(f"查询失败: {content.get('message')}")
        return result


    def request_url(self, url: str, param_dict: Dict, method: Optional[str] = "POST", timeout: int = 10):
        try:
            headers = {
                'Content-Type': 'application/json',
                'Accept': 'application/json',
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            if method.upper() == 'GET':
                response = requests.get(url, params=param_dict, headers=headers, timeout=10)
            elif method.upper() == 'POST':
                print(f"param_dict: ------------------------- {param_dict}")
                print(f"url: ------------------------------ {url}")
                response = requests.post(url, json=param_dict, headers=headers, timeout=timeout, verify=False)
                print(f"response: =----================== {response}")
                # 删除这些错误的判断！
            else:
                response = requests.request(method, url, json=param_dict, headers=headers, timeout=timeout)
                
            response.raise_for_status()
            result = response.json()
            
            if isinstance(result, dict):
                if result.get("success") and "data" in result:
                    return result["data"]  # 对于你的API，这里会返回 []
                elif result.get("success") and "message" in result:
                    return result["message"]
                elif not result.get("success"):
                    return result.get('message', 'Unknown error')
            return result
            
        except Exception as e:
            return str(e)
    
    
    def setup_logger(self, name: str = "SleepDataStorage") -> logging.Logger:
        """创建自定义logger"""
        logger = logging.getLogger(name)
        
        # 避免重复添加handler
        if logger.handlers:
            return logger
        
        logger.setLevel(logging.INFO)
        
        # 创建控制台处理器
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(logging.INFO)
        
        # 创建格式器
        formatter = logging.Formatter(
            '[%(asctime)s] [%(levelname)-8s] [%(name)s] - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        handler.setFormatter(formatter)
        
        logger.addHandler(handler)
        return logger
    

    def request_url_(self, url: str, param_dict: Dict, method: Optional[str] = "POST"):
        # 同步版本
        try:
            headers = {
                'Content-Type': 'application/json',
                'Accept': 'application/json',
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            if method.upper() == 'GET':
                response = requests.get(url, params=param_dict, headers=headers, timeout=10)
            elif method.upper() == 'POST':
                # POST请求：参数放在请求体中
                print(f"param_dict: ------------------------- {param_dict}")
                print(f"url: ------------------------------ {url}")
                response = requests.post(url, json=param_dict, headers=headers, timeout=10, verify=False)
                print(f"response: =----================== {response}")
                if isinstance(response, bool) or isinstance(response, str) or response == "true":
                    return True
                return False
            else:
                # 其他方法
                response = requests.request(method, url, json=param_dict, headers=headers, timeout=10)
            response.raise_for_status()
            result = response.json()
            if isinstance(result, dict):
                if result.get("success") and "data" in result:
                    return result["data"]
                elif result.get("success") and "message" in result:
                    return result["message"]
                elif not result.get("success"):
                    return result.get('message', 'Unknown error')
            return result
        except Exception as e:
            return str(e)


    def format_table_data_markdown(self, type, key_mapping, data_list):
        if not data_list:
            return f"暂无{type}信息"
        
        if key_mapping is None:
            key_mapping = {
            'id': 'ID',
            'name': '姓名',
            'age': '年龄', 
            'type': '类型',
            'content': '内容',
            'create_time': '创建时间',
            'update_time': '更新时间',
            'status': '状态',
            'value': '数值',
            'object': '项目',
            'description': '描述'
        }
            
        # 创建表格标题
        markdown_table = f"### 您好！我已为您查询到{type}的信息：\n\n"
        first_dict = data_list[0] if data_list else {}
        available_keys = list(first_dict.keys())
        
        # 创建表头
        headers = [key_mapping.get(key, key) for key in available_keys]
        markdown_table += "| " + " | ".join(headers) + " |\n"
        markdown_table += "|" + "|".join(["-" * len(header) for header in headers]) + "|\n"
        for i, item in enumerate(data_list, 1):
            row_data = []
            for key in available_keys:
                value = item.get(key, '未知')
                # 处理时间格式
                if 'create_time' in key.lower() and isinstance(value, str) and 'T' in value:
                    date_part, time_part = value.split('T')
                    time_part = time_part.split('.')[0] if '.' in time_part else time_part
                    value = f"{date_part} {time_part}"
                value = str(value).replace('|', '\\|').replace('\n', ' ')
                row_data.append(value)
            
            markdown_table += "| " + " | ".join(row_data) + " |\n"
        
        return markdown_table


    def generate_order_html(self, title, order_content, output_file=None):
        """
        生成订单HTML文件
        
        参数:
        title: 网页标题
        order_content: 订单内容（完整的文本内容）
        output_file: 输出文件名，如果为None则返回HTML字符串
        
        返回:
        如果指定了output_file，则保存文件并返回文件路径
        否则返回HTML字符串
        """
        
        html_template = f'''<!DOCTYPE html>
    <html lang="zh-CN">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>{title}</title>
        <style>
            body {{
                margin: 0;
                padding: 20px;
                background-color: #f5f5f5;
                font-family: 'Courier New', monospace;
                display: flex;
                justify-content: center;
                align-items: center;
                min-height: 100vh;
            }}
            
            .order-container {{
                background-color: white;
                border: 2px solid #333;
                border-radius: 8px;
                padding: 30px;
                width: 600px;
                box-shadow: 0 4px 12px rgba(0,0,0,0.1);
                line-height: 1.6;
                font-size: 14px;
            }}
            
            .order-content {{
                white-space: pre-line;
                text-align: center;
                color: #333;
            }}
            
            @media print {{
                body {{
                    background-color: white;
                    padding: 0;
                }}
                .order-container {{
                    border: 1px solid #333;
                    box-shadow: none;
                    margin: 0;
                }}
            }}
        </style>
    </head>
    <body>
        <div class="order-container">
            <div class="order-content">{order_content}</div>
        </div>
    </body>
    </html>'''
        
        if output_file:
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(html_template)
            print(f"HTML文件已生成: {output_file}")
            return output_file
        else:
            return html_template


    def _extract_attributes(self, full_match):
        """
        从完整匹配中提取标签属性
        
        Args:
            full_match: 完整的标签匹配文本，如 '<card name="MenuCards">content</card>'
        
        Returns:
            dict: 属性字典，如 {'name': 'MenuCards'}
        """
        attributes = {}
        
        # 匹配开始标签中的属性
        start_tag_pattern = r'<(\w+)([^>]*)>'
        match = re.match(start_tag_pattern, full_match)
        
        if match:
            tag_name = match.group(1)
            attrs_string = match.group(2)
            
            # 提取属性键值对
            attr_pattern = r'(\w+)\s*=\s*["\']([^"\']*)["\']'
            for attr_match in re.finditer(attr_pattern, attrs_string):
                attr_name = attr_match.group(1)
                attr_value = attr_match.group(2)
                attributes[attr_name] = attr_value
        
        return attributes


    def parse_content(self, content):
        """
        解析内容，找到所有标签并记录位置和顺序
        
        Returns:
            list: [{'type': 'text'/'tag', 'content': '...', 'tag_name': '...', 'start': pos, 'end': pos}]
        """
        segments = []
        last_pos = 0
        
        # 找到所有标签的位置
        all_matches = []
        
        for tag_name, pattern in TAG_PATTERNS.items():
            for match in re.finditer(pattern, content, re.DOTALL):
                attributes = self._extract_attributes(full_match=match.group(0))
                all_matches.append({
                    'tag_name': tag_name,
                    'start': match.start(),
                    'end': match.end(),
                    'full_match': match.group(0),
                    'inner_content': match.group(1).strip(),
                    'attributes': attributes
                })
        
        # 按位置排序
        all_matches.sort(key=lambda x: x['start'])
        
        # 构建分段内容
        for match in all_matches:
            # 添加标签前的文本内容
            if last_pos < match['start']:
                text_content = content[last_pos:match['start']].strip()
                if text_content:
                    segments.append({
                        'type': 'text',
                        'content': text_content,
                        'start': last_pos,
                        'end': match['start']
                    })
            
            # 添加标签内容
            segments.append({
                'type': 'tag',
                'tag_name': match['tag_name'],
                'content': match['inner_content'],
                'full_match': match['full_match'],
                'start': match['start'],
                'end': match['end'],
                'attributes': match['attributes']
            })
            
            last_pos = match['end']
        
        # 添加最后剩余的文本
        if last_pos < len(content):
            remaining_text = content[last_pos:].strip()
            if remaining_text:
                segments.append({
                    'type': 'text',
                    'content': remaining_text,
                    'start': last_pos,
                    'end': len(content)
                })
        
        return segments
    
    


    def init_directory(self, directory: str, delete_flag: int = 0):
        """_summary_

        Args:
            directory (str): the directory path.
            delete_flag (int, optional): whether delete all the files in the exist directory. Defaults to 0.

        Returns:
            _type_: (bool, error_info/success_info)
        """
        try:
            if os.path.exists(directory) and delete_flag == 1:
                shutil.rmtree(directory)
            if not os.path.exists(directory):
                os.makedirs(directory) 
                os.chmod(directory, 0o2755) # 设置setgid位
            return True, f"success to init the directory: {directory}！"
        except Exception as e:
            error_info = f"fail to init the directory: {directory}\n{str(e)}！\n{traceback.format_exc()}"
            logger.error(error_info)
            return False, error_info
    
    def get_files_based_extension(self, directory, file_extension: str):
        """list all the file with the file_extension, no recursive

        Args:
            directory (_type_): _description_
            file_extension (str): file extension just like '.txt'

        Returns:
            _type_: (bool, error_info/list)
        """
        try:
            txt_files = []
            for file in os.listdir(directory):
                if file.endswith(file_extension):
                    txt_files.append(os.path.join(directory, file))
        except Exception as e:
            error_info = self.get_error_info(f"fail to get the extention: {file_extension} file！", e)
            logger.error(error_info)
            return False, error_info
        return True, txt_files

    def count_chinese_characters(self, text):
        try:
            chinese_char_pattern = r'[\u4e00-\u9fff]'
            chinese_chars = re.findall(chinese_char_pattern, text)
        except Exception as e:
            error_info = self.get_error_info("fail to count chinese characters!", e)
            logger.error(error_info)
            return False, error_info
        return True, len(chinese_chars)

    def count_english_words(self, text):
        try:
            words = re.findall(r'\b\w+\b', text)
        except Exception as e:
            error_info = self.get_error_info("fail to count english characters!", e)
            logger.error(error_info)
            return False, error_info
        return True, len(words)

    def read_yaml(self, yaml_file: str):
        try:
            with open(yaml_file, 'r', encoding='utf-8') as file:
                config = yaml.safe_load(file)
        except Exception as e:
            raise ValueError('fail to load yaml file!') from e
        return config
    
    def sort_two_list(self, list_one: Optional[list[list[int, int], list[int]]] = None, list_two: Optional[list[list[int, int], list[int]]] = None):
        """
        combined two list and rerank them. each list involved one timestamp range list and correspond label list.
        rerank the timestamp range list and rerank the correspond label list.
        """
        try:
            timestamp_range = list_one[0]
            timestamp_range.extend(list_two[0])
            label_value = list_one[1]
            label_value.extend(list_two[1])
            combined_data = list(zip(timestamp_range, label_value))
            combined_data.sort(key=lambda x: x[0][0])
            timestamps = set()
            for (start, end), _ in combined_data:
                timestamps.add(start)
                timestamps.add(end)
            timestamps = sorted(list(timestamps))
            result = []
            for i in range(len(timestamps) - 1):
                current_time = timestamps[i]
                next_time = timestamps[i + 1]
                active_intervals = []
                for (start, end), value in combined_data:
                    if start <= current_time and end >= next_time:
                        active_intervals.append((value, start))
                if active_intervals:
                    # Sort by start time in descending order
                    active_intervals.sort(key=lambda x: x[1], reverse=True)
                    value = active_intervals[0][0]
                    result.append(([current_time, next_time], value))        
                
            merged_result = []
            for interval in result:
                if (merged_result and 
                    merged_result[-1][1] == interval[1] and 
                    merged_result[-1][0][1] == interval[0][0]):
                    merged_result[-1] = ([merged_result[-1][0][0], interval[0][1]], interval[1])
                else:
                    merged_result.append(interval)
                    
            sorted_timestamps, sorted_labels = zip(*merged_result)
        except Exception as e:
            logger.error(traceback.print_exc())
            raise ValueError('fail to exec sort two list function!') from e
        return [sorted_timestamps, sorted_labels]
        
    
    def remove_stopwords(self, text, stop_words):
        words = jieba.cut(text)
        filtered_words = [word for word in words if word not in stop_words]
        return ''.join(filtered_words).replace(' ', '')
        
    
    def clean_text(self, text):
        try:
            cleaned_text = re.sub(r'https?://[^\s]+|www\.[^\s]+', '', text)
            cleaned_text = re.sub(r'<[^>]*>', '', cleaned_text)
            cleaned_text = re.sub(r'[^A-Za-z0-9\u4e00-\u9fa5\s,.!?，。！？；：""''()《》【】（）<>{}]+', '', cleaned_text)
            cleaned_text = re.sub(r'\s+', ' ', cleaned_text)
            cleaned_text = re.sub(r'([,.!?，。！？；：""''()《》【】（）<>{}])\1+', r'\1', cleaned_text)
            cleaned_text = re.sub(r'[A-Za-z0-9]{9,}', '', cleaned_text)
            cleaned_text = cleaned_text.strip()
        except Exception as e:
            raise ValueError("fail to exec clean_text function!") from e
        return cleaned_text
    
    
    def create_sliding_windows(
            self, 
            data, 
            window_size=20, 
            step_size=1, 
            field_index=None
        ):
        """
        创建滑动窗口数据
        
        Args:
            data: numpy数组，可以是1D或2D
                - 如果是1D: 直接对该数组做滑动窗口
                - 如果是2D: 需要指定field_index来选择列
            window_size: 窗口大小，默认20
            step_size: 滑动步长，默认1
            field_index: 当data是2D时，指定要处理的列索引
        
        Returns:
            windows: shape为(n_windows, window_size)的numpy数组
        """
        
        # 处理输入数据
        if data.ndim == 1:
            # 1D数据，直接使用
            time_series = data
        elif data.ndim == 2:
            # 2D数据，需要选择列
            if field_index is None:
                raise ValueError("对于2D数据，必须指定field_index")
            time_series = data[:, field_index]
        else:
            raise ValueError("数据维度不支持，只支持1D或2D数组")
        
        # 计算窗口数量
        n_samples = len(time_series)
        n_windows = (n_samples - window_size) // step_size + 1
        
        if n_windows <= 0:
            raise ValueError(f"数据长度({n_samples})小于窗口大小({window_size})")
        
        # 创建滑动窗口
        windows = np.zeros((n_windows, window_size))
        
        for i in range(n_windows):
            start_idx = i * step_size
            end_idx = start_idx + window_size
            windows[i] = time_series[start_idx:end_idx]
        return windows


    def format_notices_data_markdown(self, type, data_list):
        if not data_list:
            return f"暂无{type}信息"
        
        type_icon = {
            "通告": "📢",
            "时讯消息": "📋"
        }
        # 创建Markdown表格
        markdown_table = f"### {type_icon[type]} 最近的{type}\n\n"
        markdown_table += "| ID | 类型 | 内容 | 发布时间 |\n"
        markdown_table += "|----|----|----|---------|\n"
        
        for i, item in enumerate(data_list, 1):
            item_id = str(item.get('id', i))
            
            # 格式化时间
            create_time = item.get('create_time', '未知时间')
            if 'T' in create_time:
                date_part, time_part = create_time.split('T')
                time_part = time_part.split('.')[0] if '.' in time_part else time_part
                formatted_time = f"{date_part} {time_part}"
            else:
                formatted_time = create_time
            
            content = item.get('content', '无内容')
            item_type = item.get('type', '未知')
            
            # 处理内容中的特殊字符，避免破坏表格格式
            content = content.replace('|', '\\|').replace('\n', ' ')
            
            markdown_table += f"| {item_id} | {item_type} | {content} | {formatted_time} |\n"
        
        return markdown_table



    def format_notices_data_rich(self, type, data_list):
        if not data_list:
            return f"暂无{type}信息"
    
        # 创建表格
        table = Table(title=f"📋 {type}信息", show_header=True, header_style="bold magenta")
        table.add_column("ID", style="cyan", no_wrap=True)
        table.add_column("类型", style="green")
        table.add_column("内容", style="yellow")
        table.add_column("发布时间", style="blue")
        
        for i, item in enumerate(data_list, 1):
            item_id = str(item.get('id', i))
            
            # 格式化时间
            create_time = item.get('create_time', '未知时间')
            if 'T' in create_time:
                date_part, time_part = create_time.split('T')
                time_part = time_part.split('.')[0] if '.' in time_part else time_part
                formatted_time = f"{date_part} {time_part}"
            else:
                formatted_time = create_time
            
            content = item.get('content', '无内容')
            item_type = item.get('type', '未知')
            
            table.add_row(item_id, item_type, content, formatted_time)
        
        # 渲染为字符串
        console = Console(file=StringIO(), width=80)
        console.print(table)
        return console.file.getvalue()
    
    
    def convert_to_column_format(self, data_list, key_mapping=None):
        """
        将对象数组格式转换为列格式数据，可选择性应用字段映射
        
        Args:
            data_list (list): 对象数组，每个字典代表一行数据
            key_mapping (dict, optional): 字段名映射字典。如果不传递则保持原字段名
        
        Returns:
            dict: 列格式的字典，键为字段名，值为对应的数据列表
        
        Examples:
            >>> # 不使用映射
            >>> data_list = [{"name": "Alice", "age": 25}, {"name": "Bob", "age": 30}]
            >>> result = convert_to_column_format(data_list)
            >>> print(result)
            {"name": ["Alice", "Bob"], "age": [25, 30]}
            
            >>> # 使用映射
            >>> mapping = {"name": "姓名", "age": "年龄"}
            >>> result = convert_to_column_format(data_list, mapping)
            >>> print(result)
            {"姓名": ["Alice", "Bob"], "年龄": [25, 30]}
        """
        if not data_list:
            return {}
        
        # 从第一个对象获取所有字段名
        fields = list(data_list[0].keys())
        
        # 创建结果字典
        result = {}
        
        for field in fields:
            # 提取该字段在所有对象中的值
            values = [item.get(field, "") for item in data_list]
            
            # 如果提供了映射，使用映射后的字段名，否则使用原字段名
            if key_mapping and field in key_mapping:
                field_name = key_mapping[field]
            else:
                field_name = field
            
            # 存储到结果中
            result[field_name] = values
        
        return result
    
    
    
    def convert_to_chinese_fields(self, data_list, key_mapping):
        """
        将英文字段的数据转换为中文字段的字典列表
        
        Args:
            data_list: 原始数据列表，包含英文字段
            key_mapping: 英文字段到中文字段的映射字典
        
        Returns:
            转换后的中文字段字典列表
        """
        chinese_data_list = []
        
        for item in data_list:
            chinese_item = {}
            for english_key, chinese_key in key_mapping.items():
                if english_key in item:
                    chinese_item[chinese_key] = item[english_key]
            chinese_data_list.append(chinese_item)
        
        return chinese_data_list