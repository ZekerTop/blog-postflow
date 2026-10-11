"""路由依赖：从 app.state 取服务实例；会话与 CSRF 校验。"""
import hmac

from fastapi import Request

from ..core.errors import Forbidden, Unauthorized
from ..core.security import password_version, real_ip
from ..services.ai import AIService
from ..services.articles import ArticleService
from ..services.config import ConfigService
from ..services.publisher import Publisher


def get_publisher(request: Request) -> Publisher:
    return request.app.state.publisher


def get_config(request: Request) -> ConfigService:
    return request.app.state.config


def get_ai(request: Request) -> AIService:
    return request.app.state.ai


def get_articles(request: Request) -> ArticleService:
    return request.app.state.articles


def client_key(request: Request) -> str:
    """登录限速按真实访客 IP 计；在 nginx 后面时取它传来的 X-Real-IP（仅限受信任代理）。"""
    peer = request.client.host if request.client else "?"
    return real_ip(peer, request.headers.get("x-real-ip"), request.app.state.settings.trusted_proxies)


def require_login(request: Request) -> None:
    if not request.session.get("user"):
        raise Unauthorized("未登录")
    if request.session.get("pv") != password_version(request.app.state.config.password_hash()):
        request.session.clear()  # 密码改过：其他设备上的旧会话作废
        raise Unauthorized("密码已修改，请重新登录")
    if request.method != "GET":
        token = request.headers.get("x-csrf-token", "")
        if not hmac.compare_digest(token, request.session.get("csrf", "")):
            raise Forbidden("CSRF 校验失败，请刷新页面")
