#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time    : 2025/09/23 09:22
@Author  : weiyutao
@File    : mqtt_client.py
"""
import time
import threading
import json
import struct
from typing import Optional, Callable, Dict, Any, List, Literal
import paho.mqtt.client as mqtt
from datetime import datetime
import queue
from collections import deque
from enum import Enum


from agent.base.base_tool import tool


@tool
class MQTTClient:
    """MQTT客户端，与SocketServer具有相同的接口和功能"""
    
    def __init__(
        self,
        broker_host: str,
        broker_port: int = 8083,
        topics: List[str] = None,
        data_callback: Callable[[Dict[str, Any]], None] = None,
        device_sn_call_back: Callable[[Dict[str, Any]], None] = None,
        injected_data: Optional[list] = None,
        device_sn: Optional[str] = None,
        client_id: str = None,
        username: str = "admin",  # 新增用户名参数
        password: str = "sxkj@123456",  # 新增密码参数
        websocket_path: str = "/mqtt"  # 新增WebSocket路径参数
    ):
        """
        初始化MQTT客户端
        
        Args:
            broker_host (str): MQTT服务器地址
            broker_port (int): MQTT服务器端口
            topics (List[str]): 订阅的主题列表
            data_callback: 数据回调函数
            device_sn_call_back: 设备序列号回调函数
            injected_data: 注入的测试数据
            device_sn: 设备序列号
            client_id: MQTT客户端ID
            username: MQTT认证用户名
            password: MQTT认证密码
            websocket_path: WebSocket路径
        """
        super().__init__()
        self.broker_host = broker_host
        self.broker_port = broker_port
        self.topics = topics or []
        self.data_callback = data_callback
        self.device_sn_call_back = device_sn_call_back
        self.injected_data = injected_data
        self.device_sn = device_sn
        self.username = username
        self.password = password
        self.websocket_path = websocket_path
        
        self.last_log_time = 0
        self.log_interval = 10  # 10秒间隔 ← 在这里修改
        self.message_count = 0  # 消息计数器
        
        # 状态管理
        self.is_running = False
        self.connected = False
        
        # MQTT客户端
        self.mqtt_client = None
        self.client_id = client_id or f"mqtt_client_{int(time.time())}"
        
        # 线程管理
        self.connect_thread = None
        self.inject_thread = None
        
        # 数据缓存
        self.data_buffer = queue.Queue(maxsize=100)
        self.debug_messages = deque(maxlen=50)
        self.devices = {}
        
        # 线程锁
        self.lock = threading.Lock()
        
        self.logger.info(f"MQTT client initialized for WebSocket connection to {broker_host}:{broker_port}{websocket_path}")


    def log_debug(self, message):
        """线程安全的日志记录"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        debug_message = f"[{timestamp}] {message}"
        with self.lock:
            self.debug_messages.append(debug_message)
        self.logger.info(debug_message)


    def _initialize_mqtt(self):
        """初始化MQTT客户端（WebSocket版本）"""
        try:
            # 创建MQTT客户端，指定使用WebSocket传输
            self.mqtt_client = mqtt.Client(
                client_id=self.client_id,
                transport="websockets"  # 使用WebSocket传输
            )
            
            # 设置回调函数
            self.mqtt_client.on_connect = self._on_connect
            self.mqtt_client.on_message = self._on_message
            self.mqtt_client.on_disconnect = self._on_disconnect
            
            # 设置用户名和密码
            if self.username and self.password:
                self.mqtt_client.username_pw_set(self.username, self.password)
                self.log_debug(f"设置MQTT认证信息: 用户名={self.username}")
            
            # 设置WebSocket路径
            self.mqtt_client.ws_set_options(path=self.websocket_path, headers=None)
            
            self.log_debug(f"连接MQTT WebSocket服务器 ws://{self.broker_host}:{self.broker_port}{self.websocket_path}")
            
            # 连接到MQTT服务器
            self.mqtt_client.connect(self.broker_host, self.broker_port, 60)
            self.mqtt_client.loop_start()
            
        except Exception as e:
            self.log_debug(f"MQTT WebSocket初始化失败: {e}")
            raise


    def _on_connect(self, client, userdata, flags, rc):
        """MQTT连接回调（增强版）"""
        connection_results = {
            0: "连接成功",
            1: "协议版本不支持", 
            2: "客户端ID被拒绝",
            3: "服务器不可用",
            4: "用户名/密码错误", 
            5: "未授权",
            7: "连接被拒绝"
        }
        
        result_msg = connection_results.get(rc, f"未知错误({rc})")
        self.log_debug(f"MQTT WebSocket连接结果: {rc} - {result_msg}")
        
        if rc == 0:
            self.connected = True
            self.log_debug("MQTT WebSocket连接成功，开始订阅主题...")
            for topic in self.topics:
                result, mid = client.subscribe(topic)
                self.log_debug(f"订阅主题 '{topic}': result={result}, mid={mid}")
        else:
            self.connected = False
            self.log_debug(f"MQTT WebSocket连接失败: {result_msg}")


    def _on_disconnect(self, client, userdata, rc):
        """MQTT断开连接回调"""
        self.connected = False
        self.log_debug(f"MQTT WebSocket连接断开: {rc}")


    # ... 其他方法保持不变 ...
    def _on_message(self, client, userdata, msg):
        """MQTT消息处理（更新版本支持UART格式）"""
        try:
            current_time = time.time()
            current_time_str = datetime.fromtimestamp(current_time).strftime("%H:%M:%S")
            
            
            # 消息计数器递增
            self.message_count += 1
            
            
            # 检查是否需要打印日志（每10秒打印一次）
            should_log = (current_time - self.last_log_time) >= self.log_interval  # ← 在这里使用
            
            if should_log:
                # 基本信息日志
                self.log_debug(f"收到MQTT消息! 主题: {msg.topic}, 长度: {len(msg.payload)}, {current_time_str}")

                # # 如果是UART格式数据，显示详细调试信息
                # if len(msg.payload) == 66 and self._is_uart_format(msg.payload):
                #     uart_debug = self._parse_uart_debug_info(msg.payload)
                #     if should_log:
                #         self.log_debug(f"UART数据详情: {uart_debug}")
                self.last_log_time = current_time
                self.message_count = 0

            # 解析数据
            parse_data = self._parse_mqtt_data(msg.payload, msg.topic)
            
            if parse_data:
                if should_log:
                    self.logger.info(f"解析后数据: {parse_data}")
                if self.data_callback is not None and callable(self.data_callback):
                    self.data_callback(parse_data)
            
        except Exception as e:
            self.log_debug(f"处理MQTT消息时出错: {e}")


    def _parse_mqtt_data(self, payload, topic):
        """解析MQTT数据，主要支持UART格式数据"""
        try:
            timestamp = int(time.time())
            
            # 优先检查UART格式数据（66字节，包含Odata和Bdata标识）
            if len(payload) == 66 and self._is_uart_format(payload):
                return self._parse_uart_payload(payload, topic, timestamp)
            
            # 如果不是UART格式，尝试JSON解析
            try:
                data = json.loads(payload.decode('utf-8'))
                return self._parse_json_payload(data, topic, timestamp)
            except (json.JSONDecodeError, UnicodeDecodeError):
                # 最后尝试原始数据处理
                self.logger.warning(f"未识别的数据格式，长度: {len(payload)}")
                return self._parse_raw_payload(payload, topic, timestamp)
                    
        except Exception as e:
            self.logger.error(f"解析MQTT数据失败: {e}")
            return None


    def _is_uart_format(self, payload):
        """判断是否为UART格式数据"""
        try:
            # 检查前5字节是否为"Odata"
            if len(payload) >= 5:
                odata_header = payload[0:5]
                if odata_header == b'Odata':
                    return True
            
            # 检查是否在位置57处有"Bdata"
            if len(payload) >= 62:  # 57 + 5
                bdata_header = payload[57:62]
                if bdata_header == b'Bdata':
                    return True
                    
            return False
        except Exception:
            return False


    def _parse_uart_payload(self, payload, topic, timestamp):
        """解析UART格式的数据包"""
        try:
            # 验证数据长度
            if len(payload) != 66:
                self.logger.warning(f"UART数据长度不正确: {len(payload)}, 期望: 66")
                return None
            
            # 解析Odata部分（57字节）
            odata_part = payload[0:57]
            odata_header = odata_part[0:5]  # "Odata"
            
            if odata_header != b'Odata':
                self.logger.warning("未找到Odata标识")
                return None
            
            # 解析25个压电信号数据（每个2字节，有符号整数，低位在前）
            raw_piezo_values = []  # 存储原始十进制数值
            for i in range(25):
                start_idx = 5 + i * 2
                end_idx = start_idx + 2
                if end_idx <= 55:  # 确保不超出范围
                    # 低位在前，高位在后，有符号16位整数
                    raw_value = struct.unpack('<h', odata_part[start_idx:end_idx])[0]
                    raw_piezo_values.append(raw_value)  # 保存原始值
            
            
            # 归一化波形数据到-1到1范围（用于前端绘图）
            def normalize_to_minus1_1(data):
                """将原始压电信号归一化到-1到1范围"""
                if not data or len(data) == 0:
                    return []
                min_val = min(data)
                max_val = max(data)
                range_val = max_val - min_val if max_val != min_val else 1  # 避免除零
                # 先映射到0-1范围，再转换到-1到1范围
                return [2 * ((x - min_val) / range_val) - 1 for x in data]
            
            signal_data = normalize_to_minus1_1(raw_piezo_values)
            
            # 解析压阻信号（最后2字节，有符号整数，但有效范围0~4096）
            pressure_resistance = 0
            if len(odata_part) >= 57:
                pressure_resistance = struct.unpack('<h', odata_part[55:57])[0]
                # 确保在有效范围内
                if pressure_resistance < 0:
                    pressure_resistance = 0
                elif pressure_resistance > 4096:
                    pressure_resistance = 4096
            
            # 解析Bdata部分（9字节）
            bdata_part = payload[57:66]
            bdata_header = bdata_part[0:5]  # "Bdata"
            
            if bdata_header != b'Bdata':
                self.logger.warning("未找到Bdata标识")
                return None
            
            # 解析结果数据
            sequence_number = bdata_part[5]  # 序列号 0~59
            status_value = bdata_part[6]     # 状态值
            heart_rate = bdata_part[7]       # 心率
            breathing_rate_raw = bdata_part[8]  # 呼吸率原始值
            
            # 呼吸率需要除以10
            breathing_rate = breathing_rate_raw / 10.0
            
            # 状态值含义：
            # 0=在床, 1=离床, 2=体动, 3=弱呼吸, 4=重物, 5=打鼾
            # status_descriptions = {
            #     0: "在床", 1: "离床", 2: "体动", 
            #     3: "弱呼吸", 4: "重物", 5: "打鼾"
            # }
            
            # 根据状态判断在床情况
            in_bed = 1 if status_value == 0 else 0  # 0表示在床
            
            # 设备ID基于主题生成
            device_id = f"UART_{topic.replace('/', '_')}"
            
            # 记录详细信息
            # self.logger.info(f"UART数据解析 - 序列号: {sequence_number}, "
            #                 f"状态: {status_descriptions.get(status_value, '未知')}({status_value}), "
            #                 f"心率: {heart_rate}, 呼吸率: {breathing_rate}, "
            #                 f"压阻信号: {pressure_resistance}, "
            #                 f"归一化信号数量: {len(signal_data)}")
            
            # 返回与原格式兼容的数据结构
            return (
                timestamp,              # 时间戳
                breathing_rate,         # 呼吸率 (breath_bpm)
                raw_piezo_values,  # 呼吸曲线 (breath_curve) - 归一化后的值(-1到1)
                float(heart_rate),      # 心率 (heart_bpm)
                raw_piezo_values,  # 心率曲线 (heart_curve) - 归一化后的值(-1到1)
                0.0,                    # 目标距离 (target_distance) - UART格式中没有此数据
                float(pressure_resistance),  # 信号强度 (signal_strength) - 使用压阻信号
                int(status_value),      # 有效位ID (valid_bit_id) - 使用状态值
                0.0,                    # 体动能量 (body_move_energy) - UART格式中没有此数据
                0.0,                    # 体动范围 (body_move_range) - UART格式中没有此数据
                in_bed,                 # 在床状态
                device_id.upper()       # 设备ID
            )
            
        except Exception as e:
            self.logger.error(f"解析UART数据失败: {e}")
            return None


    def _parse_uart_payload_bake(self, payload, topic, timestamp):
        """解析UART格式的数据包"""
        try:
            # 验证数据长度
            if len(payload) != 66:
                self.logger.warning(f"UART数据长度不正确: {len(payload)}, 期望: 66")
                return None
            
            # 解析Odata部分（57字节）
            odata_part = payload[0:57]
            odata_header = odata_part[0:5]  # "Odata"
            
            if odata_header != b'Odata':
                self.logger.warning("未找到Odata标识")
                return None
            
            # 解析25个压电信号数据（每个2字节，有符号整数，低位在前）
            signal_data = []
            for i in range(25):
                start_idx = 5 + i * 2
                end_idx = start_idx + 2
                if end_idx <= 55:  # 确保不超出范围
                    # 低位在前，高位在后，有符号16位整数
                    value = struct.unpack('<h', odata_part[start_idx:end_idx])[0]
                    signal_data.append(value)
            
            # 解析压阻信号（最后2字节，有符号整数，但有效范围0~4096）
            pressure_resistance = 0
            if len(odata_part) >= 57:
                pressure_resistance = struct.unpack('<h', odata_part[55:57])[0]
                # 确保在有效范围内
                if pressure_resistance < 0:
                    pressure_resistance = 0
                elif pressure_resistance > 4096:
                    pressure_resistance = 4096
            
            # 解析Bdata部分（9字节）
            bdata_part = payload[57:66]
            bdata_header = bdata_part[0:5]  # "Bdata"
            
            if bdata_header != b'Bdata':
                self.logger.warning("未找到Bdata标识")
                return None
            
            # 解析结果数据
            sequence_number = bdata_part[5]  # 序列号 0~59
            status_value = bdata_part[6]     # 状态值
            heart_rate = bdata_part[7]       # 心率
            breathing_rate_raw = bdata_part[8]  # 呼吸率原始值
            
            # 呼吸率需要除以10
            breathing_rate = breathing_rate_raw / 10.0
            
            # 状态值含义：
            # 0=在床, 1=离床, 2=体动, 3=弱呼吸, 4=重物, 5=打鼾
            # status_descriptions = {
            #     0: "在床", 1: "离床", 2: "体动", 
            #     3: "弱呼吸", 4: "重物", 5: "打鼾"
            # }
            
            # 根据状态判断在床情况
            in_bed = 1 if status_value == 0 else 0  # 0表示在床
            
            # 设备ID基于主题生成
            device_id = f"UART_{topic.replace('/', '_')}"
            
            # 记录详细信息
            # self.logger.info(f"UART数据解析 - 序列号: {sequence_number}, "
            #                 f"状态: {status_descriptions.get(status_value, '未知')}({status_value}), "
            #                 f"心率: {heart_rate}, 呼吸率: {breathing_rate}, "
            #                 f"压阻信号: {pressure_resistance}")
            
            # 返回与原格式兼容的数据结构
            return (
                timestamp,              # 时间戳
                breathing_rate,         # 呼吸率 (breath_bpm)
                signal_data[0] if signal_data else 0.0,  # 呼吸曲线 (breath_curve) - 使用第一个压电信号
                float(heart_rate),      # 心率 (heart_bpm)
                signal_data[1] if len(signal_data) > 1 else 0.0,  # 心率曲线 (heart_curve) - 使用第二个压电信号
                0.0,                    # 目标距离 (target_distance) - UART格式中没有此数据
                float(pressure_resistance),  # 信号强度 (signal_strength) - 使用压阻信号
                int(status_value),      # 有效位ID (valid_bit_id) - 使用状态值
                0.0,                    # 体动能量 (body_move_energy) - UART格式中没有此数据
                0.0,                    # 体动范围 (body_move_range) - UART格式中没有此数据
                in_bed,                 # 在床状态
                device_id.upper()       # 设备ID
            )
            
        except Exception as e:
            self.logger.error(f"解析UART数据失败: {e}")
            return None


    def _parse_uart_debug_info(self, payload):
        """解析UART数据并返回调试信息"""
        try:
            if len(payload) != 66:
                return f"数据长度错误: {len(payload)}"
            
            debug_info = []
            
            # Odata部分信息
            odata_header = payload[0:5].decode('ascii', errors='ignore')
            debug_info.append(f"Odata标识: {odata_header}")
            
            # 压电信号采样（显示前5个）
            signals = []
            for i in range(min(5, 25)):
                start_idx = 5 + i * 2
                value = struct.unpack('<h', payload[start_idx:start_idx+2])[0]
                signals.append(str(value))
            debug_info.append(f"压电信号(前5个): {', '.join(signals)}")
            
            # 压阻信号
            pressure_resistance = struct.unpack('<h', payload[55:57])[0]
            debug_info.append(f"压阻信号: {pressure_resistance}")
            
            # Bdata部分信息
            bdata_header = payload[57:62].decode('ascii', errors='ignore')
            debug_info.append(f"Bdata标识: {bdata_header}")
            
            sequence_number = payload[62]
            status_value = payload[63]
            heart_rate = payload[64]
            breathing_rate_raw = payload[65]
            
            status_names = {0: "在床", 1: "离床", 2: "体动", 3: "弱呼吸", 4: "重物", 5: "打鼾"}
            
            debug_info.append(f"序列号: {sequence_number}")
            debug_info.append(f"状态: {status_names.get(status_value, '未知')}({status_value})")
            debug_info.append(f"心率: {heart_rate}")
            debug_info.append(f"呼吸率: {breathing_rate_raw/10.0}")
            
            return " | ".join(debug_info)
            
        except Exception as e:
            return f"调试信息解析失败: {e}"


    def _parse_json_payload(self, data, topic, timestamp):
        """解析JSON格式的数据"""
        try:
            # 将JSON数据转换为元组格式
            breath_bpm = float(data.get('breath_bpm', 0))
            breath_curve = float(data.get('breath_curve', 0))
            heart_bpm = float(data.get('heart_bpm', 0))
            heart_curve = float(data.get('heart_curve', 0))
            target_distance = float(data.get('target_distance', 0))
            signal_strength = float(data.get('signal_strength', 0))
            valid_bit_id = int(data.get('valid_bit_id', 0))
            body_move_energy = float(data.get('body_move_energy', 0))
            body_move_range = float(data.get('body_move_range', 0))
            in_bed = int(data.get('in_bed', 0))
            device_id = data.get('device_id', f"MQTT_{topic.replace('/', '_')}")
            
            return (
                timestamp,
                breath_bpm,
                breath_curve,
                heart_bpm,
                heart_curve,
                target_distance,
                signal_strength,
                valid_bit_id,
                body_move_energy,
                body_move_range,
                in_bed,
                device_id.upper()
            )
            
        except Exception as e:
            self.logger.error(f"解析JSON MQTT数据失败: {e}")
            return None


    def _parse_raw_payload(self, payload, topic, timestamp):
        """解析原始字节数据"""
        try:
            # 简单的原始数据处理
            hex_data = payload.hex().upper()
            device_id = f"MQTT_{topic.replace('/', '_')}"
            
            # 创建默认数据结构
            return (
                timestamp,
                0.0,  # breath_bpm
                0.0,  # breath_curve
                0.0,  # heart_bpm
                0.0,  # heart_curve
                0.0,  # target_distance
                0.0,  # signal_strength
                0,    # valid_bit_id
                0.0,  # body_move_energy
                0.0,  # body_move_range
                0,    # in_bed
                device_id.upper()
            )
            
        except Exception as e:
            self.logger.error(f"解析原始MQTT数据失败: {e}")
            return None


    def start(self):
        """启动MQTT客户端"""
        if self.is_running:
            self.logger.warning(f"MQTT WebSocket client for {self.broker_host}:{self.broker_port} is already running!")
            return
            
        self.is_running = True
        
        if self.injected_data is None:
            # 正常MQTT模式
            self.connect_thread = threading.Thread(target=self._start_mqtt_connection)
            self.connect_thread.daemon = True
            self.connect_thread.start()
            self.logger.info(f"MQTT WebSocket client started for {self.broker_host}:{self.broker_port}")
        else:
            # 注入数据模式
            self.inject_thread = threading.Thread(target=self._handle_injected_data)
            self.inject_thread.daemon = True
            self.inject_thread.start()
            self.logger.info("MQTT WebSocket client started (injected data mode)")


    def _start_mqtt_connection(self):
        """启动MQTT连接"""
        try:
            self._initialize_mqtt()
            # 保持连接
            while self.is_running:
                time.sleep(1)
        except Exception as e:
            self.logger.error(f"MQTT WebSocket连接线程异常: {e}")


    def _handle_injected_data(self):
        """处理注入的数据列表"""
        try:
            for data in self.injected_data:
                if not self.is_running:
                    break
                    
                parse_data = data
                if parse_data:
                    if self.data_callback is not None and callable(self.data_callback):
                        self.data_callback(parse_data)
                        
                time.sleep(0.1)  # 模拟数据间隔
                
        except Exception as e:
            self.logger.error(f"处理注入MQTT数据失败: {e}")
        finally:
            self.logger.info("完成处理所有注入的MQTT数据")


    def stop(self):
        """停止MQTT客户端"""
        if not self.is_running:
            return
            
        self.is_running = False
        
        if self.mqtt_client and self.connected:
            try:
                self.mqtt_client.loop_stop()
                self.mqtt_client.disconnect()
            except Exception as e:
                self.logger.error(f"断开MQTT WebSocket连接失败: {e}")
        
        # 等待线程结束
        if self.connect_thread and self.connect_thread.is_alive():
            self.connect_thread.join(timeout=2)
            
        if self.inject_thread and self.inject_thread.is_alive():
            self.inject_thread.join(timeout=2)
            
        self.logger.info(f"MQTT WebSocket client for {self.broker_host}:{self.broker_port} stopped!")


    def is_connected(self):
        """检查连接状态"""
        return self.connected


    def get_debug_messages(self):
        """获取调试消息"""
        with self.lock:
            return list(self.debug_messages)


    
    def add_topic(self, topic: str) -> bool:
        """
        添加并订阅单个topic
        
        Args:
            topic: 要添加的topic
            
        Returns:
            bool: 订阅是否成功
        """
        if not self.connected:
            self.logger.warning("MQTT客户端未连接，无法添加topic")
            return False
        
        if topic in self.topics:
            self.log_debug(f"Topic已存在: {topic}")
            return True  # 已经订阅
        
        try:
            result, mid = self.mqtt_client.subscribe(topic)
            if result == mqtt.MQTT_ERR_SUCCESS:
                self.topics.append(topic)
                self.log_debug(f"成功订阅topic: {topic}")
                return True
            else:
                self.log_debug(f"订阅topic失败: {topic}, 错误码: {result}")
                self.update_subscription_status(topic=topic, subscription_status="failed")
                return False
        except Exception as e:
            self.log_debug(f"订阅topic异常: {topic}, 错误: {e}")
            return False


    def remove_topic(self, topic: str) -> bool:
        """
        取消订阅单个topic
        
        Args:
            topic: 要移除的topic
            
        Returns:
            bool: 取消订阅是否成功
        """
        if not self.connected:
            self.logger.warning("MQTT客户端未连接，无法移除topic")
            return False
        
        if topic not in self.topics:
            self.log_debug(f"Topic不存在: {topic}")
            return True  # 本来就不存在
        
        try:
            result, mid = self.mqtt_client.unsubscribe(topic)
            if result == mqtt.MQTT_ERR_SUCCESS:
                self.topics.remove(topic)
                self.log_debug(f"成功取消订阅topic: {topic}")
                return True
            else:
                self.log_debug(f"取消订阅topic失败: {topic}, 错误码: {result}")
                return False
        except Exception as e:
            self.log_debug(f"取消订阅topic异常: {topic}, 错误: {e}")
            return False


    def add_topics_batch(self, new_topics: List[str]) -> Dict[str, bool]:
        """
        批量添加并订阅新的topics
        
        Args:
            new_topics: 要添加的topic列表
            
        Returns:
            Dict[str, bool]: {topic: 订阅是否成功}
        """
        results = {}
        
        for topic in new_topics:
            results[topic] = self.add_topic(topic)
        
        return results
    
    
    def remove_topics_batch(self, topics_to_remove: List[str]) -> Dict[str, bool]:
        """
        批量取消订阅topics
        
        Args:
            topics_to_remove: 要移除的topic列表
            
        Returns:
            Dict[str, bool]: {topic: 取消订阅是否成功}
        """
        results = {}
        
        for topic in topics_to_remove:
            results[topic] = self.remove_topic(topic)
        
        return results
    
    
    def get_subscribed_topics(self) -> List[str]:
        """
        获取当前订阅的topics列表
        
        Returns:
            List[str]: 当前订阅的topic列表
        """
        return self.topics.copy()
    
    
    def sync_topics(self, target_topics: List[str]) -> Dict[str, Any]:
        """
        同步topics到目标列表
        
        Args:
            target_topics: 目标topic列表
            
        Returns:
            Dict: 同步结果
        """
        current_topics = set(self.topics)
        target_topics_set = set(target_topics)
        
        # 需要添加的topics
        topics_to_add = list(target_topics_set - current_topics)
        # 需要移除的topics
        topics_to_remove = list(current_topics - target_topics_set)
        
        add_results = {}
        remove_results = {}
        
        if topics_to_add:
            add_results = self.add_topics_batch(topics_to_add)
            self.log_debug(f"添加topics结果: {add_results}")
        
        if topics_to_remove:
            remove_results = self.remove_topics_batch(topics_to_remove)
            self.log_debug(f"移除topics结果: {remove_results}")
        
        return {
            'added': add_results,
            'removed': remove_results,
            'current_topics': self.get_subscribed_topics(),
            'target_topics': target_topics,
            'sync_success': all(add_results.values()) and all(remove_results.values())
        }


    def execute(self):
        """执行方法，与SocketServer保持一致"""
        pass


if __name__ == '__main__':
    # 测试用例 - 根据您的配置更新
    from pathlib import Path
    from agent.config.sql_config import SqlConfig
    ROOT_DIRECTORY = Path(__file__).parent.parent
    MQTT_CONFIG_PATH = str(ROOT_DIRECTORY / "config" / "yaml" / "mqtt_config.yaml")
    mqtt_config = SqlConfig.from_file(MQTT_CONFIG_PATH)
    def test_callback(data):
        print(f"收到数据: {data}")
    
    mqtt_client = MQTTClient(
        broker_host=mqtt_config.host,  # 从您的配置中获取
        broker_port=mqtt_config.port,           # 从您的配置中获取
        topics=[
            "/topic/sx_sleep_heart_rate_lg_02_odata"
        ],
        data_callback=test_callback,
        username=mqtt_config.username,           # 从您的配置中获取
        password=mqtt_config.password,     # 从您的配置中获取
        websocket_path=mqtt_config.database_type      # 从您的配置中获取
    )
    
    mqtt_client.start()
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        mqtt_client.stop()