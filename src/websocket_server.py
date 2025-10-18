#!/usr/bin/env python3
"""
WebSocket Redis Bridge Service
从 Redis 订阅实时数据并通过 WebSocket 转发给前端
"""

import asyncio
import json
import logging
import signal
import time
import uuid
from datetime import datetime
from typing import Dict, Set, Optional, Any
from urllib.parse import parse_qs, urlparse
import weakref
from pathlib import Path
import ssl

import websockets
import redis.asyncio as redis
from websockets.exceptions import ConnectionClosed, WebSocketException

from base.base_tool import BaseTool
from agent.base.tool import tool
from agent.config.sql_config import SqlConfig

redis_channel = 'websocket_realtime'
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] [%(name)s] - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

class WebSocketClient:
    """WebSocket 客户端包装类"""

    def __init__(self, websocket, client_id: str, ip: str, device_id: Optional[str] = None):
        self.websocket = websocket
        self.client_id = client_id
        self.ip = ip
        self.device_id = device_id
        self.connected_at = datetime.now()
        self.last_ping = datetime.now()
        self.user_agent = None
        self.logger = logging.getLogger(__name__)

    async def send(self, message: Dict[str, Any]) -> bool:
        """发送消息给客户端"""
        try:
            await self.websocket.send(json.dumps(message))
            return True
        except (ConnectionClosed, WebSocketException) as e:
            self.logger.warning(f"发送消息失败 {self.client_id}: {e}")
            return False
        except Exception as e:
            self.logger.error(f"发送消息错误 {self.client_id}: {e}")
            return False
    
    
    async def ping(self) -> bool:
        """发送心跳"""
        try:
            await self.websocket.ping()
            return True
        except Exception as e:
            self.logger.warning(f"心跳失败 {self.client_id}: {e}")
            return False
    
    
    def is_alive(self) -> bool:
        """检查连接是否活跃（兼容所有websockets版本的正确方式）"""
        from websockets.connection import State
        
        # 检查连接状态是否为 OPEN
        return self.websocket.state == State.OPEN
    
    
    def update_ping(self):
        """更新最后心跳时间"""
        self.last_ping = datetime.now()


class WebSocketRedisBridge:
    """WebSocket Redis 桥接服务"""
    
    def __init__(
        self, 
        redis_config: SqlConfig = None, 
        websocket_config: SqlConfig = None,
        ssl_cert_path: str = None, 
        ssl_key_path: str = None
    ):
        # 配置
        self.redis_config = redis_config
        self.websocket_config = websocket_config
        if self.redis_config is None:
            raise ValueError("redis_config must not be null!")
        if self.websocket_config is None:
            raise ValueError("websocket_config must not be null!")
        # 状态
        self.clients: Dict[str, WebSocketClient] = {}
        self.redis_client = None
        self.pubsub = None
        self.running = False
        self.heartbeat_task = None
        self.redis_task = None
        self.ssl_cert_path = ssl_cert_path
        self.ssl_key_path = ssl_key_path
        
        self.ip_connections = dict()  # 记录每个IP的连接数
        self.max_connections_per_ip = 10  # 每个IP最大允许2个连接
        
        self.logger = logging.getLogger(__name__)


    def create_ssl_context(self):
        """创建SSL上下文"""
        if not self.ssl_cert_path or not self.ssl_key_path:
            self.logger.error("❌ SSL启用但证书路径未提供")
            raise ValueError("SSL证书路径必须提供")
            
        # 检查证书文件是否存在
        cert_path = Path(self.ssl_cert_path)
        key_path = Path(self.ssl_key_path)
        
        if not cert_path.exists():
            raise FileNotFoundError(f"SSL证书文件不存在: {cert_path}")
        if not key_path.exists():
            raise FileNotFoundError(f"SSL私钥文件不存在: {key_path}")
            
        self.logger.info(f"🔒 加载SSL证书: {cert_path}")
        self.logger.info(f"🔑 加载SSL私钥: {key_path}")
        
        # 创建SSL上下文
        ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        
        try:
            ssl_context.load_cert_chain(
                certfile=str(cert_path),
                keyfile=str(key_path)
            )
            
            # 可选：设置其他SSL选项
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            
            self.logger.info("✅ SSL上下文创建成功")
            return ssl_context
            
        except Exception as e:
            self.logger.error(f"❌ SSL上下文创建失败: {e}")
            raise


    async def start(self):
        """启动服务"""
        self.logger.info("🚀 启动 WebSocket Redis Bridge 服务...")
        
        try:
            # 初始化 Redis 连接
            await self.init_redis()
            
            # 创建SSL上下文
            ssl_context = self.create_ssl_context()
            
            # 启动 WebSocket 服务器
            self.running = True
            
            # 启动心跳任务
            self.heartbeat_task = asyncio.create_task(self.heartbeat_loop())
            
            # 启动 Redis 订阅任务
            self.redis_task = asyncio.create_task(self.redis_subscribe_loop())
            
            # 启动 WebSocket 服务器
            server_kwargs = {
                'host': self.websocket_config.host,
                'port': self.websocket_config.port,
                'ping_interval': 20,
                'ping_timeout': 10,
            }
            
            if ssl_context:
                server_kwargs['ssl'] = ssl_context
            server = await websockets.serve(
                self.handle_websocket_connection,
                **server_kwargs
            )
            
            self.logger.info(f"📡 WebSocket 服务: wss://{self.websocket_config.host}:{self.websocket_config.port}")
            self.logger.info(f"🔗 Redis 连接: {self.redis_config.host}:{self.redis_config.port}")
            self.logger.info(f"📢 订阅频道: {redis_channel}")
            self.logger.info("✅ 服务启动成功!")
            
            # 保持服务运行
            await server.wait_closed()
            
        except Exception as e:
            self.logger.error(f"❌ 服务启动失败: {e}")
            raise
    
    
    async def init_redis(self):
        """初始化 Redis 连接"""
        self.logger.info("🔌 正在连接 Redis...")
        
        try:
            self.redis_client = redis.Redis(
                host=self.redis_config.host,
                port=self.redis_config.port,
                db=self.redis_config.database,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_keepalive=True,
                health_check_interval=30,
            )
            
            # 测试连接
            await self.redis_client.ping()
            self.logger.info("✅ Redis 连接成功")
            
            # 创建订阅客户端
            self.pubsub = self.redis_client.pubsub()
            await self.pubsub.subscribe(redis_channel)
            self.logger.info(f"📢 成功订阅频道: {redis_channel}")
            
        except Exception as e:
            self.logger.error(f"❌ Redis 连接失败: {e}")
            raise
    
    
    
    async def handle_websocket_connection(self, websocket):
        client_ip = websocket.remote_address[0] if websocket.remote_address else 'unknown'
        
        # 检查IP连接数限制
        current_connections = self.ip_connections.get(client_ip, 0)
        if current_connections >= self.max_connections_per_ip:
            self.logger.warning(f"❌ 拒绝连接 - IP {client_ip} 已达到最大连接数({self.max_connections_per_ip})")
            await websocket.close(code=1008, reason="Too many connections from this IP")
            return
        
        # 增加IP连接计数
        self.ip_connections[client_ip] = current_connections + 1
        self.logger.info(f"📊 IP {client_ip} 连接数: {self.ip_connections[client_ip]}")
        
        client_id = self.generate_client_id()
        
        # 解析查询参数（保持不变）
        device_id = None
        path = websocket.request.path
        if path and '?' in path:
            query_params = parse_qs(urlparse(path).query)
            if 'device_id' in query_params:
                device_id = query_params['device_id'][0]
        
        # 创建客户端对象（保持不变）
        client = WebSocketClient(websocket, client_id, client_ip, device_id)
        self.clients[client_id] = client
        
        device_info = f" [设备: {device_id}]" if device_id else ""
        self.logger.info(f"📱 新客户端连接: {client_id} ({client_ip}){device_info}")
        self.logger.info(f"👥 当前连接数: {len(self.clients)}")
        
        try:
            # 发送欢迎消息（保持不变）
            await client.send({
                'type': 'welcome',
                'clientId': client_id,
                'timestamp': datetime.now().isoformat(),
                'message': 'WebSocket 连接成功'
            })
            
            # 处理客户端消息（保持不变）
            async for message in websocket:
                await self.handle_client_message(client, message)
                
        except ConnectionClosed:
            self.logger.info(f"📱 客户端正常断开: {client_id}")
        except Exception as e:
            self.logger.error(f"❌ 客户端连接错误 {client_id}: {e}")
        finally:
            # 清理客户端
            if client_id in self.clients:
                del self.clients[client_id]
            
            # 减少IP连接计数
            if client_ip in self.ip_connections:
                self.ip_connections[client_ip] -= 1
                if self.ip_connections[client_ip] <= 0:
                    del self.ip_connections[client_ip]
                self.logger.info(f"📊 IP {client_ip} 连接数: {self.ip_connections.get(client_ip, 0)}")
            
            self.logger.info(f"📱 客户端已移除: {client_id}")
            self.logger.info(f"👥 当前连接数: {len(self.clients)}")
    
    
    
    async def handle_client_message(self, client: WebSocketClient, raw_message: str):
        """处理客户端消息"""
        try:
            message = json.loads(raw_message)
            client.update_ping()
            
            message_type = message.get('type')
            
            if message_type == 'ping':
                # 响应心跳
                await client.send({
                    'type': 'pong',
                    'timestamp': datetime.now().isoformat()
                })
                
            elif message_type == 'subscribe':
                # 订阅设备
                device_id = message.get('device_id')
                if device_id:
                    client.device_id = device_id
                    await client.send({
                        'type': 'subscribed',
                        'device_id': device_id,
                        'timestamp': datetime.now().isoformat()
                    })
                    self.logger.info(f"📡 客户端 {client.client_id} 订阅设备: {device_id}")
                    
            else:
                self.logger.info(f"📨 收到客户端消息 {client.client_id}: {message}")
                
        except json.JSONDecodeError as e:
            self.logger.error(f"❌ JSON 解析错误 {client.client_id}: {e}")
        except Exception as e:
            self.logger.error(f"❌ 处理客户端消息错误 {client.client_id}: {e}")
    
    
    async def redis_subscribe_loop(self):
        """Redis 订阅循环"""
        self.logger.info("📢 启动 Redis 订阅循环...")
        
        try:
            while self.running:
                try:
                    message = await self.pubsub.get_message(timeout=1)
                    if message and message['type'] == 'message':
                        await self.handle_redis_message(message['channel'], message['data'])
                        
                except Exception as e:
                    self.logger.error(f"❌ Redis 订阅错误: {e}")
                    # 尝试重连
                    await asyncio.sleep(5)
                    try:
                        await self.init_redis()
                    except Exception as reconnect_error:
                        self.logger.error(f"❌ Redis 重连失败: {reconnect_error}")
                        
        except Exception as e:
            self.logger.error(f"❌ Redis 订阅循环错误: {e}")
    
    
    async def handle_redis_message(self, channel: str, message: str):
        """处理 Redis 消息"""
        try:
            data = json.loads(message)
            
            device_id = data.get('device_id', 'unknown')
            timestamp = data.get('timestamp', 'unknown')
            
            self.logger.info(f"📢 Redis 消息 [{channel}]: 设备={device_id}, 时间={timestamp}")
            
            # 发送给所有匹配的客户端
            sent_count = 0
            clients_to_remove = []
            
            for client_id, client in self.clients.items():
                if not client.is_alive():
                    clients_to_remove.append(client_id)
                    continue
                
                # 检查设备过滤
                if client.device_id and client.device_id != device_id:
                    continue
                
                # 发送数据
                success = await client.send({
                    'type': 'realtime_data',
                    'channel': channel,
                    'data': data,
                    'timestamp': datetime.now().isoformat()
                })
                
                if success:
                    sent_count += 1
                else:
                    clients_to_remove.append(client_id)
            
            # 清理断开的客户端
            for client_id in clients_to_remove:
                if client_id in self.clients:
                    del self.clients[client_id]
                    self.logger.info(f"🧹 清理断开的客户端: {client_id}")
            
            if sent_count > 0:
                self.logger.info(f"📤 数据已发送给 {sent_count} 个客户端")
                
        except json.JSONDecodeError as e:
            self.logger.error(f"❌ Redis 消息 JSON 解析错误: {e}")
        except Exception as e:
            self.logger.error(f"❌ 处理 Redis 消息错误: {e}")
    
    
    
    async def heartbeat_loop(self):
        """心跳循环 - 修复并发修改字典的问题"""
        self.logger.info("💓 启动心跳循环...")
        
        while self.running:
            try:
                await asyncio.sleep(30)
                
                now = datetime.now()
                
                # 使用 list() 创建客户端字典的快照，避免遍历时修改
                clients_snapshot = list(self.clients.items())
                clients_to_remove = []
                
                for client_id, client in clients_snapshot:
                    try:
                        # 再次检查客户端是否还在字典中（可能已被其他地方删除）
                        if client_id not in self.clients:
                            continue
                            
                        if not client.is_alive():
                            clients_to_remove.append(client_id)
                            continue
                        
                        # 检查心跳超时
                        time_since_ping = (now - client.last_ping).total_seconds()
                        
                        if time_since_ping > 60:
                            self.logger.info(f"⏰ 客户端 {client_id} 心跳超时，断开连接")
                            try:
                                await client.websocket.close()
                            except:
                                pass
                            clients_to_remove.append(client_id)
                        else:
                            # 发送心跳
                            try:
                                await client.ping()
                            except Exception as e:
                                self.logger.warning(f"心跳发送失败 {client_id}: {e}")
                                clients_to_remove.append(client_id)
                                
                    except Exception as client_error:
                        self.logger.error(f"处理客户端 {client_id} 时出错: {client_error}")
                        clients_to_remove.append(client_id)
                
                # 安全地清理客户端 - 使用异步锁或原子操作
                removed_count = 0
                for client_id in clients_to_remove:
                    try:
                        if client_id in self.clients:
                            del self.clients[client_id]
                            removed_count += 1
                            self.logger.info(f"📱 客户端已移除: {client_id}")
                    except Exception as remove_error:
                        self.logger.error(f"移除客户端 {client_id} 时出错: {remove_error}")
                
                if removed_count > 0:
                    self.logger.info(f"👥 当前连接数: {len(self.clients)} (清理了 {removed_count} 个连接)")
                    
            except Exception as e:
                self.logger.error(f"❌ 心跳循环错误: {e}")
                # 添加短暂延迟避免快速循环错误
                await asyncio.sleep(5)
    
    
    
    async def stop(self):
        """停止服务"""
        self.logger.info("🛑 正在停止服务...")
        
        self.running = False
        
        # 关闭所有客户端连接
        for client_id, client in self.clients.items():
            try:
                await client.websocket.close(code=1001, reason='服务关闭')
            except:
                pass
        
        self.clients.clear()
        
        # 停止任务
        if self.heartbeat_task:
            self.heartbeat_task.cancel()
            
        if self.redis_task:
            self.redis_task.cancel()
        
        # 关闭 Redis 连接
        if self.pubsub:
            await self.pubsub.unsubscribe()
            await self.pubsub.close()
            
        if self.redis_client:
            await self.redis_client.close()
        
        self.logger.info("✅ 服务已停止")
    
    
    def generate_client_id(self) -> str:
        """生成客户端ID"""
        return f"client_{int(time.time())}_{uuid.uuid4().hex[:8]}"

    
    async def execute(self):
        pass 


class HealthCheckServer:
    """健康检查HTTP服务器"""
    
    def __init__(self, bridge: WebSocketRedisBridge, port: int = 9037):
        self.bridge = bridge
        self.port = port
        self.server = None
    
    async def handle_health_check(self, request):
        """处理健康检查请求"""
        from aiohttp import web
        
        status = {
            'status': 'ok',
            'clients': len(self.bridge.clients),
            'uptime': time.time(),
            'timestamp': datetime.now().isoformat(),
            'redis_connected': self.bridge.redis_client is not None
        }
        
        return web.json_response(status)

    
    async def start(self):
        """启动健康检查服务"""
        try:
            from aiohttp import web
            
            app = web.Application()
            app.router.add_get('/health', self.handle_health_check)
            app.router.add_get('/', self.handle_health_check)
            
            runner = web.AppRunner(app)
            await runner.setup()
            
            site = web.TCPSite(runner, '0.0.0.0', self.port)
            await site.start()
            
            print(f"🏥 健康检查服务: http://0.0.0.0:{self.port}/health")
            
        except ImportError:
            print("⚠️  aiohttp 未安装，跳过健康检查服务")
        except Exception as e:
            print(f"❌ 健康检查服务启动失败: {e}")


def parse_arguments():
    """解析命令行参数"""
    import argparse
    parser = argparse.ArgumentParser(description='Socket Server Manager')
    
    # 添加port参数
    parser.add_argument(
        '--websocket_manager_port', 
        type=int, 
        default=9037, 
        help='socket server port (default: 9037)'
    )
    return parser.parse_args()


async def main(
    websocket_manager_port,
    ssl_cert_path,
    ssl_key_path
):
    """主函数"""
    from pathlib import Path
    ROOT_DIRECTORY = Path(__file__).parent.parent
    MQTT_CONFIG_PATH = str(ROOT_DIRECTORY / "config" / "yaml" / "websocket_config.yaml")
    REDIS_CONFIG_PATH = str(ROOT_DIRECTORY / "config" / "yaml" / "redis_config.yaml")
    websocket_config = SqlConfig.from_file(MQTT_CONFIG_PATH)
    redis_config = SqlConfig.from_file(REDIS_CONFIG_PATH)
    bridge = WebSocketRedisBridge(
        redis_config=redis_config, 
        websocket_config=websocket_config,
        ssl_cert_path=ssl_cert_path,
        ssl_key_path=ssl_key_path
    )
    health_server = HealthCheckServer(bridge, port=websocket_manager_port)
    
    # 优雅关闭处理
    def signal_handler():
        print("📡 收到关闭信号")
        asyncio.create_task(bridge.stop())
    
    # 注册信号处理器
    if hasattr(signal, 'SIGTERM'):
        signal.signal(signal.SIGTERM, lambda s, f: signal_handler())
    if hasattr(signal, 'SIGINT'):
        signal.signal(signal.SIGINT, lambda s, f: signal_handler())
    
    try:
        # 启动健康检查服务
        await health_server.start()
        
        # 启动主服务
        await bridge.start()
        
    except KeyboardInterrupt:
        print("📡 收到键盘中断")
        await bridge.stop()
    except Exception as e:
        print(f"💥 服务运行错误: {e}")
        await bridge.stop()
        raise


if __name__ == "__main__":
    args = parse_arguments()
    ssl_cert_path = "/work/ai/real_time_vital_analyze/cert/shunxikj.com.crt"
    ssl_key_path = "/work/ai/real_time_vital_analyze/cert/shunxikj.com.key"
    try:
        asyncio.run(main(
            websocket_manager_port=args.websocket_manager_port,
            ssl_cert_path=ssl_cert_path,
            ssl_key_path=ssl_key_path
        ))
    except KeyboardInterrupt:
        print("👋 服务已退出")
    except Exception as e:
        print(f"💥 启动失败: {e}")
        exit(1)