#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time    : 2025/09/26
@Author  : weiyutao
@File    : sleep_statistics_server.py
"""

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from datetime import datetime
import logging
from pydantic import BaseModel
from typing import Optional
from fastapi.encoders import jsonable_encoder
import asyncio

from api.table.base.health_report import HealthReport
from agent.provider.sql_provider import SqlProvider
from tools.utils import Utils

utils = Utils()


class HealthReportData(BaseModel):
    """睡眠统计数据模型"""
    # 设备信息
    device_sn: Optional[str] = None
    device_type: Optional[str] = None
    # 睡眠区间
    sleep_start_time: Optional[str] = None
    sleep_end_time: Optional[str] = None
    
    # 生理指标
    avg_breath_rate: Optional[float] = None
    avg_heart_rate: Optional[float] = None
    heart_rate_variability: Optional[float] = None
    
    # 行为统计
    body_movement_count: Optional[int] = None
    apnea_count: Optional[int] = None
    rapid_breathing_count: Optional[int] = None
    leave_bed_count: Optional[int] = None
    
    # 时长统计
    total_duration: Optional[str] = None
    in_bed_duration: Optional[str] = None
    out_bed_duration: Optional[str] = None
    deep_sleep_duration: Optional[str] = None
    light_sleep_duration: Optional[str] = None
    awake_duration: Optional[str] = None
    
    # 关键时间点
    bed_time: Optional[str] = None
    sleep_time: Optional[str] = None
    wake_time: Optional[str] = None
    leave_bed_time: Optional[str] = None
    
    deep_sleep_ratio: Optional[float] = None
    light_sleep_ratio: Optional[float] = None
    
    # 健康报告
    health_report: Optional[str] = None
    
    # 系统字段
    creator: Optional[str] = None
    updater: Optional[str] = None


class HealthReportServer:
    """睡眠统计数据服务类"""
    
    def __init__(self, sql_config_path: str):
        self.sql_config_path = sql_config_path
        self.logger = logging.getLogger(self.__class__.__name__)
        self.sql_provider = SqlProvider(model=HealthReport, sql_config_path=self.sql_config_path)
    
    def register_routes(self, app: FastAPI):
        """注册睡眠统计相关的路由"""
        app.get("/api/sleep_statistics")(self.get_sleep_statistics)
        app.post("/api/sleep_statistics")(self.post_sleep_statistics)
        app.post("/api/sleep_statistics/save")(self.save_sleep_statistics)
        app.post("/api/sleep_statistics/update")(self.update_sleep_statistics)
        app.post("/api/sleep_statistics/delete")(self.delete_sleep_statistics)
        app.get("/api/sleep_statistics/device/{device_sn}")(self.get_sleep_statistics_by_device)
        app.get("/api/sleep_statistics/latest/{device_sn}")(self.get_latest_sleep_statistics)
    
    
    async def get_sleep_statistics(
        self,
        device_sn: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ):
        """
        GET请求 - 获取睡眠统计数据
        Examples:
        - GET /api/sleep_statistics -> 获取所有睡眠统计数据（限制100条）
        - GET /api/sleep_statistics?device_sn=SN123456 -> 获取指定设备的睡眠统计数据
        - GET /api/sleep_statistics?start_date=2025-09-01&end_date=2025-09-30 -> 获取指定日期范围的数据
        """
        condition = {}
        if device_sn is not None:
            condition["device_sn"] = device_sn
            
        sql_provider = None
        try:
            sql_provider = SqlProvider(model=HealthReport, sql_config_path=self.sql_config_path)
            
            # 如果指定了日期范围，需要特殊处理
            if start_date or end_date:
                session = sql_provider.get_session()
                query = session.query(HealthReport)
                
                # 添加设备序列号条件
                if device_sn:
                    query = query.filter(HealthReport.device_sn == device_sn)
                    
                # 添加日期范围条件
                if start_date:
                    start_datetime = datetime.fromisoformat(start_date)
                    query = query.filter(HealthReport.sleep_start_time >= start_datetime)
                
                if end_date:
                    end_datetime = datetime.fromisoformat(end_date)
                    query = query.filter(HealthReport.sleep_end_time <= end_datetime)
                
                # 按睡眠开始时间降序排列
                query = query.order_by(HealthReport.sleep_start_time.desc())
                
                
                result = query.all()
                # 转换为字典列表
                result = [record.to_dict() for record in result]
            else:
                result = await sql_provider.get_record_by_condition(
                    condition=condition,
                )
            
            json_compatible_result = jsonable_encoder(result)
            
            return JSONResponse(
                status_code=200,
                content={"success": True, "data": json_compatible_result, "count": len(json_compatible_result), "timestamp": datetime.now().isoformat()}
            )
        except Exception as e:
            self.logger.error(f"获取睡眠统计数据失败: {str(e)}")
            return JSONResponse(
                status_code=500,
                content={"success": False, "message": f"获取睡眠统计数据失败: {str(e)}", "timestamp": datetime.now().isoformat()}
            )
        finally:
            if sql_provider:
                await sql_provider.close()
                await asyncio.sleep(0.1)


    async def post_sleep_statistics(
        self,
        sleep_data: HealthReportData,
    ):
        """
        POST请求 - 通过JSON请求体获取睡眠统计数据
        Examples:
        - POST /api/sleep_statistics {} -> 获取所有睡眠统计数据
        - POST /api/sleep_statistics {"device_sn": "SN123456"} -> 获取指定设备的睡眠统计数据
        """
        try:
            device_sn = sleep_data.device_sn
            start_date = sleep_data.sleep_start_time
            end_date = sleep_data.sleep_end_time
            
            result = await self.get_sleep_statistics(
                device_sn=device_sn,
                start_date=start_date,
                end_date=end_date
            )
            return result
        except Exception as e:
            self.logger.error(f"POST获取睡眠统计数据失败: {str(e)}")
            return JSONResponse(
                status_code=500,
                content={"success": False, "message": f"获取睡眠统计数据失败: {str(e)}", "timestamp": datetime.now().isoformat()}
            )


    async def get_sleep_statistics_by_device(self, device_sn: str):
        """获取指定设备的睡眠统计数据"""
        return await self.get_sleep_statistics(device_sn=device_sn)


    async def get_latest_sleep_statistics(self, device_sn: str):
        """获取指定设备的最新睡眠统计数据"""
        return await self.get_sleep_statistics(device_sn=device_sn)


    async def save_sleep_statistics(
        self,
        sleep_data: HealthReportData,
    ):
        """
        POST请求 - 保存睡眠统计数据
        """
        sql_provider = None
        try:
            self.logger.info(f"收到睡眠统计数据保存请求: {sleep_data.device_sn}")
            
            if not sleep_data.device_sn:
                return JSONResponse(
                    status_code=400,
                    content={"success": False, "message": "请提供设备序列号", "timestamp": datetime.now().isoformat()}
                )
            
            if not sleep_data.sleep_start_time or not sleep_data.sleep_end_time:
                return JSONResponse(
                    status_code=400,
                    content={"success": False, "message": "请提供睡眠时间区间", "timestamp": datetime.now().isoformat()}
                )
            
            # 检查是否已存在相同设备和时间段的记录
            sleep_start_datetime = datetime.fromisoformat(sleep_data.sleep_start_time.replace('Z', '+00:00'))
            condition = {
                "device_sn": sleep_data.device_sn,
                "sleep_start_time": sleep_start_datetime
            }
            
            sql_provider = SqlProvider(model=HealthReport, sql_config_path=self.sql_config_path)
            existing_record = await sql_provider.get_record_by_condition(condition=condition)
            
            if existing_record:
                return JSONResponse(
                    status_code=400,
                    content={"success": False, "message": f"""<confirm content="确认更新设备{sleep_data.device_sn}的睡眠记录">该设备在此时间段的睡眠记录已存在，是否要更新？</confirm>""", "timestamp": datetime.now().isoformat()}
                )
            
            # 准备插入数据
            insert_data = {
                "device_sn": sleep_data.device_sn,
                "sleep_start_time": datetime.fromisoformat(sleep_data.sleep_start_time.replace('Z', '+00:00')) if sleep_data.sleep_start_time else None,
                "sleep_end_time": datetime.fromisoformat(sleep_data.sleep_end_time.replace('Z', '+00:00')) if sleep_data.sleep_end_time else None,
                "create_time": datetime.now(),
                "update_time": datetime.now()
            }
            
            # 添加可选字段
            optional_fields = [
                'avg_breath_rate', 'avg_heart_rate', 'heart_rate_variability',
                'body_movement_count', 'apnea_count', 'rapid_breathing_count', 'leave_bed_count',
                'total_duration', 'in_bed_duration', 'out_bed_duration', 
                'deep_sleep_duration', 'light_sleep_duration', 'awake_duration',
                'health_report', 'creator', 'deep_sleep_ratio', 'light_sleep_ratio'
            ]
            
            for field in optional_fields:
                value = getattr(sleep_data, field, None)
                if value is not None:
                    insert_data[field] = value
            
            # 处理时间字段
            time_fields = ['bed_time', 'sleep_time', 'wake_time', 'leave_bed_time']
            for field in time_fields:
                value = getattr(sleep_data, field, None)
                if value:
                    insert_data[field] = datetime.fromisoformat(value.replace('Z', '+00:00'))
            
            result = await sql_provider.add_record(insert_data)
            
            if result:
                return JSONResponse(
                    status_code=200,
                    content={"success": True, "message": "睡眠统计数据保存成功", "data": str(result), "timestamp": datetime.now().isoformat()}
                )
            else:
                return JSONResponse(
                    status_code=500,
                    content={"success": False, "message": "数据库添加记录失败", "timestamp": datetime.now().isoformat()}
                )
                
        except Exception as e:
            self.logger.error(f"保存睡眠统计数据失败: {str(e)}")
            import traceback
            traceback.print_exc()
            return JSONResponse(
                status_code=500,
                content={"success": False, "message": f"保存失败: {str(e)}", "timestamp": datetime.now().isoformat()}
            )
        finally:
            if sql_provider:
                await sql_provider.close()
                await asyncio.sleep(0.1)


    async def update_sleep_statistics(
        self,
        sleep_data: HealthReportData,
    ):
        """
        POST请求 - 更新睡眠统计数据
        """
        sql_provider = None
        try:
            self.logger.info(f"收到睡眠统计数据更新请求: {sleep_data.device_sn}")
            
            if not sleep_data.device_sn:
                return JSONResponse(
                    status_code=400,
                    content={"success": False, "message": "请提供设备序列号", "timestamp": datetime.now().isoformat()}
                )
            
            if not sleep_data.sleep_start_time:
                return JSONResponse(
                    status_code=400,
                    content={"success": False, "message": "请提供睡眠开始时间以定位记录", "timestamp": datetime.now().isoformat()}
                )
            
            # 查找现有记录
            condition = {
                "device_sn": sleep_data.device_sn,
                "sleep_start_time": sleep_data.sleep_start_time
            }
            
            sql_provider = SqlProvider(model=HealthReport, sql_config_path=self.sql_config_path)
            existing_records = await sql_provider.get_record_by_condition(condition=condition)
            
            if not existing_records:
                return JSONResponse(
                    status_code=404,
                    content={"success": False, "message": f"未找到设备{sleep_data.device_sn}在指定时间的睡眠记录", "timestamp": datetime.now().isoformat()}
                )
            
            existing_record = existing_records[0]
            
            # 准备更新数据
            update_data = {
                "update_time": datetime.now(),
                "updater": sleep_data.updater if sleep_data.updater else "system"
            }
            
            # 更新字段（只更新有值的字段）
            if sleep_data.sleep_end_time:
                update_data["sleep_end_time"] = datetime.fromisoformat(sleep_data.sleep_end_time.replace('Z', '+00:00'))
            
            # 生理指标
            if sleep_data.avg_breath_rate is not None:
                update_data["avg_breath_rate"] = sleep_data.avg_breath_rate
            if sleep_data.avg_heart_rate is not None:
                update_data["avg_heart_rate"] = sleep_data.avg_heart_rate
            if sleep_data.heart_rate_variability is not None:
                update_data["heart_rate_variability"] = sleep_data.heart_rate_variability
                
            # 行为统计
            if sleep_data.body_movement_count is not None:
                update_data["body_movement_count"] = sleep_data.body_movement_count
            if sleep_data.apnea_count is not None:
                update_data["apnea_count"] = sleep_data.apnea_count
            if sleep_data.rapid_breathing_count is not None:
                update_data["rapid_breathing_count"] = sleep_data.rapid_breathing_count
            if sleep_data.leave_bed_count is not None:
                update_data["leave_bed_count"] = sleep_data.leave_bed_count
            if sleep_data.deep_sleep_ratio is not None:
                update_data["deep_sleep_ratio"] = sleep_data.deep_sleep_ratio
            if sleep_data.light_sleep_ratio is not None:
                update_data["light_sleep_ratio"] = sleep_data.light_sleep_ratio
                
            # 时长统计
            duration_fields = ['total_duration', 'in_bed_duration', 'out_bed_duration', 
                             'deep_sleep_duration', 'light_sleep_duration', 'awake_duration']
            for field in duration_fields:
                value = getattr(sleep_data, field, None)
                if value:
                    update_data[field] = value
                    
            # 关键时间点
            time_fields = ['bed_time', 'sleep_time', 'wake_time', 'leave_bed_time']
            for field in time_fields:
                value = getattr(sleep_data, field, None)
                if value:
                    update_data[field] = datetime.fromisoformat(value.replace('Z', '+00:00'))
                    
            # 健康报告
            if sleep_data.health_report:
                update_data["health_report"] = sleep_data.health_report
            
            # 执行更新
            result = await sql_provider.update_record(
                record_id=existing_record["id"],
                update_data=update_data
            )
            
            if result:
                return JSONResponse(
                    status_code=200,
                    content={"success": True, "message": f"设备{sleep_data.device_sn}的睡眠记录更新成功", "timestamp": datetime.now().isoformat()}
                )
            else:
                return JSONResponse(
                    status_code=500,
                    content={"success": False, "message": "数据库更新记录失败", "timestamp": datetime.now().isoformat()}
                )
                
        except Exception as e:
            self.logger.error(f"更新睡眠统计数据失败: {str(e)}")
            import traceback
            traceback.print_exc()
            return JSONResponse(
                status_code=500,
                content={"success": False, "message": f"更新失败: {str(e)}", "timestamp": datetime.now().isoformat()}
            )
        finally:
            if sql_provider:
                await sql_provider.close()
                await asyncio.sleep(0.1)


    async def delete_sleep_statistics(
        self,
        sleep_data: HealthReportData,
    ):
        """
        POST请求 - 删除睡眠统计数据
        """
        sql_provider = None
        try:
            self.logger.info(f"收到睡眠统计数据删除请求: {sleep_data.device_sn}")
            
            if not sleep_data.device_sn:
                return JSONResponse(
                    status_code=400,
                    content={"success": False, "message": "请提供要删除记录的设备序列号", "timestamp": datetime.now().isoformat()}
                )
                
            if not sleep_data.sleep_start_time:
                return JSONResponse(
                    status_code=400,
                    content={"success": False, "message": "请提供睡眠开始时间以定位记录", "timestamp": datetime.now().isoformat()}
                )
            
            # 查找要删除的记录
            condition = {
                "device_sn": sleep_data.device_sn,
                "sleep_start_time": sleep_data.sleep_start_time
            }
            
            sql_provider = SqlProvider(model=HealthReport, sql_config_path=self.sql_config_path)
            existing_records = await sql_provider.get_record_by_condition(condition=condition)
            
            if not existing_records:
                return JSONResponse(
                    status_code=404,
                    content={"success": False, "message": f"未找到设备{sleep_data.device_sn}在指定时间的睡眠记录", "timestamp": datetime.now().isoformat()}
                )
                
            existing_record = existing_records[0]
            
            # 执行删除
            delete_result = await sql_provider.delete_record(
                record_id=existing_record["id"], 
                hard_delete=True
            )
            
            if delete_result:
                return JSONResponse(
                    status_code=200,
                    content={"success": True, "message": f"设备{sleep_data.device_sn}的睡眠记录删除成功", "timestamp": datetime.now().isoformat()}
                )
            else:
                return JSONResponse(
                    status_code=500,
                    content={"success": False, "message": f"删除失败！设备{sleep_data.device_sn}的睡眠记录删除失败", "timestamp": datetime.now().isoformat()}
                )
                
        except Exception as e:
            self.logger.error(f"删除睡眠统计数据失败: {str(e)}")
            import traceback
            traceback.print_exc()
            return JSONResponse(
                status_code=500,
                content={"success": False, "message": f"删除失败: {str(e)}", "timestamp": datetime.now().isoformat()}
            )
        finally:
            if sql_provider:
                await sql_provider.close()
                await asyncio.sleep(0.1)


    async def get_sleep_report(self, device_sn: str, days: int = 7):
        """
        获取睡眠报告 - 统计指定天数内的睡眠数据
        """
        try:
            from datetime import timedelta
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)
            
            result = await self.get_sleep_statistics(
                device_sn=device_sn,
                start_date=start_date.isoformat(),
                end_date=end_date.isoformat()
            )
            
            if hasattr(result, 'body'):
                import json
                response_data = json.loads(result.body.decode())
                if response_data.get("success"):
                    sleep_records = response_data.get("data", [])
                    
                    # 生成睡眠报告
                    report = self._generate_sleep_report(sleep_records, days)
                    
                    return JSONResponse(
                        status_code=200,
                        content={"success": True, "data": report, "timestamp": datetime.now().isoformat()}
                    )
            
            return result
            
        except Exception as e:
            self.logger.error(f"获取睡眠报告失败: {str(e)}")
            return JSONResponse(
                status_code=500,
                content={"success": False, "message": f"获取睡眠报告失败: {str(e)}", "timestamp": datetime.now().isoformat()}
            )


    def _generate_sleep_report(self, sleep_records, days):
        """生成睡眠报告"""
        if not sleep_records:
            return {"message": f"过去{days}天内没有睡眠数据"}
        
        total_records = len(sleep_records)
        
        # 统计各项指标
        avg_breath_rates = [r['avg_breath_rate'] for r in sleep_records if r.get('avg_breath_rate')]
        avg_heart_rates = [r['avg_heart_rate'] for r in sleep_records if r.get('avg_heart_rate')]
        movement_counts = [r['body_movement_count'] for r in sleep_records if r.get('body_movement_count') is not None]
        apnea_counts = [r['apnea_count'] for r in sleep_records if r.get('apnea_count') is not None]
        
        report = {
            "period": f"过去{days}天",
            "total_nights": total_records,
            "statistics": {
                "avg_breath_rate": {
                    "average": round(sum(avg_breath_rates) / len(avg_breath_rates), 2) if avg_breath_rates else None,
                    "min": min(avg_breath_rates) if avg_breath_rates else None,
                    "max": max(avg_breath_rates) if avg_breath_rates else None
                },
                "avg_heart_rate": {
                    "average": round(sum(avg_heart_rates) / len(avg_heart_rates), 2) if avg_heart_rates else None,
                    "min": min(avg_heart_rates) if avg_heart_rates else None,
                    "max": max(avg_heart_rates) if avg_heart_rates else None
                },
                "body_movement": {
                    "average": round(sum(movement_counts) / len(movement_counts), 2) if movement_counts else None,
                    "total": sum(movement_counts) if movement_counts else 0
                },
                "apnea_events": {
                    "average": round(sum(apnea_counts) / len(apnea_counts), 2) if apnea_counts else None,
                    "total": sum(apnea_counts) if apnea_counts else 0
                }
            },
            "recent_records": sleep_records[:5]  # 最近5条记录
        }
        
        return report


if __name__ == '__main__':
    from pathlib import Path
    import asyncio
    
    ROOT_DIRECTORY = Path(__file__).parent.parent.parent.parent
    SQL_CONFIG_PATH = str(ROOT_DIRECTORY / "config" / "yaml" / "sql_config.yaml")
    
    async def main():
        sleep_server = HealthReportServer(sql_config_path=SQL_CONFIG_PATH)
        
        # 测试获取数据
        response = await sleep_server.get_sleep_statistics()
        print("获取睡眠统计数据测试:")
        print(response)
        
        # 测试保存数据
        test_data = HealthReportData(
            device_sn="TEST_DEVICE_001",
            sleep_start_time="2025-09-26T22:00:00",
            sleep_end_time="2025-09-27T07:30:00",
            avg_breath_rate=16.5,
            avg_heart_rate=65.2,
            body_movement_count=12,
            total_duration="7小时30分钟",
            deep_sleep_duration="2小时15分钟"
        )
        
        save_response = await sleep_server.save_sleep_statistics(test_data)
        print("\n保存睡眠统计数据测试:")
        print(save_response)
    
    asyncio.run(main())