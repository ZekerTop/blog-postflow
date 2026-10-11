"""应用组装：只做接线（配置 → 实例 → 路由 → 中间件），不写业务逻辑。"""
import logging
from collections.abc import Callable
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from .api import articles as articles_routes
from .api import auth as auth_routes
from .api import config as config_routes
from .api import posts as posts_routes
from .core.config import Settings, ensure_session_secret, get_settings
from .core.errors import AppError
from .core.logging import setup_logging
from .integrations.github import GitHub
from .services.ai import AIService
from .services.articles import ArticleService
from .services.config import ConfigService
from .services.publisher import Publisher
from .storage.config_store import ConfigStore
from .storage.publish_store import PublishStore

STATIC = Path(__file__).parent / "static"
# 只加载本站脚本（防 XSS 注入外部脚本）、不许被别的网站嵌入（防点击劫持）；HSTS 由 nginx 加
SECURITY_HEADERS = {
    "Content-Security-Policy": "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
                               "img-src 'self' data:; connect-src 'self'; font-src 'self'; object-src 'none'; "
                               "base-uri 'none'; form-action 'self'; frame-ancestors 'none'",
    "X-Frame-Options": "DENY",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "same-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=(), payment=()",
    "Cross-Origin-Opener-Policy": "same-origin",
}
log = logging.getLogger("postflow.main")


def create_app(settings: Settings, github_factory: Callable[[str], GitHub] = GitHub) -> FastAPI:
    setup_logging()
    config = ConfigService(settings, ConfigStore(settings.db_file), github_factory)
    announce_setup_code(settings, config)

    @asynccontextmanager
    async def lifespan(_):
        yield
        await config.aclose()

    app = FastAPI(title="blog-postflow", docs_url=None, redoc_url=None, lifespan=lifespan)
    app.state.settings = settings
    app.state.config = config
    app.state.publisher = Publisher(config, PublishStore(settings.db_file))
    app.state.articles = ArticleService(config)
    app.state.ai = AIService(config)

    app.add_middleware(
        SessionMiddleware,
        secret_key=ensure_session_secret(settings),
        max_age=settings.session_days * 86400,
        https_only=settings.cookie_secure,
        same_site="lax",
    )

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        resp = await call_next(request)
        for k, v in SECURITY_HEADERS.items():
            resp.headers.setdefault(k, v)
        if request.url.path.startswith("/api/"):
            resp.headers["Cache-Control"] = "no-store"  # 接口返回不进浏览器 / 代理缓存
        return resp

    @app.exception_handler(AppError)
    async def app_error(_: Request, e: AppError):
        return JSONResponse({"detail": e.message, "code": e.code}, status_code=e.status)

    app.include_router(auth_routes.router)
    app.include_router(config_routes.router)
    app.include_router(posts_routes.router)
    app.include_router(articles_routes.router)
    app.mount("/static", StaticFiles(directory=STATIC), name="static")

    @app.get("/", include_in_schema=False)
    async def index():
        return FileResponse(STATIC / "index.html")

    return app


def announce_setup_code(settings: Settings, config: ConfigService) -> None:
    """首次启动还没密码：初始化码打到日志并写入 data/setup-code.txt（600），只有能登服务器的人看得到。"""
    f = settings.db_file.parent / "setup-code.txt"
    if config.needs_setup():
        f.write_text(config.setup_code + "\n")
        f.chmod(0o600)
        log.warning("首次使用：打开页面，用初始化码 %s 设置登录密码（也在 %s）", config.setup_code, f)
    elif f.exists():
        f.unlink()


def app_from_env() -> FastAPI:
    return create_app(get_settings())
