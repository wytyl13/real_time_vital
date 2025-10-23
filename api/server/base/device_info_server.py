#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time    : 2025/10/16 16:20
@Author  : weiyutao
@File    : device_info_server.py
"""


from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from datetime import datetime
import logging
from pydantic import BaseModel
from typing import (
    Optional
)
from fastapi.encoders import jsonable_encoder
import asyncio
import json
from datetime import datetime

from api.table.base.device_info import DeviceInfo
from agent.provider.sql_provider import SqlProvider
from tools.utils import Utils


utils = Utils()

class ListDeviceInfo(BaseModel):
    id: Optional[int] = None
    device_sn: Optional[str] = None
    device_type: Optional[str] = None
    device_name: Optional[str] = None
    device_location: Optional[str] = None
    wifi_name: Optional[str] = None
    wifi_password: Optional[str] = None
    topic: Optional[str] = None
    device_status: Optional[str] = None
    subscription_status: Optional[str] = None
    offline_time: Optional[int] = None
    user_name: Optional[str] = None
    tenant_id: Optional[int] = None


class DeviceInfoServer:
    """设备服务类"""

    def __init__(self, sql_config_path: str):
        self.sql_config_path = sql_config_path
        self.logger = logging.getLogger(self.__class__.__name__)


    def register_routes(self, app: FastAPI):
        """注册设备相关的路由"""
        app.get("/api/device_info")(self.get_device_info)
        app.post("/api/device_info")(self.post_device_info)
        app.post("/api/device_info/save")(self.save_device_info)
        app.post("/api/device_info/update")(self.update_device_info)
        app.post("/api/device_info/delete")(self.delete_device_info)


    async def get_device_info(
        self,
        id: Optional[int] = None,
        device_sn: Optional[str] = None,
        user_name: Optional[str] = None,
        device_status: Optional[str] = None,
        subscription_status: Optional[str] = None,

    ):
        """
        GET请求 - 支持获取所有设备（不传递任何参数）信息，支持获取指定设备（在url中传递device_sn参数）信息
        Examples:
        - GET /api/device_info -> 获取所有设备信息
        - GET /api/device_info?device_sn=DEV001 -> 获取DEV001设备的信息
        """
        condition = {}
        if device_sn is not None:
            condition["device_sn"] = device_sn
        
        if id is not None and device_sn is None:
            condition["id"] = id
            
        if user_name is not None:
            condition["user_name"] = user_name
            
        if device_status is not None:
            condition["device_status"] = device_status
            
        if subscription_status is not None:
            condition["subscription_status"] = subscription_status

        print(f"condition: ---------------------- {condition}")
        try:
            sql_provider = SqlProvider(model=DeviceInfo, sql_config_path=self.sql_config_path)
            result = await sql_provider.get_record_by_condition(
                condition=condition,
                fields=[
                    "id", 
                    "device_sn", 
                    "device_type", 
                    "device_name", 
                    "device_location", 
                    "wifi_name", 
                    "wifi_password", 
                    "topic", 
                    "device_status", 
                    "subscription_status", 
                    "offline_time", 
                    "user_name", 
                    "create_time", 
                    "tenant_id"
                ]
            )
            json_compatible_result = jsonable_encoder(result)
            
            return JSONResponse(
                status_code=200,
                content={"success": True, "data": json_compatible_result, "timestamp": datetime.now().isoformat()}
            )
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={"success": False, "message": f"获取设备数据失败: {str(e)}", "timestamp": datetime.now().isoformat()}
            )
        finally:
            if sql_provider:
                await sql_provider.close()
                # 等待一小段时间确保连接完全关闭
                await asyncio.sleep(0.1)


    async def post_device_info(
        self,
        list_device_info: ListDeviceInfo,
    ):
        """
        POST请求 - 支持获取所有设备（使用JSON空白请求体）信息，支持获取指定设备（在JSON请求体中传递device_sn参数）信息
        Examples:
        - POST /api/device_info {} -> 获取所有设备信息
        - POST /api/device_info {"device_sn": "DEV001"} -> 获取DEV001设备的信息
        """
        # 无效代码-----------------------------------------------------------------------------------------
        try:
            device_sn = list_device_info.device_sn
            id = list_device_info.id
            user_name = list_device_info.user_name
            subscription_status = list_device_info.subscription_status # 订阅状态
            device_status = list_device_info.device_status # 在线状态
        except Exception as e:
            return JSONResponse(
                status_code=400,
                content={"success": False, "message": f"传参错误！{str(e)}", "data": None, "timestamp": datetime.now().isoformat()}
            )
        try:
            result = await self.get_device_info(
                id=id, 
                device_sn=device_sn, 
                user_name=user_name, 
                subscription_status=subscription_status, 
                device_status=device_status
            )
            return result
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={"success": False, "message": f"获取设备数据失败: {str(e)}", "timestamp": datetime.now().isoformat()}
            )


    async def save_device_info(
        self,
        list_device_info: ListDeviceInfo,
    ):
        """
        POST请求 - 保存设备数据
        """
        sql_provider = None
        try:
            self.logger.info(f"收到设备数据保存请求: {list_device_info}")
            
            if not list_device_info.device_sn:
                return JSONResponse(
                    status_code=400,
                    content={"success": False, "message": f"请提供设备编号", "timestamp": datetime.now().isoformat()}
                )
            
            if not list_device_info.device_type:
                return JSONResponse(
                    status_code=400,
                    content={"success": False, "message": f"请提供设备类型", "timestamp": datetime.now().isoformat()}
                )
            
            if not list_device_info.device_name:
                return JSONResponse(
                    status_code=400,
                    content={"success": False, "message": f"请提供设备名称", "timestamp": datetime.now().isoformat()}
                )
            
            if not list_device_info.user_name:
                return JSONResponse(
                    status_code=400,
                    content={"success": False, "message": f"请提供设备绑定的用户名", "timestamp": datetime.now().isoformat()}
                )
            
            if list_device_info.id:
                return JSONResponse(
                    status_code=400,
                    content={"success": False, "message": f"不允许提供设备id", "timestamp": datetime.now().isoformat()}
                )
            
            # 检查设备编号是否已存在
            response = await self.post_device_info(list_device_info)
            response = utils.parse_server_return(response)
            if response:
                return JSONResponse(
                    status_code=400,
                    content={"success": False, "message": f"设备编号{list_device_info.device_sn}已经存在！", "timestamp": datetime.now().isoformat()}
                )
            
            # 准备插入数据
            insert_data = {
                "device_sn": list_device_info.device_sn,
                "device_type": list_device_info.device_type,
                "device_name": list_device_info.device_name,
                "user_name": list_device_info.user_name,
                "create_time": datetime.now(),
                "update_time": datetime.now()
            }
            
            # 可选字段处理
            if hasattr(list_device_info, 'device_location') and list_device_info.device_location:
                insert_data["device_location"] = list_device_info.device_location
            
            if hasattr(list_device_info, 'wifi_name') and list_device_info.wifi_name:
                insert_data["wifi_name"] = list_device_info.wifi_name
                
            if hasattr(list_device_info, 'wifi_password') and list_device_info.wifi_password:
                insert_data["wifi_password"] = list_device_info.wifi_password
                
            if hasattr(list_device_info, 'topic') and list_device_info.topic:
                insert_data["topic"] = list_device_info.topic
                
            if hasattr(list_device_info, 'device_status') and list_device_info.device_status:
                insert_data["device_status"] = list_device_info.device_status
            else:
                insert_data["device_status"] = "offline"
                
            if hasattr(list_device_info, 'subscription_status') and list_device_info.subscription_status:
                insert_data["subscription_status"] = list_device_info.subscription_status
            else:
                insert_data["subscription_status"] = "pending"
                
            if hasattr(list_device_info, 'tenant_id') and list_device_info.tenant_id is not None:
                insert_data["tenant_id"] = list_device_info.tenant_id
            else:
                insert_data["tenant_id"] = 0

            if hasattr(list_device_info, 'offline_time') and list_device_info.tenant_id is not None:
                insert_data["offline_time"] = list_device_info.offline_time
            else:
                insert_data["offline_time"] = None
            
            sql_provider = SqlProvider(model=DeviceInfo, sql_config_path=self.sql_config_path)
            result = await sql_provider.add_record(insert_data)
            
            if result:
                return JSONResponse(
                    status_code=200,
                    content={"success": True, "message": f"设备保存成功", "data": str(result), "timestamp": datetime.now().isoformat()}
                )
            else:
                return JSONResponse(
                    status_code=500,
                    content={"success": False, "message": f"数据库添加记录失败", "timestamp": datetime.now().isoformat()}
                )
                
        except Exception as e:
            self.logger.error(f"保存设备数据失败: {str(e)}")
            return JSONResponse(
                status_code=500,
                content={"success": False, "message": f"保存失败: {str(e)}", "timestamp": datetime.now().isoformat()}
            )
        finally:
            if sql_provider:
                await sql_provider.close()
                await asyncio.sleep(0.1)


    async def update_device_info(
        self,
        list_device_info: ListDeviceInfo,
    ):
        """
        POST请求 - 更新设备数据
        注意：可以按照id和设备编号更改设备信息，但不能更改设备类型、设备编号、id、topic
        """
        sql_provider = None
        try:
            self.logger.info(f"收到设备数据更新请求: {list_device_info}")
            
            if not list_device_info.device_sn and not list_device_info.id:
                return JSONResponse(
                    status_code=400,
                    content={"success": False, "message": "请提供设备编号或id", "timestamp": datetime.now().isoformat()}
                )
            response_str_title = f"设备编号：{list_device_info.device_sn}" if list_device_info.device_sn else f"设备id：{list_device_info.id}"
            
            device_identifier: ListDeviceInfo = ListDeviceInfo(
                id=list_device_info.id,
                device_sn=list_device_info.device_sn
            )
            
            
            # 查询现有设备数据
            response = await self.post_device_info(device_identifier)
            
            result = utils.parse_server_return(response)
            
            if not result:
                return JSONResponse(
                    status_code=400,
                    content={"success": False, "message": f"{response_str_title}不存在", "timestamp": datetime.now().isoformat()}
                )
            
            # 准备更新数据
            response = result[0]
            insert_data = {
                "update_time": datetime.now()
            }
            
            # 不允许更改的字段：设备类型、设备编号、id、topic
            if list_device_info.device_type and list_device_info.device_type != response["device_type"]:
                return JSONResponse(
                    status_code=400,
                    content={"success": False, "message": "不允许更改设备类型", "timestamp": datetime.now().isoformat()}
                )
            
            if list_device_info.device_sn and list_device_info.device_sn != response["device_sn"]:
                return JSONResponse(
                    status_code=400,
                    content={"success": False, "message": "不允许更改设备编号", "timestamp": datetime.now().isoformat()}
                )
            
            if list_device_info.topic and list_device_info.topic != response.get("topic"):
                return JSONResponse(
                    status_code=400,
                    content={"success": False, "message": "不允许更改订阅主题", "timestamp": datetime.now().isoformat()}
                )
            
            # 保持不可更改的字段
            insert_data["device_sn"] = response["device_sn"]
            insert_data["device_type"] = response["device_type"]
            insert_data["topic"] = response.get("topic")
            
            # 更新字段
            if hasattr(list_device_info, 'device_name') and list_device_info.device_name:
                insert_data["device_name"] = list_device_info.device_name
            else:
                insert_data["device_name"] = response["device_name"]
                
            if hasattr(list_device_info, 'device_location') and list_device_info.device_location:
                insert_data["device_location"] = list_device_info.device_location
            else:
                insert_data["device_location"] = response.get("device_location")
                
            if hasattr(list_device_info, 'wifi_name') and list_device_info.wifi_name:
                insert_data["wifi_name"] = list_device_info.wifi_name
            else:
                insert_data["wifi_name"] = response.get("wifi_name")
                
            if hasattr(list_device_info, 'wifi_password') and list_device_info.wifi_password:
                insert_data["wifi_password"] = list_device_info.wifi_password
            else:
                insert_data["wifi_password"] = response.get("wifi_password")
                
            if hasattr(list_device_info, 'device_status') and list_device_info.device_status:
                insert_data["device_status"] = list_device_info.device_status
            else:
                insert_data["device_status"] = response.get("device_status", "offline")
                
            if hasattr(list_device_info, 'subscription_status') and list_device_info.subscription_status:
                insert_data["subscription_status"] = list_device_info.subscription_status
            else:
                insert_data["subscription_status"] = response.get("subscription_status", "pending_subscription")
                
            if hasattr(list_device_info, 'tenant_id') and list_device_info.tenant_id is not None:
                insert_data["tenant_id"] = list_device_info.tenant_id
            else:
                insert_data["tenant_id"] = response.get("tenant_id", 0)

            if hasattr(list_device_info, 'offline_time') and list_device_info.offline_time is not None:
                insert_data["offline_time"] = list_device_info.offline_time
            else:
                insert_data["offline_time"] = response.get("offline_time", None)
            
            # 更新记录
            sql_provider = SqlProvider(model=DeviceInfo, sql_config_path=self.sql_config_path)
            result = await sql_provider.update_record(record_id=response["id"], data=insert_data)
            
            if result:
                return JSONResponse(
                    status_code=200,
                    content={"success": True, "message": f"{response_str_title}更新成功", "data": str(result), "timestamp": datetime.now().isoformat()}
                )
            else:
                return JSONResponse(
                    status_code=500,
                    content={"success": False, "message": f"更新{response_str_title}失败！数据库更新记录失败", "timestamp": datetime.now().isoformat()}
                )
                
        except Exception as e:
            import traceback
            self.logger.error(f"更新{response_str_title}数据失败: {str(e)}\n{traceback.format_exc()}")
            return JSONResponse(
                status_code=500,
                content={"success": False, "message": f"更新{response_str_title}失败: {str(e)}", "timestamp": datetime.now().isoformat()}
            )
        finally:
            if sql_provider:
                await sql_provider.close()
                await asyncio.sleep(0.1)


    async def delete_device_info(
        self,
        list_device_info: ListDeviceInfo,
    ):
        """
        POST请求 - 删除设备数据
        """
        sql_provider = None
        try:
            self.logger.info(f"收到设备数据删除请求: {list_device_info}")
            
            if not list_device_info.device_sn and not list_device_info.id:
                return JSONResponse(
                    status_code=400,
                    content={"success": False, "message": f"请提供要删除的设备编号或id", "timestamp": datetime.now().isoformat()}
                )
            
            device_identifier: ListDeviceInfo = ListDeviceInfo(
                id=list_device_info.id,
                device_sn=list_device_info.device_sn
            )
            
            # 查询设备是否存在
            response = await self.post_device_info(device_identifier)
            
            result = utils.parse_server_return(response)
            response_str_title = f"设备编号：{list_device_info.device_sn}" if list_device_info.device_sn else f"设备id：{list_device_info.id}"
            if not result:
                return JSONResponse(
                    status_code=500,
                    content={"success": False, "message": f"删除失败！{response_str_title}不存在", "timestamp": datetime.now().isoformat()}
                )
            
            result = result[0]
            sql_provider = SqlProvider(model=DeviceInfo, sql_config_path=self.sql_config_path)
            delete_result = await sql_provider.delete_record(record_id=result["id"], hard_delete=True)
            return JSONResponse(
                status_code=200,
                content={"success": True, "message": f"{response_str_title}删除成功", "timestamp": datetime.now().isoformat()}
            )
                
        except Exception as e:
            import traceback
            self.logger.error(f"删除{response_str_title}失败: {str(e)}\n{traceback.format_exc()}")
            return JSONResponse(
                status_code=500,
                content={"success": False, "message": f"删除{response_str_title}失败: {str(e)}", "timestamp": datetime.now().isoformat()}
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
        device_server = DeviceInfoServer(sql_config_path=SQL_CONFIG_PATH)
        response = await device_server.get_device_info()
        print(response)
        
    asyncio.run(main())