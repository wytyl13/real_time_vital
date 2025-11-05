# test_websocket_alerts.py
import redis
import json
import time
from datetime import datetime

class WebSocketAlertTester:
    def __init__(self):
        # 🔧 根据你的实际配置修改这里
        self.redis_client = redis.Redis(
            host='real_time_vital_analyze_redis',  # 改成你的Redis地址
            port=6379,
            db=0,
            decode_responses=True
        )
        self.channel = 'websocket_alerts'
    
    def test_connection(self):
        """测试Redis连接"""
        try:
            self.redis_client.ping()
            print("✅ Redis连接成功")
            return True
        except Exception as e:
            print(f"❌ Redis连接失败: {e}")
            return False
    
    def check_subscribers(self):
        """检查当前有多少订阅者"""
        # 发送一个ping消息
        count = self.redis_client.publish(self.channel, '{"type":"ping"}')
        print(f"\n📊 频道 'websocket_alerts' 当前有 {count} 个订阅者")
        
        if count == 0:
            print("⚠️ 警告: 没有订阅者!")
            print("   可能的原因:")
            print("   1. WebSocket服务没有启动")
            print("   2. WebSocket服务没有订阅这个频道")
            print("   3. 频道名称不一致")
        else:
            print(f"✅ 正常: 有 {count} 个服务在监听")
        
        return count
    
    def send_test_alert(self):
        """发送测试预警消息"""
        test_message = {
            "type": "alert",
            "device_id": "d0cf13feffe3",
            "alert_type": "TEST_MOVEMENT",
            "action": "start",
            "timestamp": int(time.time() * 1000),
            "data": {
                "state": 2,
                "breath_bpm": 16.5,
                "heart_bpm": 72.0
            },
            "test_flag": True,
            "send_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        message_json = json.dumps(test_message, ensure_ascii=False)
        
        print(f"\n📤 发送测试预警消息:")
        print(f"频道: {self.channel}")
        print(f"消息内容:")
        print(json.dumps(test_message, indent=2, ensure_ascii=False))
        
        subscriber_count = self.redis_client.publish(self.channel, message_json)
        
        print(f"\n📊 发送结果: {subscriber_count} 个订阅者收到消息")
        
        if subscriber_count == 0:
            print("❌ 失败: 没有订阅者收到消息!")
        else:
            print("✅ 成功: 消息已发送")
        
        return subscriber_count
    
    def listen_alerts(self, duration=30):
        """监听预警消息"""
        pubsub = self.redis_client.pubsub()
        pubsub.subscribe(self.channel)
        
        print(f"\n👂 开始监听频道: {self.channel}")
        print(f"⏱️  监听 {duration} 秒...")
        print(f"💡 提示: 在另一个窗口触发预警,看能否收到消息")
        print("=" * 70)
        
        start_time = time.time()
        message_count = 0
        
        try:
            for message in pubsub.listen():
                if time.time() - start_time > duration:
                    break
                
                if message['type'] == 'message':
                    message_count += 1
                    timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]
                    
                    print(f"\n✅ [{message_count}] 收到消息 @ {timestamp}")
                    print("-" * 70)
                    
                    try:
                        data = json.loads(message['data'])
                        print("解析后的JSON:")
                        print(json.dumps(data, indent=2, ensure_ascii=False))
                        
                        # 特别关注的字段
                        if 'device_id' in data:
                            print(f"\n🔑 设备ID: {data['device_id']}")
                        if 'alert_type' in data:
                            print(f"⚠️  预警类型: {data['alert_type']}")
                        if 'action' in data:
                            print(f"🎬 动作: {data['action']}")
                            
                    except json.JSONDecodeError:
                        print("原始消息 (非JSON):")
                        print(message['data'])
                    
                    print("-" * 70)
        
        except KeyboardInterrupt:
            print("\n⏹️  手动停止监听")
        
        finally:
            pubsub.unsubscribe()
            print(f"\n📊 监听结束: 共收到 {message_count} 条消息")
            
            if message_count == 0:
                print("⚠️  没有收到任何消息!")
                print("   请检查:")
                print("   1. 是否真的触发了预警?")
                print("   2. Python服务是否正常运行?")
                print("   3. 查看Python服务的日志")

def show_menu():
    """显示菜单"""
    print("\n" + "=" * 70)
    print("🧪 WebSocket预警系统测试工具")
    print("=" * 70)
    print("1. 检查Redis连接")
    print("2. 检查订阅者数量")
    print("3. 发送测试预警")
    print("4. 监听预警消息 (30秒)")
    print("5. 监听预警消息 (持续监听,Ctrl+C停止)")
    print("6. 完整测试流程")
    print("0. 退出")
    print("=" * 70)

def main():
    tester = WebSocketAlertTester()
    
    while True:
        show_menu()
        choice = input("\n请选择操作 (0-6): ").strip()
        
        if choice == '0':
            print("👋 退出")
            break
        
        elif choice == '1':
            print("\n🔍 测试Redis连接...")
            tester.test_connection()
        
        elif choice == '2':
            print("\n🔍 检查订阅者数量...")
            tester.check_subscribers()
        
        elif choice == '3':
            print("\n🔍 发送测试预警...")
            tester.send_test_alert()
        
        elif choice == '4':
            print("\n🔍 开始监听...")
            tester.listen_alerts(30)
        
        elif choice == '5':
            print("\n🔍 开始持续监听 (Ctrl+C停止)...")
            tester.listen_alerts(999999)
        
        elif choice == '6':
            print("\n🔍 执行完整测试流程...")
            print("\n" + "=" * 70)
            print("步骤 1/4: 测试Redis连接")
            print("=" * 70)
            if not tester.test_connection():
                print("❌ Redis连接失败,无法继续测试")
                continue
            
            time.sleep(1)
            
            print("\n" + "=" * 70)
            print("步骤 2/4: 检查订阅者数量")
            print("=" * 70)
            count = tester.check_subscribers()
            
            time.sleep(1)
            
            print("\n" + "=" * 70)
            print("步骤 3/4: 发送测试预警")
            print("=" * 70)
            tester.send_test_alert()
            
            time.sleep(1)
            
            print("\n" + "=" * 70)
            print("步骤 4/4: 监听10秒")
            print("=" * 70)
            print("💡 提示: 在这10秒内,去触发一个真实预警")
            tester.listen_alerts(10)
            
            print("\n" + "=" * 70)
            print("✅ 完整测试流程结束")
            print("=" * 70)
        
        else:
            print("❌ 无效选项,请重新选择")
        
        input("\n按回车键继续...")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 程序被中断")
    except Exception as e:
        print(f"\n❌ 发生错误: {e}")
        import traceback
        traceback.print_exc()