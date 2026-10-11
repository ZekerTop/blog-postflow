"""「设置」页接口：Token / Key / 模型、博客增删改查与自检。全部需要登录 + CSRF。"""
import yaml
from fastapi import APIRouter, Depends

from ..services.config import ConfigService
from .deps import get_ai, get_config, require_login
from ..services.ai import PROVIDERS, AIService
from .schemas import AITestIn, BlogIn, SecretsIn

router = APIRouter(prefix="/api/config", dependencies=[Depends(require_login)])


def blog_out(b, config: ConfigService) -> dict:
    """博客专用 Token 只回传是否已设置和末 4 位。"""
    dump = lambda d: yaml.safe_dump(d, allow_unicode=True, sort_keys=False).strip() if d else ""  # noqa: E731
    return b.model_dump(exclude={"category_dirs", "options"}) | {
        "category_dirs_yaml": dump(b.category_dirs), "options_yaml": dump(b.options)} | config.blog_token_view(b.id)


@router.get("")
async def get_all(config: ConfigService = Depends(get_config)):
    return {"secrets": config.secrets_view(), "blogs": [blog_out(b, config) for b in config.blogs()],
            "adapters": config.adapters(), "presets": config.presets(), "ai_providers": PROVIDERS}


@router.post("/secrets")
async def save_secrets(data: SecretsIn, config: ConfigService = Depends(get_config)):
    config.update_secrets(data.model_dump())
    return config.secrets_view()


@router.post("/ai/test")
async def test_ai(data: AITestIn, ai: AIService = Depends(get_ai)):
    return await ai.test(data.model_dump())


@router.post("/blogs")
async def add_blog(data: BlogIn, config: ConfigService = Depends(get_config)):
    return blog_out(config.save_blog(data.model_dump(), is_new=True), config)


@router.post("/blogs/{blog_id}")
async def update_blog(blog_id: str, data: BlogIn, config: ConfigService = Depends(get_config)):
    return blog_out(config.save_blog(data.model_dump() | {"id": blog_id}, is_new=False), config)


@router.post("/blogs/{blog_id}/delete")
async def delete_blog(blog_id: str, config: ConfigService = Depends(get_config)):
    config.delete_blog(blog_id)
    return {"ok": True}


@router.post("/blogs/{blog_id}/check")
async def check_blog(blog_id: str, config: ConfigService = Depends(get_config)):
    return await config.check_blog(blog_id)
