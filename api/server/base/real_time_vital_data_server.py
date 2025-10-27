#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time    : 2025/10/27 15:40
@Author  : weiyutao
@File    : real_time_vital_data_server.py
"""

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from datetime import datetime
import logging
from pydantic import BaseModel
from typing import Optional, List
from fastapi.encoders import jsonable_encoder
import asyncio
import json

from api.table.base.real_time_vital_data import RealTimeVitalData
from agent.provider.sql_provider import SqlProvider
from tools.utils import Utils


utils = Utils()


class ListRealTimeVitalData(BaseModel):
    """实时生命体征数据模型"""
    id: Optional[int] = None
    device_sn: Optional[str] = None
    timestamp: Optional[float] = None
    breath_bpm: Optional[float] = None
    breath_curve: Optional[List[float]] = None
    heart_bpm: Optional[float] = None
    heart_curve: Optional[List[float]] = None
    state: Optional[int] = None
    # 查询参数
    start_timestamp: Optional[float] = None  # 开始时间戳
    end_timestamp: Optional[float] = None    # 结束时间戳


class RealTimeVitalDataServer:
    """实时生命体征数据服务类"""

    def __init__(self, sql_config_path: str):
        self.sql_config_path = sql_config_path
        self.logger = logging.getLogger(self.__class__.__name__)


    def register_routes(self, app: FastAPI):
        """注册实时数据相关的路由"""
        app.get("/api/real_time_vital_data")(self.get_real_time_vital_data)
        app.post("/api/real_time_vital_data")(self.post_real_time_vital_data)
        app.post("/api/real_time_vital_data/save")(self.save_real_time_vital_data)
        app.post("/api/real_time_vital_data/delete")(self.delete_real_time_vital_data)
        app.post("/api/real_time_vital_data/latest")(self.get_latest_data)


    async def get_real_time_vital_data(
        self,
        id: Optional[int] = None,
        device_sn: Optional[str] = None,
        start_timestamp: Optional[float] = None,
        end_timestamp: Optional[float] = None,
    ):
        """
        GET请求 - 支持获取实时数据
        Examples:
        - GET /api/real_time_vital_data?device_sn=DEV001 -> 获取DEV001设备的最近100条数据
        - GET /api/real_time_vital_data?device_sn=DEV001&start_timestamp=1698000000&end_timestamp=1698086400 -> 获取指定时间范围的数据
        """
        sql_provider = None
        try:
            condition = {}
            
            if id is not None:
                condition["id"] = id
            
            if device_sn is not None:
                condition["device_sn"] = device_sn

            # 处理时间范围查询
            time_range_condition = []
            if start_timestamp is not None:
                time_range_condition.append(f"timestamp >= {start_timestamp}")
            if end_timestamp is not None:
                time_range_condition.append(f"timestamp <= {end_timestamp}")

            self.logger.info(f"查询条件: {condition}, 时间范围: {time_range_condition}")

            sql_provider = SqlProvider(model=RealTimeVitalData, sql_config_path=self.sql_config_path)
            
            # 构建查询
            if time_range_condition:
                # 如果有时间范围条件，使用原始SQL查询
                where_clauses = []
                for key, value in condition.items():
                    where_clauses.append(f"{key} = '{value}'")
                where_clauses.extend(time_range_condition)
                where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"
                
                query = f"""
                SELECT id, device_sn, timestamp, breath_bpm, breath_curve, 
                       heart_bpm, heart_curve, state, create_time
                FROM real_time_vital_data
                WHERE {where_sql}
                ORDER BY timestamp DESC
                """
                result = await sql_provider.execute_query(query)
            else:
                # 普通条件查询
                result = await sql_provider.get_record_by_condition(
                    condition=condition,
                    fields=[
                        "id",
                        "device_sn",
                        "timestamp",
                        "breath_bpm",
                        "breath_curve",
                        "heart_bpm",
                        "heart_curve",
                        "state",
                        "create_time"
                    ],
                )

            json_compatible_result = jsonable_encoder(result)
            
            return JSONResponse(
                status_code=200,
                content={
                    "success": True,
                    "data": json_compatible_result,
                    "count": len(json_compatible_result) if json_compatible_result else 0,
                    "timestamp": datetime.now().isoformat()
                }
            )

        except Exception as e:
            import traceback
            self.logger.error(f"获取实时数据失败: {str(e)}\n{traceback.format_exc()}")
            return JSONResponse(
                status_code=500,
                content={
                    "success": False,
                    "message": f"获取实时数据失败: {str(e)}",
                    "timestamp": datetime.now().isoformat()
                }
            )
        finally:
            if sql_provider:
                await sql_provider.close()
                await asyncio.sleep(0.1)


    async def post_real_time_vital_data(
        self,
        list_data: ListRealTimeVitalData,
    ):
        """
        POST请求 - 支持获取实时数据（使用JSON请求体）
        Examples:
        - POST /api/real_time_vital_data {"device_sn": "DEV001"} -> 获取DEV001设备的数据
        - POST /api/real_time_vital_data {"device_sn": "DEV001", "start_timestamp": 1698000000, "end_timestamp": 1698086400}
        """
        try:
            device_sn = list_data.device_sn
            id = list_data.id
            start_timestamp = list_data.start_timestamp
            end_timestamp = list_data.end_timestamp
        except Exception as e:
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "message": f"传参错误！{str(e)}",
                    "data": None,
                    "timestamp": datetime.now().isoformat()
                }
            )

        try:
            result = await self.get_real_time_vital_data(
                id=id,
                device_sn=device_sn,
                start_timestamp=start_timestamp,
                end_timestamp=end_timestamp,
            )
            return result
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={
                    "success": False,
                    "message": f"获取实时数据失败: {str(e)}",
                    "timestamp": datetime.now().isoformat()
                }
            )


    async def save_real_time_vital_data(
        self,
        list_data: ListRealTimeVitalData,
    ):
        """
        POST请求 - 保存单条实时数据
        """
        sql_provider = None
        try:
            self.logger.info(f"收到实时数据保存请求: {list_data}")
            
            # 验证必填字段
            if not list_data.device_sn:
                return JSONResponse(
                    status_code=400,
                    content={
                        "success": False,
                        "message": "请提供设备编号",
                        "timestamp": datetime.now().isoformat()
                    }
                )
            
            if list_data.timestamp is None:
                return JSONResponse(
                    status_code=400,
                    content={
                        "success": False,
                        "message": "请提供数据时间戳",
                        "timestamp": datetime.now().isoformat()
                    }
                )

            # 准备插入数据
            insert_data = {
                "device_sn": list_data.device_sn,
                "timestamp": list_data.timestamp,
                "breath_bpm": list_data.breath_bpm,
                "breath_curve": list_data.breath_curve,
                "heart_bpm": list_data.heart_bpm,
                "heart_curve": list_data.heart_curve,
                "state": list_data.state,
                "create_time": datetime.now()
            }

            # 插入数据库
            sql_provider = SqlProvider(model=RealTimeVitalData, sql_config_path=self.sql_config_path)
            result = await sql_provider.add_record(data=insert_data)
            
            if result:
                return JSONResponse(
                    status_code=200,
                    content={
                        "success": True,
                        "message": f"设备 {list_data.device_sn} 实时数据保存成功",
                        "data": {"id": result},
                        "timestamp": datetime.now().isoformat()
                    }
                )
            else:
                return JSONResponse(
                    status_code=500,
                    content={
                        "success": False,
                        "message": "实时数据保存失败",
                        "timestamp": datetime.now().isoformat()
                    }
                )

        except Exception as e:
            import traceback
            self.logger.error(f"保存实时数据失败: {str(e)}\n{traceback.format_exc()}")
            return JSONResponse(
                status_code=500,
                content={
                    "success": False,
                    "message": f"保存实时数据失败: {str(e)}",
                    "timestamp": datetime.now().isoformat()
                }
            )
        finally:
            if sql_provider:
                await sql_provider.close()
                await asyncio.sleep(0.1)


    async def get_latest_data(
        self,
        list_data: ListRealTimeVitalData,
    ):
        """
        POST请求 - 获取指定设备的最新数据
        """
        sql_provider = None
        try:
            if not list_data.device_sn:
                return JSONResponse(
                    status_code=400,
                    content={
                        "success": False,
                        "message": "请提供设备编号",
                        "timestamp": datetime.now().isoformat()
                    }
                )

            sql_provider = SqlProvider(model=RealTimeVitalData, sql_config_path=self.sql_config_path)
            
            # 查询最新一条数据
            result = await sql_provider.get_record_by_condition(
                condition={"device_sn": list_data.device_sn},
                fields=[
                    "id",
                    "device_sn",
                    "timestamp",
                    "breath_bpm",
                    "breath_curve",
                    "heart_bpm",
                    "heart_curve",
                    "state",
                    "create_time"
                ],
            )

            json_compatible_result = jsonable_encoder(result)
            
            if json_compatible_result:
                return JSONResponse(
                    status_code=200,
                    content={
                        "success": True,
                        "data": json_compatible_result[0],
                        "timestamp": datetime.now().isoformat()
                    }
                )
            else:
                return JSONResponse(
                    status_code=404,
                    content={
                        "success": False,
                        "message": f"设备 {list_data.device_sn} 暂无数据",
                        "timestamp": datetime.now().isoformat()
                    }
                )

        except Exception as e:
            import traceback
            self.logger.error(f"获取最新数据失败: {str(e)}\n{traceback.format_exc()}")
            return JSONResponse(
                status_code=500,
                content={
                    "success": False,
                    "message": f"获取最新数据失败: {str(e)}",
                    "timestamp": datetime.now().isoformat()
                }
            )
        finally:
            if sql_provider:
                await sql_provider.close()
                await asyncio.sleep(0.1)


    async def delete_real_time_vital_data(
        self,
        list_data: ListRealTimeVitalData,
    ):
        """
        POST请求 - 删除实时数据
        支持按ID删除或按设备+时间范围删除
        """
        sql_provider = None
        try:
            self.logger.info(f"收到实时数据删除请求: {list_data}")
            
            if list_data.id:
                # 按ID删除
                sql_provider = SqlProvider(model=RealTimeVitalData, sql_config_path=self.sql_config_path)
                delete_result = await sql_provider.delete_record(record_id=list_data.id, hard_delete=True)
                
                return JSONResponse(
                    status_code=200,
                    content={
                        "success": True,
                        "message": f"数据记录 ID:{list_data.id} 删除成功",
                        "timestamp": datetime.now().isoformat()
                    }
                )
            
            elif list_data.device_sn:
                # 按设备和时间范围删除
                sql_provider = SqlProvider(model=RealTimeVitalData, sql_config_path=self.sql_config_path)
                await sql_provider.delete_records_by_condition(condition={"device_sn": list_data.device_sn})
                
                return JSONResponse(
                    status_code=200,
                    content={
                        "success": True,
                        "message": f"设备 {list_data.device_sn} 的数据删除成功",
                        "timestamp": datetime.now().isoformat()
                    }
                )
            else:
                return JSONResponse(
                    status_code=400,
                    content={
                        "success": False,
                        "message": "请提供要删除的数据ID或设备编号",
                        "timestamp": datetime.now().isoformat()
                    }
                )

        except Exception as e:
            import traceback
            self.logger.error(f"删除实时数据失败: {str(e)}\n{traceback.format_exc()}")
            return JSONResponse(
                status_code=500,
                content={
                    "success": False,
                    "message": f"删除实时数据失败: {str(e)}",
                    "timestamp": datetime.now().isoformat()
                }
            )
        finally:
            if sql_provider:
                await sql_provider.close()
                await asyncio.sleep(0.1)


if __name__ == '__main__':
    from pathlib import Path
    import asyncio
    
    ROOT_DIRECTORY = Path(__file__).parent.parent.parent.parent
    SQL_CONFIG_PATH = str(ROOT_DIRECTORY / "config" / "yaml" / "sql_config.yaml")
    
    async def main():
        vital_data_server = RealTimeVitalDataServer(sql_config_path=SQL_CONFIG_PATH)
        
        # 测试查询
        response = await vital_data_server.get_real_time_vital_data(device_sn="DEV001")
        print(response)
        
    asyncio.run(main())