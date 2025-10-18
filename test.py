import asyncio
import websockets
import json
import ssl

async def check_websocket_data():
    # 替换为实际的WebSocket端口
    websocket_url = "wss://localhost:9036"
    
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    
    try:
        async with websockets.connect(websocket_url, ssl=ssl_context) as websocket:
            print("✅ 连接成功，等待欢迎消息...")
            
            # 第一步：先接收服务端发送的欢迎消息（必须先处理）
            welcome_msg = await websocket.recv()
            welcome_data = json.loads(welcome_msg)
            if welcome_data.get('type') == 'welcome':
                print(f"📥 欢迎消息: {welcome_data['message']} (客户端ID: {welcome_data['clientId']})")
            else:
                print(f"❌ 未收到预期的欢迎消息，收到: {welcome_data}")
                return
            
            # 第二步：发送订阅指令
            await websocket.send(json.dumps({
                "type": "subscribe",
                "device_id": "UART__TOPIC_SX_SLEEP_HEART_RATE_LG_02_ODATA"
            }))
            print("📤 已发送订阅消息，等待确认...")
            
            # 第三步：接收订阅确认消息
            confirm_msg = await websocket.recv()
            confirm_data = json.loads(confirm_msg)
            if confirm_data.get('type') == 'subscribed':
                print(f"✅ 订阅成功，设备ID: {confirm_data['device_id']}")
                print("📊 开始接收实时数据（按Ctrl+C停止）：")
                
                # 持续接收数据
                while True:
                    data = await websocket.recv()
                    print(f"\n实时数据: {json.loads(data)}")
            else:
                print(f"❌ 未收到订阅确认，收到: {confirm_data}")
                
    except Exception as e:
        print(f"❌ 测试失败: {e}")

if __name__ == "__main__":
    try:
        asyncio.run(check_websocket_data())
    except KeyboardInterrupt:
        print("\n👋 测试结束")