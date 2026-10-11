"""密码哈希与登录限速。与 Web 框架无关；会话/CSRF 校验在 api/deps.py。"""
import hashlib
import hmac
import ipaddress
import secrets
import socket
import time
from collections import defaultdict, deque
from urllib.parse import urlparse

from .errors import BadRequest, TooManyRequests

N, R, P = 2**14, 8, 1
MAX_FAILS, WINDOW = 5, 15 * 60


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    h = hashlib.scrypt(password.encode(), salt=salt, n=N, r=R, p=P)
    return f"scrypt${salt.hex()}${h.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, salt, h = stored.split("$")
    except ValueError:
        return False
    if algo != "scrypt":
        return False
    calc = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=N, r=R, p=P)
    return hmac.compare_digest(calc.hex(), h)


def password_version(stored_hash: str) -> str:
    """写进会话的密码指纹：改密码后旧会话全部失效。"""
    return hashlib.sha256(stored_hash.encode()).hexdigest()[:16]


def real_ip(peer: str, x_real_ip: str | None, trusted: list[str]) -> str:
    """反代后面拿真实访客 IP：只有对端是受信任的代理时才采用 X-Real-IP，否则伪造的头会被忽略。"""
    try:
        peer_ip = ipaddress.ip_address(peer)
    except ValueError:
        return peer
    if x_real_ip and any(peer_ip in ipaddress.ip_network(n, strict=False) for n in trusted):
        try:
            return str(ipaddress.ip_address(x_real_ip.strip()))
        except ValueError:
            pass
    return peer


def check_public_url(url: str) -> None:
    """只允许指向公网的 http(s) 地址：解析出的任一 IP 是本机 / 内网 / 链路本地 / 保留地址就拒绝。"""
    u = urlparse(url)
    if u.scheme not in ("http", "https") or not u.hostname:
        raise BadRequest("接口地址要以 http:// 或 https:// 开头")
    try:
        infos = socket.getaddrinfo(u.hostname, u.port or (443 if u.scheme == "https" else 80), proto=socket.IPPROTO_TCP)
    except socket.gaierror:
        raise BadRequest(f"接口地址的域名解析失败：{u.hostname}")
    for info in infos:
        ip = ipaddress.ip_address(info[4][0].split("%")[0])
        if not ip.is_global:
            raise BadRequest("接口地址不能是本机或内网地址（安全限制，防止借此访问服务器内网服务）")


class LoginLimiter:
    def __init__(self):
        self.fails: dict[str, deque[float]] = defaultdict(deque)

    def check(self, key: str) -> None:
        q = self.fails[key]
        now = time.time()
        while q and now - q[0] > WINDOW:
            q.popleft()
        if len(q) >= MAX_FAILS:
            raise TooManyRequests("失败次数过多，15 分钟后再试")

    def fail(self, key: str) -> None:
        self.fails[key].append(time.time())

    def reset(self, key: str) -> None:
        self.fails.pop(key, None)

