"""业务异常。services 层只抛这些，不依赖 FastAPI；api 层统一转成 HTTP 响应。

响应格式：{"detail": "给人看的中文信息", "code": "机器可读的错误码"}
排障时按 code 在日志里搜。
"""


class AppError(Exception):
    status = 400
    code = "bad_request"

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class BadRequest(AppError):
    pass


class Unauthorized(AppError):
    status, code = 401, "unauthorized"


class Forbidden(AppError):
    status, code = 403, "forbidden"


class NotFound(AppError):
    status, code = 404, "not_found"


class Conflict(AppError):
    status, code = 409, "conflict"


class UpstreamError(AppError):
    """GitHub / Claude 等外部服务出错。"""

    status, code = 502, "upstream_error"


class TooManyRequests(AppError):
    status, code = 429, "rate_limited"
