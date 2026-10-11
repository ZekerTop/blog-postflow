from fastapi import APIRouter, Depends

from ..domain.slug import slugify
from ..services.ai import AIService
from ..services.publisher import Publisher
from .deps import get_ai, get_publisher, require_login
from .schemas import EnrichIn, PublishIn, RetryIn

router = APIRouter(prefix="/api", dependencies=[Depends(require_login)])


@router.get("/slug")
async def slug(title: str = ""):
    """按标题生成拼音网址（输入标题时实时调用）。"""
    return {"slug": slugify(title[:200])}


@router.post("/enrich")
async def enrich(data: EnrichIn, ai: AIService = Depends(get_ai)):
    return await ai.suggest(data.title, data.body)


@router.post("/preview")
async def preview(data: PublishIn, publisher: Publisher = Depends(get_publisher)):
    return await publisher.preview(data.post, data.blog_ids, data.paths)


@router.post("/publish")
async def publish(data: PublishIn, publisher: Publisher = Depends(get_publisher)):
    return await publisher.publish(data.post, data.blog_ids, data.overwrite, data.paths)


@router.post("/publish/{pid}/retry")
async def retry(pid: int, data: RetryIn, publisher: Publisher = Depends(get_publisher)):
    return await publisher.retry(pid, data.blog_ids, data.overwrite)


@router.get("/status/{pid}")
async def status(pid: int, publisher: Publisher = Depends(get_publisher)):
    return await publisher.status(pid)


@router.get("/history")
async def history(publisher: Publisher = Depends(get_publisher)):
    return publisher.history()
