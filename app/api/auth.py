import logging
import secrets

from fastapi import APIRouter, Depends, Request

from ..core.errors import AppError
from ..services.config import ConfigService
from ..services.publisher import Publisher
from ..core.security import password_version
from .deps import client_key, get_config, get_publisher, require_login
from .schemas import LoginIn, PasswordIn, SetupIn

router = APIRouter(prefix="/api")
log = logging.getLogger("postflow.auth")


def start_session(request: Request) -> dict:
    request.session.clear()
    request.session["user"] = "owner"
    request.session["csrf"] = secrets.token_urlsafe(32)
    request.session["pv"] = password_version(request.app.state.config.password_hash())
    return {"csrf": request.session["csrf"]}


@router.get("/setup")
async def setup_status(config: ConfigService = Depends(get_config)):
    return {"needs_setup": config.needs_setup()}


@router.post("/setup")
async def setup(data: SetupIn, request: Request, config: ConfigService = Depends(get_config)):
    config.setup(data.code, data.password, client_key(request))
    return start_session(request)


@router.post("/login")
async def login(data: LoginIn, request: Request, config: ConfigService = Depends(get_config)):
    try:
        config.login(data.password, client_key(request))
    except AppError:
        log.warning("login failed from %s", client_key(request))
        raise
    return start_session(request)


@router.post("/logout", dependencies=[Depends(require_login)])
async def logout(request: Request):
    request.session.clear()
    return {"ok": True}


@router.post("/password", dependencies=[Depends(require_login)])
async def change_password(data: PasswordIn, request: Request, config: ConfigService = Depends(get_config)):
    config.change_password(data.current, data.new)
    return {"ok": True} | start_session(request)  # 当前设备换新会话继续用，其他设备的会话失效


@router.get("/me", dependencies=[Depends(require_login)])
async def me(request: Request, publisher: Publisher = Depends(get_publisher)):
    blogs = [{"id": b.id, "name": b.name, "repo": b.repo, "branch": b.branch, "adapter": b.adapter}
             for b in publisher.blogs.values()]
    return {"csrf": request.session["csrf"], "blogs": blogs}
