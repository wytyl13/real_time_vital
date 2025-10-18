#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time    : 2025/10/16 10:11
@Author  : weiyutao
@File    : base.py
"""

from sqlalchemy.ext.declarative import declarative_base

# 创建统一的Base类
Base = declarative_base()