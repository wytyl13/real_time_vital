#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time    : 2025/08/09 09:38
@Author  : weiyutao
@File    : init_tables.py
"""
from pathlib import Path
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.exc import OperationalError

from api.table.base.user_data import UserData
from api.table.base.device_info import DeviceInfo
from api.table.base.health_report import HealthReport

# from api.table.base.community_real_time_data import CommunityRealTimeData
# from api.table.meal_assistance_subsystem.menu_data import MenuData
# from api.table.meal_assistance_service_app.order_food_data import OrderFoodData
# from api.table.merchant_service_system.merchant_management import MerchantData
# from api.table.real_time_vital_analyze.sleep_statistics import SleepStatistics
# from api.table.base.role_info import RoleInfo


from agent.config.sql_config import SqlConfig
from api.table.base.base import Base


ROOT_DIRECTORY = Path(__file__).parent.parent.parent
SQL_CONFIG_PATH = str(ROOT_DIRECTORY / "config" / "yaml" / "sql_config.yaml")

sql_config = SqlConfig.from_file(SQL_CONFIG_PATH)


async def check_tables_exist():
    """检查表是否已存在"""
    engine = create_async_engine(sql_config.sql_url)
    
    async with engine.begin() as conn:
        # 获取所有需要创建的表名
        table_names = [table.name for table in Base.metadata.tables.values()]
        print(table_names)
        # 检查每个表是否存在
        existing_tables = []
        for table_name in table_names:
            try:
                # 尝试查询表的存在性
                result = await conn.execute(text(f"SELECT 1 FROM {table_name} LIMIT 1"))
                existing_tables.append(table_name)
            except Exception:
                # 表不存在或查询失败
                pass
    
    await engine.dispose()
    return existing_tables


async def drop_all_tables():
    """删除所有表"""
    engine = create_async_engine(sql_config.sql_url)
    
    async with engine.begin() as conn:
        # 删除所有表
        await conn.run_sync(Base.metadata.drop_all)
    
    await engine.dispose()
    print("所有表已删除！")


async def create_all_tables():
    """异步创建所有表"""
    engine = create_async_engine(sql_config.sql_url)
    
    async with engine.begin() as conn:
        # 这会创建所有继承自Base的表
        await conn.run_sync(Base.metadata.create_all)
    
    await engine.dispose()
    print("所有表创建完成！")


async def create_missing_tables(missing_table_names):
    """创建指定的缺失表"""
    engine = create_async_engine(sql_config.sql_url)
    
    async with engine.begin() as conn:
        from sqlalchemy import MetaData
        missing_metadata = MetaData()
        
        for table_name in missing_table_names:
            if table_name in Base.metadata.tables:
                Base.metadata.tables[table_name].to_metadata(missing_metadata)
        
        await conn.run_sync(missing_metadata.create_all)
    
    await engine.dispose()
    print(f"已创建缺失的表: {', '.join(missing_table_names)}")


async def create_tables_with_check():
    """检查表是否存在，如果存在则询问用户是否删除重建"""
    existing_tables = await check_tables_exist()
    all_required_tables = [table.name for table in Base.metadata.tables.values()]  # 定义所需的所有表
    
    if existing_tables:
        print(f"检测到以下表已存在: {', '.join(existing_tables)}")
        
        while True:
            user_choice = input("是否要删除现有表并重新创建？(y/n): ").strip().lower()
            
            if user_choice in ['y', 'yes', '是']:
                print("正在删除现有表...")
                await drop_all_tables()
                print("正在重新创建表...")
                await create_all_tables()
                break
            elif user_choice in ['n', 'no', '否']:
                print("保留现有表，创建缺失的表...")
                # 创建不存在的表
                missing_tables = set(all_required_tables) - set(existing_tables)
                if missing_tables:
                    await create_missing_tables(missing_tables)
                break
            else:
                print("请输入 y(是) 或 n(否)")
    else:
        print("未检测到现有表，开始创建新表...")
        await create_all_tables()


async def create_default_users():
    """创建默认用户"""
    engine = create_async_engine(sql_config.sql_url)
    async_session = sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        try:
            from sqlalchemy import select
            
            # 定义默认用户列表
            default_users = [
                {
                    "user_name": "admin",
                    "password": "admin",
                    "full_name": "admin",
                    "role": "admin",
                    "community": "舜熙科技智慧养老社区",
                    "status": "active",
                    "creator": "system"
                },
                {
                    "user_name": "shunxikeji",
                    "password": "shunxikeji",
                    "full_name": "shunxikeji",
                    "gender": "男",
                    "age": 18,
                    "height": 170,
                    "weight": 60,
                    "address": "北京市海淀区圆明园西路2号院",
                    "phone": "17600174284",
                    "email": "wytyl1314520@gmail.com",
                    "role": "user",
                    "community": "舜熙科技智慧养老社区",
                    "status": "active",
                    "creator": "system"
                },
                {
                    "user_name": "weiyutao",
                    "password": "weiyutao",
                    "full_name": "weiyutao",
                    "role": "device_manager",
                    "community": "舜熙科技智慧养老社区",
                    "status": "active",
                    "creator": "system"
                }
            ]
            
            # 遍历创建用户
            for user_data in default_users:
                # 检查用户是否已存在
                result = await session.execute(
                    select(UserData).where(UserData.user_name == user_data["user_name"])
                )
                existing_user = result.scalar_one_or_none()
                
                if not existing_user:
                    # 创建新用户
                    new_user = UserData(**user_data)
                    session.add(new_user)
                    print(f"创建用户 {user_data['user_name']} 成功")
                else:
                    print(f"用户 {user_data['user_name']} 已存在")
            
            # 提交事务
            await session.commit()
            print("默认用户创建完成！")
            
        except Exception as e:
            # 回滚事务
            await session.rollback()
            print(f"创建默认用户时发生错误: {e}")
            import traceback
            traceback.print_exc()
        finally:
            await session.close()
    
    await engine.dispose()


# async def create_default_roles():
#     """创建默认角色"""
#     engine = create_async_engine(sql_config.sql_url)
#     async_session = sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    
#     async with async_session() as session:
#         try:
#             from sqlalchemy import select
            
#             # 定义默认角色列表
#             default_roles = [
#                 {
#                     "role_name": "设备管理员",
#                     "role_code": "device_manager",
#                     "description": "设备管理员",
#                     "permissions": '["real_time_vital_analyze_service"]',
#                     "role_status": 1,
#                     "creator": "system"
#                 },
#                 {
#                     "role_name": "普通用户",
#                     "role_code": "user",
#                     "description": "系统普通用户，具有基础操作权限",
#                     "permissions": '["welcome_system", "meal_assistance_subsystem", "meal_assistance_service_app", "real_time_vital_analyze_service", "merchant_service_system", "traditional_medical_service"]',
#                     "role_status": 1,
#                     "creator": "system"
#                 }
#             ]
            
#             # 遍历创建角色
#             for role_data in default_roles:
#                 # 检查角色是否已存在
#                 result = await session.execute(
#                     select(RoleInfo).where(RoleInfo.role_code == role_data["role_code"])
#                 )
#                 existing_role = result.scalar_one_or_none()
                
#                 if not existing_role:
#                     # 创建新角色
#                     new_role = RoleInfo(**role_data)
#                     session.add(new_role)
#                     print(f"创建角色 {role_data['role_name']} ({role_data['role_code']}) 成功")
#                 else:
#                     print(f"角色 {role_data['role_name']} ({role_data['role_code']}) 已存在")
            
#             # 提交事务
#             await session.commit()
#             print("默认角色创建完成！")
            
#         except Exception as e:
#             # 回滚事务
#             await session.rollback()
#             print(f"创建默认角色时发生错误: {e}")
#             import traceback
#             traceback.print_exc()
#         finally:
#             await session.close()
    
#     await engine.dispose()


async def create_default_devices():
    """创建默认设备数据"""
    engine = create_async_engine(sql_config.sql_url)
    async_session = sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        try:
            from sqlalchemy import select
            
            # 定义默认设备列表
            default_devices = [
                {
                    "device_sn": "UART__TOPIC_SX_SLEEP_HEART_RATE_LG_02_ODATA",
                    "device_name": "样板间靠门床垫",
                    "device_type": "智能床垫",
                    "user_name": "shunxikeji",
                    "device_status": "online",
                    "wifi_name": "sxkj",
                    "wifi_password": "88888888",
                    "topic": "/topic/sx_sleep_heart_rate_lg_02_odata",
                },
                {
                    "device_sn": "UART__TOPIC_SX_SLEEP_HEART_RATE_LG_00_ODATA",
                    "device_type": "智能床垫",
                    "device_name": "大厅测试",
                    "wifi_name": "sxkj",
                    "wifi_password": "88888888",
                    "topic": "/topic/sx_sleep_heart_rate_lg_00_odata",
                    "device_status": "online",
                    "user_name": "shunxikeji",
                }
            ]
            
            # 遍历创建设备
            for device_data in default_devices:
                # 检查设备是否已存在
                result = await session.execute(
                    select(DeviceInfo).where(DeviceInfo.device_sn == device_data["device_sn"])
                )
                existing_device = result.scalar_one_or_none()
                
                if not existing_device:
                    new_device = DeviceInfo(**device_data)
                    session.add(new_device)
                    print(f"✓ 创建设备: {device_data['device_name']} ({device_data['device_sn']})")
                else:
                    print(f"- 设备已存在: {device_data['device_name']} ({device_data['device_sn']})")
            
            await session.commit()
            print("默认设备创建完成！")
            
        except Exception as e:
            await session.rollback()
            print(f"✗ 创建默认设备数据时发生错误: {e}")
            import traceback
            traceback.print_exc()
        finally:
            await session.close()
    
    await engine.dispose()


async def create_default_sleep_statistics():
    """创建默认睡眠统计数据"""
    engine = create_async_engine(sql_config.sql_url)
    async_session = sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        try:
            from sqlalchemy import select
            from datetime import datetime
            
            # 定义默认睡眠统计数据列表
            default_sleep_data = [
                {
                    "device_sn": "UART__TOPIC_SX_SLEEP_HEART_RATE_LG_50_ODATA",
                    "device_type": None,
                    "sleep_start_time": datetime.fromisoformat("2025-08-11T09:18:00"),
                    "sleep_end_time": datetime.fromisoformat("2025-08-11T09:25:00"),
                    "avg_breath_rate": 16.0,
                    "avg_heart_rate": 114.0,
                    "heart_rate_variability": 0.1383,
                    "body_movement_count": 0,
                    "apnea_count": 0,
                    "rapid_breathing_count": 1,
                    "leave_bed_count": 0,
                    "total_duration": "0小时6分21秒",
                    "in_bed_duration": "0小时6分21秒",
                    "out_bed_duration": "0小时0分0秒",
                    "deep_sleep_duration": "0小时0分0秒",
                    "light_sleep_duration": "0小时0分0秒",
                    "awake_duration": "0小时5分24秒",
                    "bed_time": datetime.fromisoformat("2025-08-11T09:19:00"),
                    "sleep_time": datetime.fromisoformat("2025-08-11T09:26:00"),
                    "wake_time": datetime.fromisoformat("2025-08-11T09:26:00"),
                    "leave_bed_time": datetime.fromisoformat("2025-08-11T09:26:00"),
                    "deep_sleep_ratio": 0.3,
                    "light_sleep_ratio": 0.7,
                    "health_report": """### 睡眠类型识别
本次睡眠属于**午睡**，判断依据为总睡眠时长（6分21秒）小于2小时且开始时间在09:18:52。

### 总体概况
整体睡眠状况不佳。入睡后未进入深睡眠阶段，主要表现为浅睡眠和清醒状态，且存在呼吸急促现象。

### 生理指标分析
- **呼吸率**：平均呼吸率为16次/分钟，在午睡标准范围内（12-20次/分钟），但接近上限。
- **心率**：平均心率为114次/分钟，超出午睡正常范围（65-85次/分钟），偏离程度较大。理想值为70-80次/分钟。
- **心率变异性**：心率变异性为0.1383，在良好范围内（>0.15），表明心脏调节功能较好。

### 睡眠结构分析
- **深睡眠时长**：0小时，未达到午睡标准的深睡眠占比（5-15%）。
- **浅睡眠时长**：0小时21秒，占总时间的3.4%，偏离正常范围（70-85%）。
- **清醒时长**：5分24秒，占总时间的87.6%，远高于理想值（<10分钟或<总时长的15%）。
- **睡眠效率**：计算结果为0%，低于理想范围（>80%），表明本次午睡质量极差。

### 行为表现分析
- **体动频率**：未记录任何体动，符合午睡标准（正常 <8次/小时）。
- **呼吸急促次数**：出现1次快速呼吸现象，需要关注。
- **离床行为**：无离床行为，符合午睡标准（正常0次）。

### 时间节律分析
- **入睡潜伏期**：计算结果为7分钟，处于可接受范围内（<30分钟），表明入睡较快。
- **作息规律性**：上床时间和自然醒来时间间隔较短，接近理想状态。

### 综合评估
整体睡眠质量评级为**较差**。主要问题在于未能进入深睡眠阶段、心率偏高且出现一次呼吸急促现象。建议关注心脏健康并适当调整午睡时长和环境，以提高午睡质量。""",
                    "creator": "system",
                    "updater": None
                },
                {
                    "device_sn": "UART__TOPIC_SX_SLEEP_HEART_RATE_LG_50_ODATA",
                    "device_type": None,
                    "sleep_start_time": datetime.fromisoformat("2025-07-03T21:00:00"),
                    "sleep_end_time": datetime.fromisoformat("2025-07-04T07:01:00"),
                    "avg_breath_rate": 14.0,
                    "avg_heart_rate": 79.0,
                    "heart_rate_variability": 0.1918,
                    "body_movement_count": 2,
                    "apnea_count": 2,
                    "rapid_breathing_count": 50,
                    "leave_bed_count": 5,
                    "total_duration": "10小时0分22秒",
                    "in_bed_duration": "10小时0分22秒",
                    "out_bed_duration": None,
                    "deep_sleep_duration": "47分29秒",
                    "light_sleep_duration": "5小时12分1秒",
                    "awake_duration": "3小时27分钟",
                    "bed_time": datetime.fromisoformat("2025-07-03T21:00:00"),
                    "sleep_time": datetime.fromisoformat("2025-07-03T21:40:00"),
                    "wake_time": datetime.fromisoformat("2025-07-04T07:01:00"),
                    "leave_bed_time": datetime.fromisoformat("2025-07-04T04:32:00"),
                    "health_report": """### 总体概况
整体睡眠时长为10小时0分22秒，但深睡时间较短且存在多次离床行为。总体表现为浅睡和清醒时间较长。

### 生理指标分析
- **呼吸率**：平均呼吸率为14次/分钟，在正常范围内（12-20次/分钟），理想值为14-16次/分钟。
- **心率**：平均心率为79次/分钟，处于正常范围（60-100次/分钟）内。睡眠时的理想心率在50-70次/分钟之间，但该数值略高。
- **心率变异性**：心率变异性为0.1918，在良好范围内（>0.15），表明心脏功能较好。

### 睡眠结构分析
- **深睡时长**：仅47分29秒，占总睡眠时间的4.8%，远低于理想值1.5-2.5小时。
- **浅睡时长**：5小时12分1秒，占总睡眠时间的51.3%。正常范围为45-55%。
- **清醒时长**：3小时27分钟，占总睡眠时间的32.8%，明显偏高。理想值应小于30分钟。

### 行为表现分析
- **体动次数**：每晚仅两次，符合正常范围（20-40次/夜）。
- **呼吸暂停次数**：共发生两次，未达到重度标准（>30次/整夜），但需关注。
- **呼吸急促次数**：50次/夜，明显高于理想值（<20次/整夜），提示可能存在呼吸问题。
- **离床次数**：共五次，频繁离床影响睡眠质量。

### 时间节律分析
- **入睡潜伏期**：从上床到入睡用了40分57秒，接近30分钟的正常范围。
- **作息时间规律性**：整体作息规律较好，但存在多次离床行为可能影响睡眠连续性。

### 综合评估
综合上述各项指标分析，您的睡眠质量评分为61分，属于"一般"等级。主要问题包括深睡时长不足、呼吸急促次数较多以及频繁离床等。建议保持良好的作息规律，并关注潜在的呼吸系统健康状况。

请根据以上报告调整生活习惯和作息时间，如有持续不适，请及时就医咨询专业医生。""",
                    "creator": None,
                    "updater": None
                }
            ]
            
            # 遍历创建睡眠统计数据
            for sleep_data in default_sleep_data:
                # 检查是否已存在相同的睡眠记录（根据设备序列号和睡眠开始时间判断）
                result = await session.execute(
                    select(HealthReport).where(
                        HealthReport.device_sn == sleep_data["device_sn"],
                        HealthReport.sleep_start_time == sleep_data["sleep_start_time"]
                    )
                )
                existing_record = result.scalar_one_or_none()
                
                if not existing_record:
                    new_record = HealthReport(**sleep_data)
                    session.add(new_record)
                    print(f"✓ 创建睡眠记录: {sleep_data['device_sn']} - {sleep_data['sleep_start_time']}")
                else:
                    print(f"- 睡眠记录已存在: {sleep_data['device_sn']} - {sleep_data['sleep_start_time']}")
            
            await session.commit()
            
        except Exception as e:
            await session.rollback()
            print(f"✗ 创建默认睡眠统计数据时发生错误: {e}")
            import traceback
            traceback.print_exc()
        finally:
            await session.close()
    
    await engine.dispose()



async def init_database():
    """初始化数据库：创建表和默认用户"""
    print("开始初始化数据库...")
    
    try:
        # 1. 检查并创建表
        await create_tables_with_check()
        
        # # 2. 先创建角色
        # await create_default_roles()
        
        # 3. 创建默认用户
        await create_default_users()
        
        # 4 创建默认设备
        await create_default_devices()
        
        # 5. 创建默认用睡眠数据
        await create_default_sleep_statistics()
        
        print("数据库初始化完成！")
    
    except Exception as e:
        print(f"数据库初始化过程中发生错误: {e}")
        raise


if __name__ == '__main__':
    import asyncio
    asyncio.run(init_database())