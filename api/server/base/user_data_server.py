
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time    : 2025/08/06 11:22
@Author  : weiyutao
@File    : user_data_server.py
"""


from fastapi import FastAPI, HTTPException, Depends
from fastapi.responses import JSONResponse
from datetime import datetime
import logging
from pydantic import BaseModel
from typing import (
    Optional,
    Dict,
    Any
)
from pathlib import Path
from fastapi.encoders import jsonable_encoder
import asyncio
import json
import random
import string

from .jwt_utils import create_access_token, get_current_user, ACCESS_TOKEN_EXPIRE_MINUTES
from datetime import timedelta

from api.table.base.user_data import UserData
from agent.provider.sql_provider import SqlProvider
from tools.utils import Utils
from api.server.base.sms_verication_api import SMSVerificationServer, SMSVerifyRequest

utils = Utils()

class ListUserData(BaseModel):
    id: Optional[int] = None
    user_name: Optional[str] = None
    password: Optional[str] = None
    full_name: Optional[str] = None
    gender: Optional[str] = None
    age: Optional[int] = None
    height: Optional[float] = None
    weight: Optional[float] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    status: Optional[str] = None
    role: Optional[str] = None
    community: Optional[str] = None
    tenant_id: Optional[int] = None


class LoginUserData(BaseModel):
    user_name: str
    password: str


class UserDataServer:
    """用户服务类"""

    def __init__(self, sql_config_path: str):
        self.sql_config_path = sql_config_path
        self.logger = logging.getLogger(self.__class__.__name__)
        ROOT_DIRECTORY = Path(__file__).parent.parent.parent.parent
        ENV_PATH = str(ROOT_DIRECTORY / ".env")
        REDIS_CONFIG_PATH = str(ROOT_DIRECTORY / "config" / "yaml" / "redis_config.yaml")
        
        # 初始化SMS验证服务
        self.sms_server = SMSVerificationServer(
            env_path=ENV_PATH, 
            redis_config_path=REDIS_CONFIG_PATH
        )
        
        

    def register_routes(self, app: FastAPI):
        """注册用户相关的路由"""
        app.get("/api/user_data")(self.get_user_data)
        app.post("/api/user_data")(self.post_user_data)
        app.post("/api/user_data/save", dependencies=[Depends(get_current_user)])(self.save_user_data)
        app.post("/api/user_data/update", dependencies=[Depends(get_current_user)])(self.update_user_data)
        app.post("/api/user_data/delete")(self.delete_user_data)
        # app.post("/api/user_data/delete", dependencies=[Depends(get_current_user)])(self.delete_user_data)
        app.post("/api/user_data/login")(self.login_user)  # 新增登录接口
        app.post("/api/user_data/verication_and_save_user")(self.verication_and_save_user)  # 新增登录接口


    async def verify_user_sms_code(self, phone: str, code: str, scene: str = "register") -> dict:
        try:
            # 创建验证请求
            verify_request = SMSVerifyRequest(
                phone=phone,
                code=code,
                scene=scene
            )
            
            # 执行验证
            response = await self.sms_server.verify_code(verify_request)
            
            # 判断验证结果
            # 由于verify_code返回的是JSONResponse，我们需要检查状态码
            if hasattr(response, 'status_code'):
                return response.status_code == 200
            
            return False
        
        except Exception as e:
            print(f"SMS验证异常: {str(e)}")
            return False
        
        finally:
            # 确保关闭连接
            if self.sms_server:
                await self.sms_server.close()


    async def get_user_data(
        self,
        user_name: Optional[str] = None,
        id: Optional[int] = None,
        phone: Optional[str] = None
    ):
        """
        GET请求 - 支持获取所有用户（不传递任何参数）信息，支持获取指定用户（在url中传递user_name参数）信息
        Examples:
        - GET /api/user_data -> 获取所有用户信息
        - GET /api/user_data?user_name=john -> 获取john用户的设备信息
        """
        condition = {}
        print(f"condition: ---------------------- {condition}")
        if user_name is not None:
            condition["user_name"] = user_name
        
        if id is not None and user_name is None:
            condition["id"] = id

        if phone is not None:
            condition["phone"] = phone
            
        try:
            sql_provider = SqlProvider(model=UserData, sql_config_path=self.sql_config_path)
            result = await sql_provider.get_record_by_condition(
                condition=condition,
                fields=["id", "user_name", "password", "full_name", "gender", "age", "height", "weight", "address", "phone", "email", "status", "create_time", "tenant_id", "role", "community"]
            )
            json_compatible_result = jsonable_encoder(result)
            
            return JSONResponse(
                status_code=200,
                content={"success": True, "data": json_compatible_result, "timestamp": datetime.now().isoformat()}
            )
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={"success": False, "message": f"获取用户数据失败: {str(e)}", "timestamp": datetime.now().isoformat()}
            )
        finally:
            if sql_provider:
                await sql_provider.close()
                # 等待一小段时间确保连接完全关闭
                await asyncio.sleep(0.1)


    async def post_user_data(
        self,
        list_user_data: ListUserData,
    ):
        """
        POST请求 - 支持获取所有用户（使用JSON空白请求体）信息，支持获取指定用户（在JSON请求体中传递user_name参数）信息
        Examples:
        - POST /api/user_data {} -> 获取所有用户信息
        - POST /api/user_data {"user_name": "JOHN"} -> 获取JOHN用户的设备信息
        """
        # 无效代码-----------------------------------------------------------------------------------------
        try:
            user_name = list_user_data.user_name
            id = list_user_data.id
            phone = list_user_data.phone
        except Exception as e:
            return JSONResponse(
                status_code=400,
                content={"success": False, "message": f"传参错误！{str(e)}", "data": None, "timestamp": datetime.now().isoformat()}
            )
        # 无效代码-----------------------------------------------------------------------------------------
        try:
            result = await self.get_user_data(user_name=user_name, id=id, phone=phone)
            return result
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={"success": False, "message": f"获取用户数据失败: {str(e)}", "timestamp": datetime.now().isoformat()}
            )

    
    async def save_user_data(
        self,
        list_user_data: ListUserData,
    ):
        """
        POST请求 - 保存用户数据
        """
        sql_provider = None
        try:
            self.logger.info(f"收到用户数据保存请求: {list_user_data}")
            
            if not list_user_data.user_name:
                if not list_user_data.phone:
                    return JSONResponse(
                        status_code=400,
                        content={"success": False, "message": f"请提供用户名或手机号", "timestamp": datetime.now().isoformat()}
                    )
                    
                    
            phone_user_data = ListUserData(
                phone=list_user_data.phone,
            )
            phone_response = await self.post_user_data(phone_user_data)
            phone_response = utils.parse_server_return(phone_response)
            if phone_response:
                return JSONResponse(
                    status_code=500,
                    content={
                        "success": False, 
                        "message": f"用户{list_user_data.phone}已经存在！",
                        "data": phone_response,
                        "timestamp": datetime.now().isoformat()
                    }
                )
            
            
            def generate_random_username(length=8):
                letters = string.ascii_lowercase + string.digits
                return ''.join(random.choice(letters) for _ in range(length))
            
            
            # 根据手机号生成不重复的纯字符串用户名
            base_username = generate_random_username(8)
            generated_username = base_username
            counter = 1
            
            while True:
                temp_user_data = ListUserData(
                    user_name=generated_username,
                )
            
                response = await self.post_user_data(temp_user_data)
                response = utils.parse_server_return(response)
                
                if not response:  # 用户名不存在，可以使用
                    break
                    
                
                # 用户名已存在，重新生成
                else:
                    generated_username = generate_random_username(8)
                    counter += 1
                
                if counter > 100:  # 防止无限循环
                    return JSONResponse(
                        status_code=400,
                        content={"success": False, "message": f"创建用户失败：{list_user_data.phone}", "timestamp": datetime.now().isoformat()}
                    )
            
            list_user_data.user_name = generated_username
            self.logger.info(f"为手机号 {list_user_data.phone} 生成用户名: {generated_username}")
            
            
            # if not list_user_data.user_name:
            #     return JSONResponse(
            #         status_code=400,
            #         content={"success": False, "message": f"请提供用户名", "timestamp": datetime.now().isoformat()}
            #     )
            
            # if not list_user_data.password:
            #     return JSONResponse(
            #         status_code=400,
            #         content={"success": False, "message": f"请提供密码", "timestamp": datetime.now().isoformat()}
            #     )
            
            
            if list_user_data.id:
                return JSONResponse(
                    status_code=400,
                    content={"success": False, "message": f"不允许提供用户id", "timestamp": datetime.now().isoformat()}
                )
            
            # 检查用户名是否已存在
            response = await self.post_user_data(list_user_data)
            response = utils.parse_server_return(response)
            if response:
                return JSONResponse(
                    status_code=400,
                    content={
                        "success": False, 
                        "message": f"用户{list_user_data.user_name}已经存在！", 
                        "data": response,
                        "timestamp": datetime.now().isoformat()
                    }
                )
            
            # 准备插入数据
            insert_data = {
                "user_name": list_user_data.user_name,
                "password": list_user_data.password,
                "full_name": list_user_data.full_name,
                "create_time": datetime.now().isoformat(),
                "update_time": datetime.now().isoformat()
            }
            
            # 可选字段处理
            if hasattr(list_user_data, 'gender') and list_user_data.gender:
                insert_data["gender"] = list_user_data.gender
            
            if hasattr(list_user_data, 'age') and list_user_data.age is not None:
                insert_data["age"] = list_user_data.age
                
            if hasattr(list_user_data, 'height') and list_user_data.height is not None:
                insert_data["height"] = list_user_data.height
                
            if hasattr(list_user_data, 'weight') and list_user_data.weight is not None:
                insert_data["weight"] = list_user_data.weight
                
            if hasattr(list_user_data, 'address') and list_user_data.address:
                insert_data["address"] = list_user_data.address
                
            if hasattr(list_user_data, 'phone') and list_user_data.phone:
                insert_data["phone"] = list_user_data.phone
                
            if hasattr(list_user_data, 'email') and list_user_data.email:
                insert_data["email"] = list_user_data.email
                
            if hasattr(list_user_data, 'status') and list_user_data.status:
                insert_data["status"] = list_user_data.status
            else:
                insert_data["status"] = "active"
                
            if hasattr(list_user_data, 'role') and list_user_data.role:
                insert_data["role"] = list_user_data.role
            else:
                insert_data["role"] = "user"  # 默认角色
                
            if hasattr(list_user_data, 'community') and list_user_data.community:
                insert_data["community"] = list_user_data.community
                
            if hasattr(list_user_data, 'tenant_id') and list_user_data.tenant_id is not None:
                insert_data["tenant_id"] = list_user_data.tenant_id
            else:
                insert_data["tenant_id"] = 0
            
            sql_provider = SqlProvider(model=UserData, sql_config_path=self.sql_config_path)
            result = await sql_provider.add_record(insert_data)
            
            if result:
                return JSONResponse(
                    status_code=200,
                    content={
                        "success": True, 
                        "message": f"用户保存成功", 
                        "data": insert_data, 
                        "timestamp": datetime.now().isoformat()
                    }
                )
            else:
                return JSONResponse(
                    status_code=500,
                    content={"success": False, "message": f"数据库添加记录失败", "timestamp": datetime.now().isoformat()}
                )
                
        except Exception as e:
            self.logger.error(f"保存用户数据失败: {str(e)}")
            return JSONResponse(
                status_code=500,
                content={"success": False, "message": f"保存失败: {str(e)}", "timestamp": datetime.now().isoformat()}
            )
        finally:
            if sql_provider:
                await sql_provider.close()
                await asyncio.sleep(0.1)


    async def verication_and_save_user(
        self, 
        sms_verify_request: SMSVerifyRequest
    ):
        try:
            verify_response = await self.verify_user_sms_code(
                phone=sms_verify_request.phone,
                code=sms_verify_request.code
            )
            
            if not verify_response:
                return JSONResponse(
                    status_code=500,
                    content={"success": False, "message": f"验证码错误", "timestamp": datetime.now().isoformat()}
                )
            
            check_exists_response = await self.post_user_data(ListUserData(phone=sms_verify_request.phone))
            check_exists_response_result = utils.parse_server_return(check_exists_response)
            if not check_exists_response_result:
                save_repsonse = await self.save_user_data(ListUserData(phone=sms_verify_request.phone))
                check_exists_response_result = utils.parse_server_return(save_repsonse)
            else:
                check_exists_response_result = check_exists_response_result[0] if len(check_exists_response_result) > 0 else {}
            
            print(f"check_exists_response_result: {check_exists_response_result}")
            # 生成token
            access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
            access_token = create_access_token(
                data={"sub": check_exists_response_result["user_name"], "id": check_exists_response_result["id"], "role": check_exists_response_result["role"]},
                expires_delta=access_token_expires
            )
            
            return JSONResponse(
                status_code=200,
                content={
                    "success": True,
                    "message": "登录成功",
                    "data": {
                        "access_token": access_token,
                        "token_type": "bearer",
                        "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60,
                        "user_info": check_exists_response_result
                    },
                    "timestamp": datetime.now().isoformat()
                }
            )
            
        except Exception as e:
            return JSONResponse(
                status_code=500,
                content={"success": False, "message": f"fail to exec verication and save user function {str(e)}", "timestamp": datetime.now().isoformat()}
            )


    async def update_user_data(
        self,
        list_user_data: ListUserData,
        current_user: Dict[str, Any] = Depends(get_current_user)
    ):
        """
        POST请求 - 更新用户数据
        注意这里更新用户会更新对应的用户id
        """
        sql_provider = None
        try:
            self.logger.info(f"收到用户数据更新请求: {list_user_data}")
            
            if not list_user_data.user_name and not list_user_data.id:
                return JSONResponse(
                    status_code=400,
                    content={"success": False, "message": "请提供用户名或id", "timestamp": datetime.now().isoformat()}
                )
                
            # 此处可新增判断用户名和id不一致的情形
            response_str_title = f"用户：{list_user_data.user_name}" if list_user_data.user_name else f"用户id：{list_user_data.id}"
            
            role = current_user["role"]
            if role != "admin":
                if list_user_data.id and list_user_data.id != current_user["id"]:
                    return JSONResponse(
                    status_code=403,
                    content={"success": False, "message": "无权限修改该用户数据", "timestamp": datetime.now().isoformat()}
                )
                if list_user_data.user_name and list_user_data.user_name != current_user["user_name"]:
                    return JSONResponse(
                    status_code=403,
                    content={"success": False, "message": "无权限修改该用户数据", "timestamp": datetime.now().isoformat()}
                )
            
            # 查询现有用户数据
            response = await self.post_user_data(list_user_data)
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
            
            if list_user_data.user_name:
                insert_data["user_name"] = list_user_data.user_name
            
            # 更新字段
            if hasattr(list_user_data, 'password') and list_user_data.password:
                insert_data["password"] = list_user_data.password
            else:
                insert_data["password"] = response["password"]
                
            if hasattr(list_user_data, 'full_name') and list_user_data.full_name:
                insert_data["full_name"] = list_user_data.full_name
            else:
                insert_data["full_name"] = response["full_name"]
                
            if hasattr(list_user_data, 'gender') and list_user_data.gender:
                insert_data["gender"] = list_user_data.gender
            else:
                insert_data["gender"] = response.get("gender")
                
            if hasattr(list_user_data, 'age') and list_user_data.age is not None:
                insert_data["age"] = list_user_data.age
            else:
                insert_data["age"] = response.get("age")
                
            if hasattr(list_user_data, 'height') and list_user_data.height is not None:
                insert_data["height"] = list_user_data.height
            else:
                insert_data["height"] = response.get("height")
                
            if hasattr(list_user_data, 'weight') and list_user_data.weight is not None:
                insert_data["weight"] = list_user_data.weight
            else:
                insert_data["weight"] = response.get("weight")
                
            if hasattr(list_user_data, 'address') and list_user_data.address:
                insert_data["address"] = list_user_data.address
            else:
                insert_data["address"] = response.get("address")
                
            if hasattr(list_user_data, 'phone') and list_user_data.phone:
                insert_data["phone"] = list_user_data.phone
            else:
                insert_data["phone"] = response.get("phone")
                
            if hasattr(list_user_data, 'email') and list_user_data.email:
                insert_data["email"] = list_user_data.email
            else:
                insert_data["email"] = response.get("email")
                
            if hasattr(list_user_data, 'status') and list_user_data.status:
                insert_data["status"] = list_user_data.status
            else:
                insert_data["status"] = response.get("status", "active")
                
            if hasattr(list_user_data, 'role') and list_user_data.role:
                insert_data["role"] = list_user_data.role
            else:
                insert_data["role"] = response.get("role")
                
            if hasattr(list_user_data, 'community') and list_user_data.community:
                insert_data["community"] = list_user_data.community
            else:
                insert_data["community"] = response.get("community")
                
            if hasattr(list_user_data, 'tenant_id') and list_user_data.tenant_id is not None:
                insert_data["tenant_id"] = list_user_data.tenant_id
            else:
                insert_data["tenant_id"] = response.get("tenant_id", 0)
            
            # 删除旧记录并添加新记录
            sql_provider = SqlProvider(model=UserData, sql_config_path=self.sql_config_path)
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


    async def delete_user_data(
        self,
        list_user_data: ListUserData,
    ):
        """
        POST请求 - 删除用户数据
        """
        sql_provider = None
        try:
            self.logger.info(f"收到用户数据删除请求: {list_user_data}")
            
            if not list_user_data.user_name and not list_user_data.id:
                return JSONResponse(
                    status_code=400,
                    content={"success": False, "message": f"请提供要删除的用户名或id", "timestamp": datetime.now().isoformat()}
                )
            
            # 查询用户是否存在
            response = await self.post_user_data(list_user_data)
            
            result = utils.parse_server_return(response)
            print(result)
            response_str_title = f"用户：{list_user_data.user_name}" if list_user_data.user_name else f"用户id：{list_user_data.id}"
            if not result:
                return JSONResponse(
                    status_code=500,
                    content={"success": False, "message": f"删除失败！{response_str_title}不存在", "timestamp": datetime.now().isoformat()}
                )
            
            result = result[0]
            sql_provider = SqlProvider(model=UserData, sql_config_path=self.sql_config_path)
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


    async def login_user(
        self,
        login_data: LoginUserData,
    ):
        """
        POST请求 - 用户登录验证
        """
        sql_provider = None
        try:
            self.logger.info(f"收到用户登录请求: {login_data.user_name}")
            
            # 参数验证
            if not login_data.user_name:
                return JSONResponse(
                    status_code=400,
                    content={"success": False, "message": "用户名为空", "timestamp": datetime.now().isoformat()}
                )
            
            if not login_data.password:
                return JSONResponse(
                    status_code=400,
                    content={"success": False, "message": "密码为空", "timestamp": datetime.now().isoformat()}
                )
            
            # 查询用户是否存在
            list_user_data = ListUserData(user_name=login_data.user_name)
            response = await self.post_user_data(list_user_data)
            
            result = utils.parse_server_return(response)
            
            if not result:
                return JSONResponse(
                    status_code=400,
                    content={"success": False, "message": "用户名不存在", "timestamp": datetime.now().isoformat()}
                )
            
            user_info = result[0]
            
            # 验证密码
            if user_info["password"] != login_data.password:
                return JSONResponse(
                    status_code=400,
                    content={"success": False, "message": "密码错误", "timestamp": datetime.now().isoformat()}
                )
            
            
            # 生成token
            access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
            access_token = create_access_token(
                data={"sub": login_data.user_name, "id": user_info["id"], "role": user_info["role"]},
                expires_delta=access_token_expires
            )
            
            return JSONResponse(
                status_code=200,
                content={
                    "success": True,
                    "message": "登录成功",
                    "data": {
                        "access_token": access_token,
                        "token_type": "bearer",
                        "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60,
                        "user_info": user_info
                    },
                    "timestamp": datetime.now().isoformat()
                }
            )
            
            # 登录成功
            # return JSONResponse(
            #     status_code=200,
            #     content={"success": True, "message": "登录成功", "data": {"user_name": user_info["user_name"], "full_name": user_info["full_name"]}, "timestamp": datetime.now().isoformat()}
            # )
            
        except Exception as e:
            import traceback
            self.logger.error(f"用户登录失败: {str(e)}\n{traceback.format_exc()}")
            return JSONResponse(
                status_code=500,
                content={"success": False, "message": f"登录失败: {str(e)}", "timestamp": datetime.now().isoformat()}
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
        user_server = UserDataServer(sql_config_path=SQL_CONFIG_PATH)
        response = await user_server.get_user_data()
        print(response)
        
    asyncio.run(main())