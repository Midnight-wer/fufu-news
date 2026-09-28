"""
fufu新闻 - 统一响应格式
==========================
定义所有 API 接口的统一响应结构。

响应格式规范：
- 成功: { "code": 200, "data": <实际数据>, "message": "ok" }
- 失败: { "code": <HTTP状态码>, "data": [], "message": "<错误提示>" }

关键约定：
- data 字段永远不会是 None（成功时有数据，失败时为空数组 []）
- code 字段在成功时固定为 200，失败时为对应 HTTP 状态码
- message 字段在成功时为 "ok"，失败时为业务友好的错误提示
"""
from typing import Any, TypeVar, Generic
from pydantic import BaseModel

T = TypeVar("T")  # 泛型类型变量


class ApiResponse(BaseModel, Generic[T]):
    """
    统一 API 响应包装模型。

    泛型参数 T 为 data 字段的实际数据类型。
    可用于 OpenAPI 文档自动生成时指定响应类型。
    """
    code: int = 200
    data: T | list = []  # 支持指定类型或默认空列表
    message: str = "ok"


def success(data: Any = [], message: str = "ok") -> dict:
    """
    构建成功响应。

    参数:
        data: 响应数据（list/dict/对象），默认为空列表
        message: 成功消息，默认 "ok"

    返回:
        dict: 格式为 {"code": 200, "data": ..., "message": ...} 的字典

    注意:
        data 永远不会返回 None——如果传入 None，将被替换为空列表 []
    """
    return {
        "code": 200,
        "data": data if data is not None else [],
        "message": message,
    }


def error(code: int = 500, message: str = "服务器开小差了～") -> dict:
    """
    构建错误响应。

    参数:
        code: HTTP 错误状态码（如 400, 401, 404, 500 等）
        message: 错误提示消息（业务友好的中文描述）

    返回:
        dict: 格式为 {"code": <code>, "data": [], "message": ...} 的字典

    注意:
        错误响应的 data 固定为空数组 []，不传递任何业务数据。
    """
    return {
        "code": code,
        "data": [],
        "message": message,
    }
