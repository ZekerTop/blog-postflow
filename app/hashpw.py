"""生成登录密码哈希：python -m app.hashpw，把输出填进 .env 的 POSTFLOW_PASSWORD_HASH。"""
import getpass

from .core.security import hash_password

if __name__ == "__main__":
    pw = getpass.getpass("新密码：")
    if pw != getpass.getpass("再输一次："):
        raise SystemExit("两次不一致")
    print(hash_password(pw))
