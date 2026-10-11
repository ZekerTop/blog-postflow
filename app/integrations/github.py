import base64
from urllib.parse import quote

import httpx

from ..core.errors import UpstreamError

API = "https://api.github.com"


class GitHubError(UpstreamError):
    pass


class GitHub:
    def __init__(self, token: str, transport: httpx.AsyncBaseTransport | None = None):
        self.client = httpx.AsyncClient(
            base_url=API,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            timeout=30,
            transport=transport,
        )

    async def _check(self, r: httpx.Response) -> dict:
        if r.status_code >= 400:
            try:
                msg = r.json().get("message", r.text)
            except ValueError:
                msg = r.text
            raise GitHubError(f"GitHub {r.status_code}: {msg}")
        return r.json()

    async def file_sha(self, repo: str, path: str, branch: str) -> str | None:
        r = await self.client.get(f"/repos/{repo}/contents/{quote(path)}", params={"ref": branch})
        if r.status_code == 404:
            return None
        return (await self._check(r))["sha"]

    async def put_file(self, repo: str, path: str, branch: str, content: str, message: str, sha: str | None) -> dict:
        body = {
            "message": message,
            "content": base64.b64encode(content.encode()).decode(),
            "branch": branch,
        }
        if sha:
            body["sha"] = sha
        r = await self.client.put(f"/repos/{repo}/contents/{quote(path)}", json=body)
        data = await self._check(r)
        return {"commit_sha": data["commit"]["sha"], "commit_url": data["commit"]["html_url"]}

    async def get_file(self, repo: str, path: str, branch: str) -> tuple[str, str]:
        """返回 (文本内容, sha)。"""
        r = await self.client.get(f"/repos/{repo}/contents/{quote(path)}", params={"ref": branch})
        if r.status_code == 404:
            raise GitHubError(f"文件不存在：{path}")
        data = await self._check(r)
        return base64.b64decode(data["content"]).decode("utf-8"), data["sha"]

    async def list_files(self, repo: str, branch: str) -> list[str]:
        """分支上的全部文件路径（git tree，递归）。"""
        data = await self._check(await self.client.get(f"/repos/{repo}/git/trees/{quote(branch)}", params={"recursive": "1"}))
        if data.get("truncated"):
            raise GitHubError("仓库文件太多，GitHub 返回的列表被截断了")
        return [t["path"] for t in data["tree"] if t["type"] == "blob"]

    async def commit_files(self, repo: str, branch: str, message: str, changes: dict[str, str | None]) -> dict:
        """一次提交多个改动（内容 = 写入，None = 删除），要么全成功要么全不生效。"""
        ref = await self._check(await self.client.get(f"/repos/{repo}/git/ref/heads/{quote(branch)}"))
        head = ref["object"]["sha"]
        base_tree = (await self._check(await self.client.get(f"/repos/{repo}/git/commits/{head}")))["tree"]["sha"]
        tree = [{"path": p, "mode": "100644", "type": "blob", "sha": None} if c is None
                else {"path": p, "mode": "100644", "type": "blob", "content": c} for p, c in changes.items()]
        new_tree = await self._check(await self.client.post(f"/repos/{repo}/git/trees", json={"base_tree": base_tree, "tree": tree}))
        commit = await self._check(await self.client.post(f"/repos/{repo}/git/commits",
                                                           json={"message": message, "tree": new_tree["sha"], "parents": [head]}))
        await self._check(await self.client.patch(f"/repos/{repo}/git/refs/heads/{quote(branch)}", json={"sha": commit["sha"]}))
        return {"commit_sha": commit["sha"], "commit_url": commit["html_url"]}

    async def check_target(self, repo: str, branch: str, posts_dir: str) -> list[str]:
        """配置自检：仓库可访问、Token 有写权限、分支存在、文章目录存在。返回问题列表，空 = 通过。"""
        r = await self.client.get(f"/repos/{repo}")
        if r.status_code in (401, 403, 404):
            hint = {401: "Token 无效或已过期", 403: "Token 无权访问", 404: "仓库不存在，或 Token 没授权这个仓库"}
            return [f"GitHub {r.status_code}：{hint[r.status_code]}"]
        info = await self._check(r)
        problems = []
        if not info.get("permissions", {}).get("push"):
            problems.append("Token 对这个仓库没有写权限（需要 Contents: Read and write）")
        r = await self.client.get(f"/repos/{repo}/branches/{quote(branch)}")
        if r.status_code == 404:
            return problems + [f"分支 {branch} 不存在"]
        await self._check(r)
        r = await self.client.get(f"/repos/{repo}/contents/{quote(posts_dir.rstrip('/'))}", params={"ref": branch})
        if r.status_code == 404:
            problems.append(f"目录 {posts_dir} 在分支 {branch} 上不存在")
        else:
            await self._check(r)
        return problems

    async def runs_for_commit(self, repo: str, sha: str) -> list[dict]:
        r = await self.client.get(f"/repos/{repo}/actions/runs", params={"head_sha": sha, "per_page": 5})
        data = await self._check(r)
        return [
            {"name": w["name"], "status": w["status"], "conclusion": w["conclusion"], "url": w["html_url"]}
            for w in data.get("workflow_runs", [])
        ]

    async def aclose(self) -> None:
        await self.client.aclose()
