# 部署与运维

推荐：一台有 Docker 的 Linux 服务器 + nginx 反代 + HTTPS。Postflow 本身只需要很少的资源（实测内存限 384M 足够）。

## 结构

```
浏览器 ─HTTPS─▶ nginx（postflow.example.com，Let's Encrypt）
                 └─ 反代 ─▶ 127.0.0.1:8790 ─▶ Docker 容器 postflow（uvicorn :8000）
                                              └─ /data ⇐ /opt/postflow/data（SQLite、会话密钥、备份）
```

- 服务器上**不需要源码、git、仓库密钥**，只有镜像和数据。GitHub Token / AI Key 在网页「设置」里填，存在 `/opt/postflow/data/postflow.db`（建议 600）。
- 容器加固：uid 10001、只读根文件系统、`--cap-drop ALL`、`no-new-privileges`、限制内存和进程数、只绑 127.0.0.1。
- nginx 示例：`deploy/nginx.example.conf`。**必须保留 `proxy_cache off` 和 `proxy_next_upstream off`**：有些面板的全局配置默认开缓存和出错重试，会让接口串号、发布请求被重发。登录 / 首次设置接口在 nginx 层限流 10 次/分钟（应用内另有 5 次/15 分钟的登录限速）。

## 第一次部署

```sh
# 1. 构建镜像（在服务器上，或本机打好 linux/amd64 镜像再 docker save / load）
docker build -t postflow:latest .

# 2. 安装运维命令，按需修改脚本顶部的端口、域名、路径
sudo install -m 755 deploy/postflow /usr/local/bin/postflow
sudo mkdir -p /opt/postflow/data /opt/postflow/cert && sudo chown 10001:10001 /opt/postflow/data

# 3. 启动
POSTFLOW_DOMAIN=postflow.example.com postflow start

# 4. 配 nginx（deploy/nginx.example.conf）和证书后，取初始化码，打开网页设置登录密码
postflow setup-code
```

`postflow` 脚本里的证书续期用 acme.sh 的 Docker 镜像（webroot 模式）。你也可以用 certbot 或面板自带的证书，那样就不需要 `cert-renew`。

建议的定时任务（`/etc/cron.d/postflow`）：

```
30 3 * * * root /usr/local/bin/postflow backup >/dev/null 2>&1
15 4 * * * root /usr/local/bin/postflow cert-renew >/dev/null 2>&1
```

## 日常命令（服务器上）

```
postflow status      # 容器状态 + 本机 / 外网健康检查
postflow logs 200    # 最近日志
postflow restart     # 重启（也会清空登录失败计数）
postflow backup      # 立即备份数据库（保留 14 天）
postflow setup-code  # 首次使用的初始化码
postflow update      # 用 /opt/postflow/image.tar.gz 换新版本，失败自动回滚到 postflow:previous
postflow cert-renew  # 续期证书
```

## 发布新版本

```sh
# 本机
.venv/bin/python -m pytest -q
docker build --platform linux/amd64 -t postflow:latest .
docker save postflow:latest | gzip -1 | ssh <your-server> 'cat > /opt/postflow/image.tar.gz'
ssh <your-server> 'postflow update && postflow status'
```

国内网络拉不到 Docker Hub 时，可以先从镜像站拉基础镜像再改名：

```
docker pull --platform linux/amd64 docker.m.daocloud.io/library/python:3.13-slim
docker tag docker.m.daocloud.io/library/python:3.13-slim python:3.13-slim
```

## 回滚

- 代码：`postflow update` 失败会自动回滚；手动回滚 `docker rm -f postflow` 后用 `postflow:previous` 镜像重新启动。
- 数据：停容器，把 `data/backups/` 里的某个备份拷回 `data/postflow.db`（属主 10001），再启动。
- 整个下线：删 nginx 配置并重载，`docker rm -f postflow`。
