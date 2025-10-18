#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time    : 2025/10/17 16:20
@Author  : weiyutao
@File    : sms_verification_server.py
"""

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from datetime import datetime
import logging
from pydantic import BaseModel
from typing import Optional
import asyncio
import json
import random
import re
import redis.asyncio as redis
import yaml
from pathlib import Path
from dotenv import dotenv_values

# 导入你现有的短信发送模块
from alibabacloud_dysmsapi20170525.client import Client as Dysmsapi20170525Client
from alibabacloud_tea_openapi import models as open_api_models
from alibabacloud_dysmsapi20170525 import models as dysmsapi_20170525_models
from alibabacloud_tea_util import models as util_models


class SMSRequest(BaseModel):
    """发送短信验证码请求模型"""
    phone: str
    scene: Optional[str] = "register"  # register, login, reset_password


class SMSVerifyRequest(BaseModel):
    """验证短信验证码请求模型"""
    phone: str
    code: str
    scene: Optional[str] = "register"


class SMSVerificationServer:
    """短信验证码服务类"""

    def __init__(self, env_path: str, redis_config_path: str):
        self.env_path = env_path
        self.redis_config_path = redis_config_path
        self.logger = logging.getLogger(self.__class__.__name__)
        self.redis_client = None
        
        # 加载配置
        self._load_env_config()
        self._load_redis_config()
        
        # 初始化阿里云短信客户端
        self._init_sms_client()

    def _load_env_config(self):
        """加载环境配置文件"""
        try:
            environment = dotenv_values(self.env_path)
            self.access_key_id = environment.get("ACCESS_KEY_ID")
            self.access_key_secret = environment.get("ACCESS_KEY_SECRET")
            self.sms_sign_name = environment.get("SMS_SIGN_NAME")
            self.sms_template_code = environment.get("SMS_TEMPLATE_CODE")
            self.sign_name = environment.get("SMS_SIGN_NAME", self.sms_sign_name)
            self.template_code = environment.get("SMS_TEMPLATE_CODE", self.sms_template_code)
            
            if not self.access_key_id or not self.access_key_secret:
                raise ValueError("ACCESS_KEY_ID 和 ACCESS_KEY_SECRET 必须在环境配置中设置")
                
        except Exception as e:
            self.logger.error(f"加载环境配置失败: {str(e)}")
            raise

    def _load_redis_config(self):
        """加载Redis配置文件"""
        try:
            with open(self.redis_config_path, 'r', encoding='utf-8') as f:
                redis_config = yaml.safe_load(f)
            
            self.redis_host = redis_config.get('host', 'localhost')
            self.redis_port = redis_config.get('port', 6379)
            self.redis_db = redis_config.get('db', 0)
            
            self.logger.info(f"Redis配置加载成功: {self.redis_host}:{self.redis_port}/{self.redis_db}")
            
        except Exception as e:
            self.logger.error(f"加载Redis配置失败: {str(e)}")
            raise

    def _init_sms_client(self):
        """初始化阿里云短信客户端"""
        try:
            config = open_api_models.Config(
                access_key_id=self.access_key_id,
                access_key_secret=self.access_key_secret
            )
            config.endpoint = 'dysmsapi.aliyuncs.com'
            self.sms_client = Dysmsapi20170525Client(config)
            self.logger.info("阿里云短信客户端初始化成功")
        except Exception as e:
            self.logger.error(f"初始化阿里云短信客户端失败: {str(e)}")
            raise

    async def _get_redis_client(self):
        """获取Redis客户端"""
        if not self.redis_client:
            try:
                self.redis_client = redis.Redis(
                    host=self.redis_host,
                    port=self.redis_port,
                    db=self.redis_db,
                    decode_responses=True
                )
                # 测试连接
                await self.redis_client.ping()
                self.logger.info(f"Redis连接成功: {self.redis_host}:{self.redis_port}/{self.redis_db}")
            except Exception as e:
                self.logger.error(f"Redis连接失败: {str(e)}")
                raise
        return self.redis_client

    def register_routes(self, app: FastAPI):
        """注册短信验证码相关的路由"""
        app.post("/api/sms/send")(self.send_verification_code)
        app.post("/api/sms/verify")(self.verify_code)
        app.get("/api/sms/health")(self.health_check)

    def _validate_phone(self, phone: str) -> bool:
        """验证手机号格式"""
        pattern = r'^1[3-9]\d{9}$'
        return bool(re.match(pattern, phone))

    def _generate_code(self) -> str:
        """生成6位数字验证码"""
        return ''.join([str(random.randint(0, 9)) for _ in range(6)])

    async def _check_send_limit(self, phone: str) -> tuple[bool, str]:
        """检查发送频率限制"""
        try:
            redis_client = await self._get_redis_client()
            
            # 检查1分钟内是否已发送
            limit_key = f"sms:limit:{phone}"
            if await redis_client.exists(limit_key):
                ttl = await redis_client.ttl(limit_key)
                return False, f"请{ttl}秒后再试"
            
            return True, ""
        except Exception as e:
            self.logger.error(f"检查发送限制失败: {str(e)}")
            # 如果Redis出错，允许发送但记录错误
            return True, ""

    async def _send_sms(self, phone: str, code: str) -> tuple[bool, str]:
        """发送短信"""
        try:
            send_sms_request = dysmsapi_20170525_models.SendSmsRequest(
                phone_numbers=phone,
                sign_name=self.sign_name,
                template_code=self.template_code,
                template_param=json.dumps({"code": code})
            )
            runtime = util_models.RuntimeOptions()
            
            response = await self.sms_client.send_sms_with_options_async(send_sms_request, runtime)
            
            if response.body.code == 'OK':
                self.logger.info(f"短信发送成功: {phone}")
                return True, "发送成功"
            else:
                self.logger.error(f"短信发送失败: {response.body.message}")
                return False, response.body.message
                
        except Exception as e:
            self.logger.error(f"发送短信异常: {str(e)}")
            return False, f"发送异常: {str(e)}"

    async def _save_code_to_redis(self, phone: str, code: str):
        """保存验证码到Redis"""
        try:
            redis_client = await self._get_redis_client()
            
            # 保存验证码，5分钟过期
            code_key = f"sms:code:{phone}"
            await redis_client.setex(code_key, 300, code)
            
            # 设置发送频率限制，1分钟
            limit_key = f"sms:limit:{phone}"
            await redis_client.setex(limit_key, 60, "1")
            
            self.logger.info(f"验证码已保存到Redis: {phone}")
        except Exception as e:
            self.logger.error(f"保存验证码到Redis失败: {str(e)}")
            raise

    async def send_verification_code(self, sms_request: SMSRequest):
        """
        POST请求 - 发送短信验证码
        """
        try:
            self.logger.info(f"收到发送验证码请求: {sms_request}")
            
            # 验证手机号格式
            if not self._validate_phone(sms_request.phone):
                return JSONResponse(
                    status_code=400,
                    content={
                        "success": False, 
                        "message": "手机号格式错误", 
                        "timestamp": datetime.now().isoformat()
                    }
                )
            
            # 检查发送频率限制
            can_send, limit_message = await self._check_send_limit(sms_request.phone)
            if not can_send:
                return JSONResponse(
                    status_code=429,
                    content={
                        "success": False, 
                        "message": limit_message, 
                        "timestamp": datetime.now().isoformat()
                    }
                )
            
            # 生成验证码
            code = self._generate_code()
            self.logger.info(f"为手机号 {sms_request.phone} 生成验证码: {code}")
            
            # 发送短信
            send_success, send_message = await self._send_sms(sms_request.phone, code)
            if not send_success:
                return JSONResponse(
                    status_code=500,
                    content={
                        "success": False, 
                        "message": f"短信发送失败: {send_message}", 
                        "timestamp": datetime.now().isoformat()
                    }
                )
            
            # 保存验证码到Redis
            await self._save_code_to_redis(sms_request.phone, code)
            
            return JSONResponse(
                status_code=200,
                content={
                    "success": True, 
                    "message": "验证码发送成功", 
                    "data": {"expire_time": 300},
                    "timestamp": datetime.now().isoformat()
                }
            )
            
        except Exception as e:
            self.logger.error(f"发送验证码失败: {str(e)}")
            return JSONResponse(
                status_code=500,
                content={
                    "success": False, 
                    "message": f"发送失败: {str(e)}", 
                    "timestamp": datetime.now().isoformat()
                }
            )

    async def verify_code(self, verify_request: SMSVerifyRequest):
        """
        POST请求 - 验证短信验证码
        """
        try:
            self.logger.info(f"收到验证码验证请求: {verify_request}")
            
            # 验证手机号格式
            if not self._validate_phone(verify_request.phone):
                return JSONResponse(
                    status_code=400,
                    content={
                        "success": False, 
                        "message": "手机号格式错误", 
                        "timestamp": datetime.now().isoformat()
                    }
                )
            
            # 从Redis获取验证码
            redis_client = await self._get_redis_client()
            code_key = f"sms:code:{verify_request.phone}"
            stored_code = await redis_client.get(code_key)
            
            if not stored_code:
                return JSONResponse(
                    status_code=400,
                    content={
                        "success": False, 
                        "message": "验证码已过期或不存在", 
                        "timestamp": datetime.now().isoformat()
                    }
                )
            
            # 验证验证码
            if stored_code != verify_request.code:
                return JSONResponse(
                    status_code=400,
                    content={
                        "success": False, 
                        "message": "验证码错误", 
                        "timestamp": datetime.now().isoformat()
                    }
                )
            
            # 验证成功，删除验证码
            await redis_client.delete(code_key)
            self.logger.info(f"手机号 {verify_request.phone} 验证码验证成功")
            
            return JSONResponse(
                status_code=200,
                content={
                    "success": True, 
                    "message": "验证成功", 
                    "data": {"phone": verify_request.phone, "scene": verify_request.scene},
                    "timestamp": datetime.now().isoformat()
                }
            )
            
        except Exception as e:
            self.logger.error(f"验证验证码失败: {str(e)}")
            return JSONResponse(
                status_code=500,
                content={
                    "success": False, 
                    "message": f"验证失败: {str(e)}", 
                    "timestamp": datetime.now().isoformat()
                }
            )

    async def health_check(self):
        """
        GET请求 - 健康检查
        """
        try:
            # 检查Redis连接
            redis_client = await self._get_redis_client()
            await redis_client.ping()
            redis_status = "healthy"
        except Exception as e:
            redis_status = f"error: {str(e)}"
        
        return JSONResponse(
            status_code=200,
            content={
                "success": True,
                "message": "短信验证服务运行正常",
                "data": {
                    "service": "sms_verification",
                    "redis_status": redis_status,
                    "sms_provider": "alibaba_cloud"
                },
                "timestamp": datetime.now().isoformat()
            }
        )

    async def close(self):
        """关闭连接"""
        if self.redis_client:
            await self.redis_client.aclose()
            self.logger.info("Redis连接已关闭")


if __name__ == '__main__':
    import sys
    from pathlib import Path
    
    # 配置路径 - 参考你的项目结构
    ROOT_DIRECTORY = Path(__file__).parent.parent.parent.parent
    ENV_PATH = str(ROOT_DIRECTORY / ".env")
    REDIS_CONFIG_PATH = str(ROOT_DIRECTORY / "config" / "yaml" / "redis_config.yaml")
    
    # 测试发送验证码
    async def test_send():
        sms_server = SMSVerificationServer(env_path=ENV_PATH, redis_config_path=REDIS_CONFIG_PATH)
        
        # 测试发送
        sms_request = SMSRequest(phone="17600174284", scene="register")
        response = await sms_server.send_verification_code(sms_request)
        print("发送响应:", response.body)
        
        # 测试验证（需要手动输入收到的验证码）
        if len(sys.argv) > 1:
            test_code = sys.argv[1]
            verify_request = SMSVerifyRequest(phone="17600174284", code=test_code, scene="register")
            verify_response = await sms_server.verify_code(verify_request)
            print("验证响应:", verify_response.body)
        
        await sms_server.close()
    
    # 运行测试
    if __name__ == '__main__':
        print("测试短信验证码服务")
        print("用法: python sms_verification_server.py [验证码]")
        asyncio.run(test_send())