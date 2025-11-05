#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time    : 2025/10/28 18:49
@Author  : weiyutao
@File    : message_center_server.py
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

from api.table.base.message_center import MessageCenter
from agent.provider.sql_provider import SqlProvider
from tools.utils import Utils

utils = Utils()

class ListMessageCenter(BaseModel):
    id: Optional[int] = None
    device_sn: Optional[str] = None
    message_type: Optional[int] = None
    title: Optional[str] = None
    content: Optional[str] = None
    is_read: Optional[bool] = None
    trigger_time: Optional[int] = None
    duration: Optional[int] = None
    extra_data: Optional[dict] = None
    user_name: Optional[str] = None
    tenant_id: Optional[int] = None

class CreateMessageCenter(BaseModel):
    device_sn: str
    message_type: int
    title: str
    content: str
    trigger_time: int
    duration: Optional[int] = None
    extra_data: Optional[dict] = None
    user_name: str
    tenant_id: Optional[int] = 0

class MarkReadRequest(BaseModel):
    message_ids: List[int]
    user_name: str

class MessageCenterServer:
    """消息中心服务类"""

    def __init__(self, sql_config_path: str):
        self.sql_config_path = sql_config_path
        self.logger = logging.getLogger(self.__class__.__name__)

    def register_routes(self, app: FastAPI):
        """注册消息中心相关的路由"""
        app.get("/api/message_center")(self.get_message_center)
        app.post("/api/message_center")(self.post_message_center)
        app.post("/api/message_center/save")(self.save_message_center)
        app.post("/api/message_center/update")(self.update_message_center)
        app.post("/api/message_center/delete")(self.delete_message_center)
        app.post("/api/message_center/mark_read")(self.mark_messages_read)
        app.post("/api/message_center/mark_all_read")(self.mark_all_messages_read)

    async def get_message_center(
        self,
        user_name: Optional[str] = None,
        device_sn: Optional[str] = None,
        message_type: Optional[int] = None,
        is_read: Optional[bool] = None,
        id: Optional[int] = None,
    ):
        """
        GET请求 - 支持获取所有消息或按条件过滤
        Examples:
        - GET /api/message_center -> 获取所有消息
        - GET /api/message_center?user_name=john -> 获取john用户的消息
        - GET /api/message_center?message_type=1 -> 获取预警类型消息
        """
        condition = {}
        
        if user_name is not None:
            condition["user_name"] = user_name
        if device_sn is not None:
            condition["device_sn"] = device_sn
        if message_type is not None:
            condition["message_type"] = message_type
        if is_read is not None:
            condition["is_read"] = is_read
        if id is not None:
            condition["id"] = id
            
        try:
            sql_provider = SqlProvider(model=MessageCenter, sql_config_path=self.sql_config_path)
            result = await sql_provider.get_record_by_condition(
                condition=condition,
                fields=["id", "device_sn", "message_type", "title", "content", "is_read", 
                       "trigger_time", "duration", "extra_data", "user_name", "create_time", "tenant_id"],
            )
            json_compatible_result = jsonable_encoder(result)
            
            return JSONResponse(
                status_code=200,
                content={"success": True, "data": json_compatible_result, "timestamp": datetime.now().isoformat()}
            )
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={"success": False, "message": f"获取消息数据失败: {str(e)}", "timestamp": datetime.now().isoformat()}
            )
        finally:
            if sql_provider:
                await sql_provider.close()
                await asyncio.sleep(0.1)

    async def post_message_center(
        self,
        list_message_center: ListMessageCenter,
    ):
        """
        POST请求 - 支持获取所有消息或按条件过滤
        """
        try:
            user_name = list_message_center.user_name
            device_sn = list_message_center.device_sn
            message_type = list_message_center.message_type
            is_read = list_message_center.is_read
            id = list_message_center.id
        except Exception as e:
            return JSONResponse(
                status_code=400,
                content={"success": False, "message": f"传参错误！{str(e)}", "data": None, "timestamp": datetime.now().isoformat()}
            )
        
        try:
            result = await self.get_message_center(
                user_name=user_name, 
                device_sn=device_sn, 
                message_type=message_type, 
                is_read=is_read, 
                id=id
            )
            return result
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={"success": False, "message": f"获取消息数据失败: {str(e)}", "timestamp": datetime.now().isoformat()}
            )

    async def save_message_center(
        self,
        create_message: CreateMessageCenter,
    ):
        """
        POST请求 - 保存消息数据
        """
        sql_provider = None
        try:
            self.logger.info(f"收到消息保存请求: {create_message}")
            
            # 参数验证
            if not create_message.device_sn:
                return JSONResponse(
                    status_code=400,
                    content={"success": False, "message": "请提供设备编号", "timestamp": datetime.now().isoformat()}
                )
            
            if not create_message.title:
                return JSONResponse(
                    status_code=400,
                    content={"success": False, "message": "请提供消息标题", "timestamp": datetime.now().isoformat()}
                )
                
            if not create_message.content:
                return JSONResponse(
                    status_code=400,
                    content={"success": False, "message": "请提供消息内容", "timestamp": datetime.now().isoformat()}
                )
                
            if not create_message.user_name:
                return JSONResponse(
                    status_code=400,
                    content={"success": False, "message": "请提供用户名", "timestamp": datetime.now().isoformat()}
                )
            
            # 准备插入数据
            insert_data = {
                "device_sn": create_message.device_sn,
                "message_type": create_message.message_type,
                "title": create_message.title,
                "content": create_message.content,
                "trigger_time": create_message.trigger_time,
                "user_name": create_message.user_name,
                "is_read": False,  # 默认未读
                "creator": "system",
                "create_time": datetime.now(),
                "update_time": datetime.now(),
                "tenant_id": create_message.tenant_id or 0
            }
            
            # 可选字段处理
            if create_message.duration is not None:
                insert_data["duration"] = create_message.duration
                
            if create_message.extra_data is not None:
                insert_data["extra_data"] = create_message.extra_data
            
            sql_provider = SqlProvider(model=MessageCenter, sql_config_path=self.sql_config_path)
            result = await sql_provider.add_record(insert_data)
            
            if result:
                return JSONResponse(
                    status_code=200,
                    content={"success": True, "message": "消息保存成功", "data": str(result), "timestamp": datetime.now().isoformat()}
                )
            else:
                return JSONResponse(
                    status_code=500,
                    content={"success": False, "message": "数据库添加记录失败", "timestamp": datetime.now().isoformat()}
                )
                
        except Exception as e:
            self.logger.error(f"保存消息数据失败: {str(e)}")
            return JSONResponse(
                status_code=500,
                content={"success": False, "message": f"保存失败: {str(e)}", "timestamp": datetime.now().isoformat()}
            )
        finally:
            if sql_provider:
                await sql_provider.close()
                await asyncio.sleep(0.1)

    async def update_message_center(
        self,
        list_message_center: ListMessageCenter,
    ):
        """
        POST请求 - 更新消息数据
        """
        sql_provider = None
        try:
            self.logger.info(f"收到消息更新请求: {list_message_center}")
            
            if not list_message_center.id:
                return JSONResponse(
                    status_code=400,
                    content={"success": False, "message": "请提供消息ID", "timestamp": datetime.now().isoformat()}
                )
            
            # 查询现有消息数据
            list_message_center_identify = ListMessageCenter(id=list_message_center.id)
            response = await self.post_message_center(list_message_center_identify)
            result = utils.parse_server_return(response)
            
            if not result:
                return JSONResponse(
                    status_code=400,
                    content={"success": False, "message": f"消息ID {list_message_center.id} 不存在", "timestamp": datetime.now().isoformat()}
                )
            
            # 准备更新数据
            existing_message = result[0]
            update_data = {
                "update_time": datetime.now(),
                "updater": "system"
            }
            
            # 更新指定字段
            if list_message_center.title is not None:
                update_data["title"] = list_message_center.title
                
            if list_message_center.content is not None:
                update_data["content"] = list_message_center.content
                
            if list_message_center.is_read is not None:
                update_data["is_read"] = list_message_center.is_read
                
            if list_message_center.extra_data is not None:
                update_data["extra_data"] = list_message_center.extra_data
            
            sql_provider = SqlProvider(model=MessageCenter, sql_config_path=self.sql_config_path)
            result = await sql_provider.update_record(record_id=list_message_center.id, data=update_data)
            
            if result:
                return JSONResponse(
                    status_code=200,
                    content={"success": True, "message": "消息更新成功", "data": str(result), "timestamp": datetime.now().isoformat()}
                )
            else:
                return JSONResponse(
                    status_code=500,
                    content={"success": False, "message": "数据库更新记录失败", "timestamp": datetime.now().isoformat()}
                )
                
        except Exception as e:
            import traceback
            self.logger.error(f"更新消息数据失败: {str(e)}\n{traceback.format_exc()}")
            return JSONResponse(
                status_code=500,
                content={"success": False, "message": f"更新失败: {str(e)}", "timestamp": datetime.now().isoformat()}
            )
        finally:
            if sql_provider:
                await sql_provider.close()
                await asyncio.sleep(0.1)

    async def delete_message_center(
        self,
        list_message_center: ListMessageCenter,
    ):
        """
        POST请求 - 删除消息数据
        """
        sql_provider = None
        try:
            self.logger.info(f"收到消息删除请求: {list_message_center}")
            
            if not list_message_center.id:
                return JSONResponse(
                    status_code=400,
                    content={"success": False, "message": "请提供要删除的消息ID", "timestamp": datetime.now().isoformat()}
                )
            
            # 查询消息是否存在
            response = await self.post_message_center(list_message_center)
            result = utils.parse_server_return(response)
            
            if not result:
                return JSONResponse(
                    status_code=500,
                    content={"success": False, "message": f"删除失败！消息ID {list_message_center.id} 不存在", "timestamp": datetime.now().isoformat()}
                )
            
            sql_provider = SqlProvider(model=MessageCenter, sql_config_path=self.sql_config_path)
            delete_result = await sql_provider.delete_record(record_id=list_message_center.id, hard_delete=True)
            
            return JSONResponse(
                status_code=200,
                content={"success": True, "message": f"消息ID {list_message_center.id} 删除成功", "timestamp": datetime.now().isoformat()}
            )
                
        except Exception as e:
            import traceback
            self.logger.error(f"删除消息失败: {str(e)}\n{traceback.format_exc()}")
            return JSONResponse(
                status_code=500,
                content={"success": False, "message": f"删除失败: {str(e)}", "timestamp": datetime.now().isoformat()}
            )
        finally:
            if sql_provider:
                await sql_provider.close()
                await asyncio.sleep(0.1)

    async def mark_messages_read(
        self,
        mark_read_request: MarkReadRequest,
    ):
        """
        POST请求 - 批量标记消息为已读
        """
        sql_provider = None
        try:
            self.logger.info(f"收到批量标记已读请求: {mark_read_request}")
            
            if not mark_read_request.message_ids:
                return JSONResponse(
                    status_code=400,
                    content={"success": False, "message": "请提供要标记的消息ID列表", "timestamp": datetime.now().isoformat()}
                )
            
            sql_provider = SqlProvider(model=MessageCenter, sql_config_path=self.sql_config_path)
            
            # 批量更新
            update_data = {
                "is_read": True,
                "update_time": datetime.now(),
                "updater": mark_read_request.user_name
            }
            
            success_count = 0
            for message_id in mark_read_request.message_ids:
                try:
                    result = await sql_provider.update_record(record_id=message_id, data=update_data)
                    if result:
                        success_count += 1
                except Exception as e:
                    self.logger.warning(f"标记消息 {message_id} 为已读失败: {str(e)}")
            
            return JSONResponse(
                status_code=200,
                content={
                    "success": True, 
                    "message": f"成功标记 {success_count}/{len(mark_read_request.message_ids)} 条消息为已读", 
                    "timestamp": datetime.now().isoformat()
                }
            )
                
        except Exception as e:
            import traceback
            self.logger.error(f"批量标记已读失败: {str(e)}\n{traceback.format_exc()}")
            return JSONResponse(
                status_code=500,
                content={"success": False, "message": f"批量标记已读失败: {str(e)}", "timestamp": datetime.now().isoformat()}
            )
        finally:
            if sql_provider:
                await sql_provider.close()
                await asyncio.sleep(0.1)

    async def mark_all_messages_read(
        self,
        list_message_center: ListMessageCenter,
    ):
        """
        POST请求 - 标记用户所有消息为已读
        """
        sql_provider = None
        try:
            self.logger.info(f"收到标记全部已读请求: {list_message_center}")
            
            if not list_message_center.user_name:
                return JSONResponse(
                    status_code=400,
                    content={"success": False, "message": "请提供用户名", "timestamp": datetime.now().isoformat()}
                )
            
            sql_provider = SqlProvider(model=MessageCenter, sql_config_path=self.sql_config_path)
            
            # 查询用户的所有未读消息
            condition = {
                "user_name": list_message_center.user_name,
                "is_read": False
            }
            
            unread_messages = await sql_provider.get_record_by_condition(
                condition=condition,
                fields=["id"]
            )
            
            if not unread_messages:
                return JSONResponse(
                    status_code=200,
                    content={"success": True, "message": "没有未读消息", "timestamp": datetime.now().isoformat()}
                )
            
            # 批量更新
            update_data = {
                "is_read": True,
                "update_time": datetime.now(),
                "updater": list_message_center.user_name
            }
            
            success_count = 0
            for message in unread_messages:
                try:
                    result = await sql_provider.update_record(record_id=message["id"], data=update_data)
                    if result:
                        success_count += 1
                except Exception as e:
                    self.logger.warning(f"标记消息 {message['id']} 为已读失败: {str(e)}")
            
            return JSONResponse(
                status_code=200,
                content={
                    "success": True, 
                    "message": f"成功标记 {success_count} 条消息为已读", 
                    "timestamp": datetime.now().isoformat()
                }
            )
                
        except Exception as e:
            import traceback
            self.logger.error(f"标记全部已读失败: {str(e)}\n{traceback.format_exc()}")
            return JSONResponse(
                status_code=500,
                content={"success": False, "message": f"标记全部已读失败: {str(e)}", "timestamp": datetime.now().isoformat()}
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
        message_server = MessageCenterServer(sql_config_path=SQL_CONFIG_PATH)
        response = await message_server.get_message_center()
        print(response)
        
    asyncio.run(main())