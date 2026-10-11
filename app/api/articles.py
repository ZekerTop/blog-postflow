"""「文章」页接口：列出 / 载入 / 删除已发布文章。全部需要登录 + CSRF。"""
from fastapi import APIRouter, Depends

from ..services.articles import ArticleService
from .deps import get_articles, require_login
from .schemas import ArticlePathIn

router = APIRouter(prefix="/api/blogs/{blog_id}/articles", dependencies=[Depends(require_login)])


@router.get("")
async def list_articles(blog_id: str, articles: ArticleService = Depends(get_articles)):
    return await articles.list(blog_id)


@router.get("/file")
async def load_article(blog_id: str, path: str, articles: ArticleService = Depends(get_articles)):
    return await articles.load(blog_id, path)


@router.post("/delete")
async def delete_article(blog_id: str, data: ArticlePathIn, articles: ArticleService = Depends(get_articles)):
    return await articles.delete(blog_id, data.path)
