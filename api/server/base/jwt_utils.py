#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time    : 2025/11/17 06:42
@Author  : weiyutao
@File    : jwt_utils.py
"""


import jwt
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from fastapi import HTTPException, status, Depends
from fastapi.security import OAuth2PasswordBearer

from dotenv import dotenv_values
from pathlib import Path

ROOT_DIRECTORY = Path(__file__).parent.parent.parent.parent
ENV_PATH = str(ROOT_DIRECTORY / ".env")
env_config = dotenv_values(ENV_PATH)

SECRET_KEY = env_config.get("JWT_SECRET_KEY", "sxkj-real-time-vital-analyze")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(env_config.get("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "30"))

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/user_data/login")

def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(token: str = Depends(oauth2_scheme)) -> Dict[str, Any]:
    """验证token并返回：用户名 + id（核心修改）"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="无法验证凭据",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        id: int = payload.get("id")
        role: str = payload.get("role")
        
        if username is None or id is None or role is None:
            raise credentials_exception
        return {"username": username, "id": id, "role": role}
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="token已过期，请重新登录")
    except jwt.InvalidSignatureError:
        raise HTTPException(status_code=401, detail="token签名无效")
    except jwt.PyJWTError:
        raise credentials_exception
