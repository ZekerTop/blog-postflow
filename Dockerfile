# Postflow 运行镜像：只含运行代码（不含测试、样本、文档、.git）；以非 root 用户运行
FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    POSTFLOW_DB_FILE=/data/postflow.db POSTFLOW_BLOGS_FILE=/data/blogs.yml POSTFLOW_COOKIE_SECURE=true
WORKDIR /app
COPY requirements.txt .
RUN grep -v '^pytest' requirements.txt > /tmp/req.txt && pip install --no-cache-dir -r /tmp/req.txt && rm /tmp/req.txt \
    && useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin postflow
COPY app ./app
USER 10001
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/setup', timeout=4)"
CMD ["uvicorn", "--factory", "app.main:app_from_env", "--host", "0.0.0.0", "--port", "8000", "--no-server-header"]
