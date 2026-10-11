"""分层规则的自动检查。违反时说明代码放错了层，按 docs/ARCHITECTURE.md 调整，不要改这里放行。"""
import ast
from pathlib import Path

APP = Path(__file__).resolve().parent.parent / "app"

# 每层允许依赖的 app 内部层（自身总是允许）
ALLOWED = {
    "core": set(),
    "domain": set(),
    "adapters": {"domain"},
    "integrations": {"core", "domain"},
    "storage": {"core", "domain"},
    "services": {"core", "domain", "adapters", "integrations", "storage"},
    "api": {"core", "domain", "integrations", "services"},
}
# 只有 api 层和 main.py 能碰 Web 框架
WEB = {"fastapi", "starlette"}


def imports(path: Path) -> list[tuple[str, int]]:
    """返回 (被导入模块的绝对名, 行号)。相对导入按文件位置解析。"""
    pkg = path.relative_to(APP.parent).with_suffix("").parts[:-1]
    out = []
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            out += [(a.name, node.lineno) for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base = pkg[: len(pkg) - node.level + 1]
                name = ".".join(base + ((node.module,) if node.module else ()))
            else:
                name = node.module
            out.append((name, node.lineno))
    return out


def test_layer_dependencies():
    errors = []
    for layer, allowed in ALLOWED.items():
        for f in (APP / layer).rglob("*.py"):
            for name, line in imports(f):
                top = name.split(".")[0]
                if top in WEB and layer != "api":
                    errors.append(f"{f.relative_to(APP)}:{line} 非 api 层导入了 {name}")
                parts = name.split(".")
                if parts[0] == "app" and len(parts) > 1:
                    target = parts[1]
                    if target != layer and target not in allowed:
                        errors.append(f"{f.relative_to(APP)}:{line} {layer} 层不允许依赖 {target}（{name}）")
    assert not errors, "\n".join(errors)
