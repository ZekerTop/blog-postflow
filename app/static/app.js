const $ = id => document.getElementById(id);
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const list = s => s.split(/[,，、]/).map(x => x.trim()).filter(Boolean);
const icon = name => `<svg><use href="#i-${name}"/></svg>`;
const store = {  // 浏览器本地存储只放草稿和界面偏好；隐私模式下可能不可用，失败就当没有
  get(k) { try { return localStorage.getItem(k); } catch { return null; } },
  set(k, v) { try { v === null ? localStorage.removeItem(k) : localStorage.setItem(k, v); } catch {} },
};
const IS_MAC = /Mac|iPhone|iPad/.test(navigator.platform);
const SLUG_RE = /^[0-9A-Za-z\u4e00-\u9fff]+(?:[-_][0-9A-Za-z\u4e00-\u9fff]+)*$/;  // 与后端 domain/post.py 一致
const SLUG_RECOMMENDED = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;
const DRAFT_KEY = "pf-draft", DRAFT_FIELDS = ["body", "title", "slug", "date", "categories", "tags", "keywords", "description", "cover"];

let csrf = "", blogs = [], adapters = [], currentId = null, previews = [], editingBlog = null, records = [];
let editing = null;  // 正在编辑的已发布文章 { blog_id, path }：发布时写回原文件
let articles = [];

/* ---------- 基础 ---------- */
async function api(path, body) {
  const opt = body === undefined ? {} : { method: "POST", headers: { "Content-Type": "application/json", "X-CSRF-Token": csrf }, body: JSON.stringify(body) };
  const r = await fetch(path, opt);
  const data = await r.json().catch(() => ({}));
  if (r.status === 401 && !["/api/login", "/api/password"].includes(path)) { showAuth("login"); throw new Error("登录已过期，请重新登录"); }
  if (!r.ok) {
    const d = data.detail;
    throw new Error(typeof d === "string" ? d : Array.isArray(d) ? d.map(e => `${e.loc?.slice(-1)[0] ?? ""} ${e.msg}`).join("；") : `请求失败（${r.status}）`);
  }
  return data;
}

function toast(msg, type = "") {
  const el = document.createElement("div");
  el.className = `toast ${type}`;
  el.innerHTML = `<span class="dot"></span><span>${esc(msg)}</span>`;
  $("toasts").append(el);
  setTimeout(() => { el.classList.add("out"); setTimeout(() => el.remove(), 250); }, type === "err" ? 5000 : 2600);
}

async function busy(btn, fn) {
  btn.classList.add("loading"); btn.disabled = true;
  try { return await fn(); } finally { btn.classList.remove("loading"); btn.disabled = false; }
}

function confirmDialog({ title, text = "", ok = "确定", danger = false, overwrite = null }) {
  const d = $("dlgConfirm");
  $("confirmTitle").textContent = title; $("confirmText").textContent = text;
  $("confirmOk").textContent = ok; $("confirmOk").className = `btn ${danger ? "danger" : "primary"}`;
  const ow = $("confirmOverwrite"); ow.classList.toggle("hidden", overwrite === null);
  ow.querySelector("input").checked = !!overwrite;
  d.showModal();
  return new Promise(resolve => {
    const done = v => { d.close(); $("confirmOk").onclick = null; d.onclose = null; resolve(v); };
    $("confirmOk").onclick = () => done({ ok: true, overwrite: ow.querySelector("input").checked });
    d.onclose = () => resolve({ ok: false });
  });
}

document.querySelectorAll("dialog").forEach(d => {
  d.addEventListener("click", e => {
    const r = d.getBoundingClientRect();
    const outside = e.target === d && (e.clientX < r.left || e.clientX > r.right || e.clientY < r.top || e.clientY > r.bottom);
    if (outside || e.target.closest("[data-close]")) d.close();
  });
});

document.querySelectorAll(".reveal-pw").forEach(b => b.onclick = () => {
  const input = $(b.dataset.for), show = input.type === "password";
  input.type = show ? "text" : "password";
  b.innerHTML = icon(show ? "eye-off" : "eye");
  b.setAttribute("aria-label", show ? "隐藏密码" : "显示密码");
  input.focus();
});

/* ---------- 主题 ---------- */
const THEMES = { auto: ["auto", "跟随系统"], light: ["sun", "亮色"], dark: ["moon", "暗色"] };
function applyTheme(t) {
  if (t === "auto") document.documentElement.removeAttribute("data-theme"); else document.documentElement.dataset.theme = t;
  $("btnTheme").innerHTML = icon(THEMES[t][0]);
  $("btnTheme").title = `主题：${THEMES[t][1]}（点击切换）`;
}
$("btnTheme").onclick = () => {
  const order = ["auto", "light", "dark"], next = order[(order.indexOf(store.get("pf-theme") || "auto") + 1) % 3];
  store.set("pf-theme", next); applyTheme(next); toast(`主题：${THEMES[next][1]}`);
};
applyTheme(store.get("pf-theme") || "auto");

/* ---------- 登录 / 首次设置 ---------- */
const TAGLINES = ["一次粘贴，发布到所有博客", "AI 生成英文网址、描述与关键词", "Hexo · VuePress · Hugo · Jekyll · Astro", "提交即部署，GitHub Actions 接力"];
let typerTimer = 0;
function typer() {
  clearTimeout(typerTimer);
  let line = 0, i = 0, del = false;
  const tick = () => {
    const s = TAGLINES[line];
    $("typer").textContent = s.slice(0, i);
    if (!del && i === s.length) { del = true; typerTimer = setTimeout(tick, 2200); return; }
    if (del && i === 0) { del = false; line = (line + 1) % TAGLINES.length; }
    i += del ? -1 : 1;
    typerTimer = setTimeout(tick, del ? 28 : 70);
  };
  tick();
}

function showAuth(which) {
  stopPolling();
  $("app").classList.add("hidden");
  $("auth").classList.remove("hidden", "leaving");
  $("login").classList.toggle("hidden", which !== "login");
  $("setup").classList.toggle("hidden", which !== "setup");
  fx.start(); typer();
  setTimeout(() => (which === "login" ? $("pw") : $("setupCode")).focus(), 400);
}

async function leaveAuth(btn) {
  const r = btn.getBoundingClientRect();
  fx.burst(r.left + r.width / 2, r.top + r.height / 2);
  $("auth").classList.add("leaving");
  await new Promise(res => setTimeout(res, 650));
  $("auth").classList.add("hidden"); fx.stop(); clearTimeout(typerTimer);
}

function fail(form, msgEl, msg) {
  msgEl.textContent = msg;
  form.classList.remove("shake", "reveal"); void form.offsetWidth; form.classList.add("shake");
}

$("login").onsubmit = e => {
  e.preventDefault();
  $("loginMsg").textContent = "";
  if (!$("pw").value) return fail($("login"), $("loginMsg"), "请输入密码");
  busy($("btnLogin"), async () => {
    try { csrf = (await api("/api/login", { password: $("pw").value })).csrf; $("pw").value = ""; await enterApp($("btnLogin")); }
    catch (err) { fail($("login"), $("loginMsg"), err.message); $("pw").select(); }
  });
};

$("setup").onsubmit = e => {
  e.preventDefault();
  const msg = $("setupMsg"); msg.textContent = "";
  if ($("setupPw").value.length < 8) return fail($("setup"), msg, "密码至少 8 位");
  if ($("setupPw").value !== $("setupPw2").value) return fail($("setup"), msg, "两次输入的密码不一致");
  busy($("btnSetup"), async () => {
    try { csrf = (await api("/api/setup", { code: $("setupCode").value, password: $("setupPw").value })).csrf; await enterApp($("btnSetup")); toast("密码已设置"); }
    catch (err) { fail($("setup"), msg, err.message); }
  });
};

["keydown", "keyup"].forEach(t => $("pw").addEventListener(t, e => {
  if (e.getModifierState) $("capsHint").classList.toggle("hidden", !e.getModifierState("CapsLock"));
}));

$("btnLogout").onclick = async () => {
  const { ok } = await confirmDialog({ title: "退出登录？", text: "草稿会保留在这个浏览器里。", ok: "退出" });
  if (!ok) return;
  await api("/api/logout", {}).catch(() => {});
  showAuth("login");
};

async function boot() {
  try {
    if ((await api("/api/setup")).needs_setup) return showAuth("setup");
    await enterApp();
  } catch { showAuth("login"); }
}

async function enterApp(fromBtn) {
  const me = await api("/api/me");
  csrf = me.csrf; blogs = me.blogs;
  renderTargets();
  restoreDraft();
  try { setEditing(JSON.parse(store.get("pf-editing") || "null")); } catch { setEditing(null); }
  if (fromBtn) await leaveAuth(fromBtn); else { $("auth").classList.add("hidden"); fx.stop(); }
  $("app").classList.remove("hidden");
  $("app").classList.remove("app-enter"); void $("app").offsetWidth; $("app").classList.add("app-enter");
  route();
  if (!store.get("pf-help-seen")) { store.set("pf-help-seen", "1"); setTimeout(() => openHelp("start"), 500); }
}

function localNow() {
  const d = new Date(); d.setMinutes(d.getMinutes() - d.getTimezoneOffset());
  return d.toISOString().slice(0, 16);
}

/* ---------- 路由 ---------- */
function route() {
  const view = ["write", "articles", "history", "settings"].includes(location.hash.slice(1)) ? location.hash.slice(1) : "write";
  document.querySelectorAll("#nav a").forEach(a => a.classList.toggle("on", a.dataset.view === view));
  document.querySelectorAll(".view").forEach(v => v.classList.toggle("hidden", v.id !== `view-${view}`));
  if (view === "history") loadHistory();
  if (view === "articles") loadArticles();
  if (view === "settings") loadConfig();
  window.scrollTo({ top: 0 });
}
window.addEventListener("hashchange", () => { if (!$("app").classList.contains("hidden")) route(); });

/* ---------- 帮助 ---------- */
function openHelp(tab = "start") {
  document.querySelectorAll("#helpTabs button").forEach(b => b.classList.toggle("on", b.dataset.t === tab));
  document.querySelectorAll("#dlgHelp [data-panel]").forEach(p => p.classList.toggle("hidden", p.dataset.panel !== tab));
  if (!$("dlgHelp").open) $("dlgHelp").showModal();
}
$("btnHelp").onclick = () => openHelp();
document.querySelectorAll("#helpTabs button").forEach(b => b.onclick = () => openHelp(b.dataset.t));
if (!IS_MAC) document.querySelectorAll("kbd.mod").forEach(k => k.textContent = "Ctrl");

/* ---------- 快捷键 ---------- */
document.addEventListener("keydown", e => {
  if ($("app").classList.contains("hidden") || document.querySelector("dialog[open]:not(#dlgPreview)")) return;
  const typing = /INPUT|TEXTAREA|SELECT/.test(document.activeElement?.tagName);
  if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
    e.preventDefault();
    if (location.hash.slice(1) !== "write" && location.hash) location.hash = "write";
    if (e.shiftKey) $("dlgPreview").open ? $("btnPublishFromPreview").click() : publish(false);
    else if (!$("dlgPreview").open) $("btnPreview").click();
  } else if (e.key === "?" && !typing && !$("dlgPreview").open) { e.preventDefault(); openHelp(); }
});

/* ---------- 写作：草稿、导入、计数 ---------- */
let draftTimer = 0;
function writeDraft() {
  clearTimeout(draftTimer); draftTimer = 0;
  const d = Object.fromEntries(DRAFT_FIELDS.map(k => [k, $(k).value]));
  const empty = DRAFT_FIELDS.every(k => k === "date" || !d[k].trim());
  store.set(DRAFT_KEY, empty ? null : JSON.stringify(d));
  const t = new Date();
  $("saved").textContent = empty ? "Markdown" : `草稿已保存 ${String(t.getHours()).padStart(2, "0")}:${String(t.getMinutes()).padStart(2, "0")}`;
}
function saveDraft() { clearTimeout(draftTimer); draftTimer = setTimeout(writeDraft, 400); }
// 刷新 / 关标签页 / 切走时立刻写，避免丢掉最后 0.4 秒的输入
addEventListener("pagehide", () => { if (draftTimer) writeDraft(); });
document.addEventListener("visibilitychange", () => { if (document.hidden && draftTimer) writeDraft(); });
function restoreDraft() {
  let d = null;
  try { d = JSON.parse(store.get(DRAFT_KEY) || "null"); } catch {}
  if (d && !$("body").value) { DRAFT_FIELDS.forEach(k => { if (d[k] != null) $(k).value = d[k]; }); $("saved").textContent = "已恢复上次的草稿"; }
  if (!$("date").value) $("date").value = localNow();
  updateCount(); checkSlug(); descHint();
}
DRAFT_FIELDS.forEach(k => $(k).addEventListener("input", saveDraft));

function updateCount() {
  const n = $("body").value.replace(/\s/g, "").length;
  $("count").textContent = n.toLocaleString();
  $("readMin").textContent = Math.max(n ? 1 : 0, Math.round(n / 400));
}
$("body").addEventListener("input", updateCount);

/* 粘贴富文本（飞书、公众号后台、网页）→ Markdown；⌘⇧V 按纯文本粘贴 */
let plainPaste = false;
$("body").addEventListener("keydown", e => { if ((e.metaKey || e.ctrlKey) && e.shiftKey && e.key.toLowerCase() === "v") plainPaste = true; });
$("body").addEventListener("paste", e => {
  const plain = plainPaste; plainPaste = false;
  const cd = e.clipboardData;
  if (plain || !cd) return;
  const html = cd.getData("text/html"), text = cd.getData("text/plain");
  if (!window.looksRich(html, text)) return;
  let md;
  try { md = window.htmlToMarkdown(html); } catch { return; }
  if (!md.trim()) return;
  e.preventDefault();
  const ta = $("body");
  ta.focus();
  // execCommand 保留撤销记录（⌘Z 能撤回转换）；不支持时退回直接替换
  if (!document.execCommand("insertText", false, md)) {
    ta.setRangeText(md, ta.selectionStart, ta.selectionEnd, "end");
    ta.dispatchEvent(new Event("input", { bubbles: true }));
  }
  const imgs = [...md.matchAll(/!\[[^\]]*\]\(([^)]+)\)/g)].map(m => m[1]);
  const locked = imgs.filter(u => /feishu\.cn|larksuite\.com|feishucdn|mmbiz\.q(pic|logo)\.cn/.test(u)).length;
  const local = (md.match(/本地图片，请上传到图床/g) || []).length;
  toast(`已转成 Markdown · ⌘Z 撤销 · ⌘⇧V 粘贴纯文本${locked || local ? `；${locked + local} 张图片发布前要换成图床链接（飞书需登录 / 公众号防盗链）` : ""}`,
        locked || local ? "err" : "");
});

function checkSlug() {
  const v = $("slug").value.trim(), bad = v && !SLUG_RE.test(v);
  const soft = v && !bad && !SLUG_RECOMMENDED.test(v) && !editing;
  $("slugHint").textContent = bad ? "只能用字母、数字、中文，用 - 或 _ 连接（不能有空格和其他符号）"
    : editing ? "已发布文章的网址不能改（改了老链接会 404）"
    : soft ? "可以用，但推荐小写英文 + 连字符，网址更干净" : "点「AI 生成」按标题提炼英文主题词，如 python-314-free-threading-template-strings-upgrade";
  $("slugHint").classList.toggle("err", !!bad);
}
$("slug").addEventListener("input", checkSlug);

/* 按标题生成拼音网址：slug 为空或还是上次自动生成的就跟着标题变；手动改过不覆盖；编辑已发布文章时不动 */
let autoSlug = "", slugTimer = 0;
async function genSlug(force = false) {
  const title = $("title").value.trim();
  if (!title || editing) return;
  const cur = $("slug").value.trim();
  if (!force && cur && cur !== autoSlug) return;
  try {
    const { slug } = await api(`/api/slug?title=${encodeURIComponent(title)}`);
    if (!force && $("slug").value.trim() !== cur) return;  // 请求期间用户自己改了
    $("slug").value = autoSlug = slug; checkSlug(); saveDraft();
  } catch {}
}
// 网址由「AI 生成」按标题提炼英文主题词；右侧按钮是没有 AI 时的备用（按标题转拼音）
$("btnSlugGen").onclick = () => editing ? toast("已发布文章的网址不能改，改了老链接会 404", "err") : genSlug(true);

/* 描述长度提示：百度电脑端摘要约显示 78 个字 */
function descHint() {
  const n = [...$("description").value.trim()].length, el = $("descHint");
  el.textContent = n ? `${n} 字 · 建议 100–130 字（第一句讲事实，第二句写读者会搜的问题）${n > 150 ? "（偏长）" : n < 80 ? "（偏短）" : ""}` : "建议 100–130 字：第一句讲事实，第二句写读者会搜的问题";
  el.className = `hint ${n && (n > 150 || n < 80) ? "warn" : ""}`;
}
$("description").addEventListener("input", descHint);

function fillAll(v) {
  DRAFT_FIELDS.forEach(k => $(k).value = v[k] ?? "");
  autoSlug = "";
  updateCount(); checkSlug(); descHint(); saveDraft();
}

$("btnNew").onclick = async () => {
  if (DRAFT_FIELDS.some(k => k !== "date" && $(k).value.trim())) {
    const { ok } = await confirmDialog({ title: "开始新文章？", text: "当前正文和元数据会被清空，草稿也会删除。", ok: "清空", danger: true });
    if (!ok) return;
  }
  fillAll({ date: localNow() });
  setEditing(null);
  $("result").classList.add("hidden"); stopPolling();
  $("body").focus();
};

async function importFile(file) {
  if (!file) return;
  if (!/\.(md|markdown|txt)$/i.test(file.name) && !/^text\//.test(file.type)) return toast("只支持 .md / .markdown / .txt", "err");
  if ($("body").value.trim()) {
    const { ok } = await confirmDialog({ title: `导入「${file.name}」？`, text: "会替换当前正文。", ok: "替换" });
    if (!ok) return;
  }
  let text = await file.text();
  const fm = text.match(/^---\r?\n([\s\S]*?)\r?\n---\r?\n/);  // 自带 front matter 的：取 title，正文去掉 front matter
  if (fm) {
    const title = fm[1].match(/^title:\s*["']?(.+?)["']?\s*$/m);
    if (title && !$("title").value) $("title").value = title[1];
    text = text.slice(fm[0].length);
  }
  const base = file.name.replace(/\.[^.]+$/, "").toLowerCase();
  if (!$("slug").value && SLUG_RE.test(base)) $("slug").value = base;
  $("body").value = text.replace(/^\s+/, "");
  updateCount(); checkSlug(); saveDraft();
  toast(`已导入 ${file.name}`);
}
$("btnImport").onclick = () => $("fileInput").click();
$("fileInput").onchange = () => { importFile($("fileInput").files[0]); $("fileInput").value = ""; };
const editorCard = document.querySelector(".editor");
editorCard.addEventListener("dragover", e => { if ([...e.dataTransfer.types].includes("Files")) { e.preventDefault(); editorCard.classList.add("dragging"); } });
editorCard.addEventListener("dragleave", e => { if (!editorCard.contains(e.relatedTarget)) editorCard.classList.remove("dragging"); });
editorCard.addEventListener("drop", e => { e.preventDefault(); editorCard.classList.remove("dragging"); importFile(e.dataTransfer.files[0]); });

/* ---------- 写作：发布 ---------- */
function renderTargets() {
  const checked = new Set([...document.querySelectorAll("#targets input:checked")].map(i => i.value));
  const fresh = !document.querySelector("#targets input");
  $("targets").innerHTML = blogs.map(b => `
    <label class="target"><input type="checkbox" value="${esc(b.id)}" ${fresh || checked.has(b.id) ? "checked" : ""}>
      <span class="box"></span>
      <span class="t-main"><span class="t-name">${esc(b.name)}</span><span class="t-sub">${esc(b.repo)} · ${esc(b.branch)}</span></span>
      <span class="tag">${esc(b.adapter)}</span></label>`).join("");
  $("noBlogs").classList.toggle("hidden", blogs.length > 0);
  ["btnPreview", "btnPublish"].forEach(id => $(id).disabled = !blogs.length);
}

$("btnEnrich").onclick = () => {
  if (!$("body").value.trim()) { toast("先粘贴正文", "err"); $("body").focus(); return; }
  busy($("btnEnrich"), async () => {
    try {
      // 标题是你定的，AI 不改；只填网址（按标题生成拼音）、描述、关键词，标签和分类不动
      const m = await api("/api/enrich", { title: $("title").value.trim(), body: $("body").value });
      if (!$("title").value.trim()) $("title").value = m.title;  // 标题框空着时用了正文开头的「# 标题」
      if (!editing) $("slug").value = autoSlug = m.slug;  // 已发布文章不改网址
      $("description").value = m.description; $("keywords").value = m.keywords.join(", ");
      checkSlug(); descHint(); saveDraft();
      toast("已生成网址、描述、关键词；标题没改");
    } catch (e) { toast(e.message, "err"); }
  });
};

function payload() {
  return {
    post: { title: $("title").value.trim(), slug: $("slug").value.trim(), date: $("date").value,
            tags: list($("tags").value), categories: list($("categories").value), description: $("description").value.trim(),
            keywords: list($("keywords").value), cover: $("cover").value.trim(), body: $("body").value },
    blog_ids: [...document.querySelectorAll("#targets input:checked")].map(i => i.value),
    overwrite: $("overwrite").checked,
    paths: editing ? { [editing.blog_id]: editing.path } : {},
  };
}

function validate(p) {
  if (!p.post.date) p.post.date = null;  // 老文章可以没有日期；新文章由后端要求必填
  const miss = [!p.post.body.trim() && "正文", !p.post.title && "标题", !p.post.slug && "Slug",
                !p.post.date && !editing && "发布时间"].filter(Boolean);
  if (miss.length) { toast(`还没填：${miss.join("、")}`, "err"); return false; }
  if (!SLUG_RE.test(p.post.slug)) { toast("Slug 格式不对", "err"); $("slug").focus(); return false; }
  if (!p.blog_ids.length) { toast("至少选一个博客", "err"); return false; }
  return true;
}

function renderPreview(i) {
  document.querySelectorAll("#previewTabs button").forEach((b, j) => b.classList.toggle("on", i === j));
  const p = previews[i];
  const state = p.exists ? `<span class="badge warn"><span class="dot"></span>已存在${$("overwrite").checked ? "，将覆盖" : "，需打开覆盖"}</span>`
    : p.check_error ? `<span class="badge err" title="${esc(p.check_error)}">无法检查是否已存在</span>` : `<span class="badge ok">新文件</span>`;
  $("previewMeta").innerHTML = `${state}${p.editing ? '<span class="badge run">编辑原文件 · 只改动过的部分</span>' : ""}<code>${esc(p.path)}</code>`;
  $("previewBody").textContent = p.content;
}

$("btnPreview").onclick = () => {
  const p = payload();
  if (!validate(p)) return;
  busy($("btnPreview"), async () => {
    try {
      previews = await api("/api/preview", p);
      $("previewSub").textContent = `${previews.length} 个博客 · 未提交，只是看看`;
      $("previewTabs").innerHTML = previews.map((x, i) => `<button data-i="${i}">${esc(x.name)}${x.exists ? '<span class="dot" style="color:var(--warn)"></span>' : ""}</button>`).join("");
      $("previewTabs").querySelectorAll("button").forEach(b => b.onclick = () => renderPreview(+b.dataset.i));
      renderPreview(0);
      $("dlgPreview").showModal();
    } catch (e) { toast(e.message, "err"); }
  });
};

async function publish(skipConfirm) {
  const p = payload();
  if (!validate(p)) return;
  if (!skipConfirm) {
    const names = blogs.filter(b => p.blog_ids.includes(b.id)).map(b => b.name).join("、");
    const { ok } = await confirmDialog({ title: "发布这篇文章？", text: `「${p.post.title}」将提交到 ${names}，提交后各仓库会自动构建部署。`, ok: "发布" });
    if (!ok) return;
  }
  await busy($("btnPublish"), async () => {
    try {
      const rec = await api("/api/publish", p);
      currentId = rec.id;
      const okN = rec.results.filter(r => r.ok).length;
      toast(okN === rec.results.length ? "已提交，等待构建" : `${rec.results.length - okN} 个失败，见发布结果`, okN === rec.results.length ? "" : "err");
      await refresh(true);
    } catch (e) { toast(e.message, "err"); }
  });
}
$("btnPublish").onclick = () => publish(false);
$("btnPublishFromPreview").onclick = () => { $("dlgPreview").close(); publish(true); };

/* ---------- 发布结果（自动轮询 Actions 状态） ---------- */
function runBadge(r) {
  if (r.conclusion === "success") return `<span class="badge ok"><span class="dot"></span>已部署</span>`;
  if (r.conclusion) return `<span class="badge err"><span class="dot"></span>${esc(r.conclusion)}</span>`;
  return `<span class="badge run"><span class="dot"></span>${r.status === "queued" ? "排队中" : "构建中"}</span>`;
}
const blogName = id => blogs.find(b => b.id === id)?.name || id;

function resultRows(rec) {
  return rec.results.map(r => `
    <div class="row"><div class="r-main">
      <div class="r-title">${esc(blogName(r.blog_id))}
        ${r.ok ? '<span class="badge ok">已提交</span>' : '<span class="badge err">失败</span>'}
        ${r.ok ? (r.runs?.length ? r.runs.map(runBadge).join("") : '<span class="badge">Actions 未开始</span>') : ""}</div>
      <div class="r-sub mono">${esc(r.path)}</div>
      ${r.ok ? `<div class="r-links"><a href="${esc(r.commit_url)}" target="_blank" rel="noopener">${icon("external")}提交 ${esc(r.commit_sha.slice(0, 7))}</a>
        ${r.runs?.map(x => `<a href="${esc(x.url)}" target="_blank" rel="noopener">${icon("external")}${esc(x.name)}</a>`).join("") || ""}
        ${r.post_url ? `<a href="${esc(r.post_url)}" target="_blank" rel="noopener">${icon("external")}文章</a>` : ""}</div>` : ""}
      ${r.error ? `<div class="r-err">${esc(r.error)}</div>` : ""}
      ${r.runs_error ? `<div class="r-err">${esc(r.runs_error)}</div>` : ""}
    </div></div>`).join("");
}

let pollTimer = 0, pollLeft = 0;
const pending = rec => rec.results.some(r => r.ok && !r.runs_error && (!r.runs?.length || r.runs.some(x => !x.conclusion)));
function stopPolling() { clearTimeout(pollTimer); pollTimer = 0; $("liveBadge").classList.add("hidden"); }

async function refresh(scroll = false) {
  if (!currentId) return;
  const rec = await api(`/api/status/${currentId}`);
  $("resultSub").textContent = `#${rec.id} · ${rec.post.title}`;
  $("resultBody").innerHTML = resultRows(rec);
  $("result").classList.remove("hidden");
  if (scroll) {
    if (location.hash.slice(1) !== "write") location.hash = "write";
    $("result").scrollIntoView({ behavior: "smooth", block: "start" });
    pollLeft = 40;  // 约 5 分钟
  }
  stopPolling();
  if (pending(rec) && pollLeft-- > 0) {
    $("liveBadge").classList.remove("hidden");
    const id = currentId;
    pollTimer = setTimeout(() => { if (id === currentId) refresh().catch(stopPolling); }, 8000);
  }
}
$("btnRefresh").onclick = () => busy($("btnRefresh"), () => { pollLeft = Math.max(pollLeft, 10); return refresh().catch(e => toast(e.message, "err")); });
$("btnCloseResult").onclick = () => { $("result").classList.add("hidden"); stopPolling(); };

/* ---------- 历史 ---------- */
async function loadHistory() {
  try { records = await api("/api/history"); } catch (e) { return toast(e.message, "err"); }
  renderHistory();
}

function renderHistory() {
  const q = $("histSearch").value.trim().toLowerCase();
  const items = records.filter(h => !q || h.post.title.toLowerCase().includes(q) || h.post.slug.includes(q));
  $("historyBody").innerHTML = items.length ? items.map(h => {
    const failed = h.results.filter(r => !r.ok).map(r => r.blog_id);
    const done = new Set(h.results.map(r => r.blog_id));
    const missing = blogs.map(b => b.id).filter(id => !done.has(id));
    return `<div class="row"><div class="r-main">
        <div class="r-title">${esc(h.post.title)}</div>
        <div class="r-sub">#${h.id} · ${esc(h.created_at.replace("T", " ").slice(0, 16))} · <span class="mono">${esc(h.post.slug)}</span></div>
        <div class="pills">${h.results.map(r => `<span class="badge ${r.ok ? "ok" : "err"}">${esc(blogName(r.blog_id))} ${r.ok ? "✓" : "✗"}</span>`).join("")}</div>
      </div><div class="r-actions">
        ${failed.length ? `<button class="btn secondary sm" data-act="retry" data-id="${h.id}" data-blogs="${esc(failed.join(","))}">重发失败的</button>` : ""}
        ${missing.length ? `<button class="btn secondary sm" data-act="retry" data-id="${h.id}" data-blogs="${esc(missing.join(","))}">补发 ${missing.length} 个</button>` : ""}
        <button class="btn ghost sm" data-act="load" data-id="${h.id}">载入编辑</button>
        <button class="btn ghost sm" data-act="status" data-id="${h.id}">查看状态</button>
      </div></div>`;
  }).join("") : `<div class="empty-row">${q ? "没有匹配的记录" : "还没有发布记录"}</div>`;
  $("historyBody").querySelectorAll("button").forEach(b => b.onclick = () => historyAction(b));
}
$("histSearch").addEventListener("input", renderHistory);

async function historyAction(b) {
  const h = records.find(x => x.id === +b.dataset.id);
  if (b.dataset.act === "load") {
    if (DRAFT_FIELDS.some(k => k !== "date" && $(k).value.trim())) {
      const { ok } = await confirmDialog({ title: `载入「${h.post.title}」？`, text: "会替换编辑器里当前的内容。", ok: "载入" });
      if (!ok) return;
    }
    const p = h.post, j = a => (a || []).join(", ");
    fillAll({ ...p, date: p.date ? String(p.date).slice(0, 16) : "", tags: j(p.tags), categories: j(p.categories), keywords: j(p.keywords) });
    const [bid, path] = Object.entries(p._paths || {})[0] || [];
    setEditing(bid ? { blog_id: bid, path } : null);
    location.hash = "write"; toast(bid ? "已载入，发布会写回原文件" : "已载入，修改后可重新发布（同 slug 需打开覆盖）");
    return;
  }
  currentId = h.id;
  if (b.dataset.act === "retry") {
    const ids = b.dataset.blogs.split(",");
    const { ok, overwrite } = await confirmDialog({ title: `发布到 ${ids.map(blogName).join("、")}？`, text: "用当时保存的文章内容重新生成并提交。", ok: "发布", overwrite: false });
    if (!ok) return;
    try { await busy(b, () => api(`/api/publish/${currentId}/retry`, { blog_ids: ids, overwrite })); }
    catch (e) { return toast(e.message, "err"); }
  }
  refresh(true).catch(e => toast(e.message, "err"));
}

/* ---------- 文章：仓库里已发布的文章 ---------- */
function setEditing(e) {
  editing = e && blogs.some(b => b.id === e.blog_id) ? e : null;
  store.set("pf-editing", editing ? JSON.stringify(editing) : null);
  $("editingBar").classList.toggle("hidden", !editing);
  if (!editing) return;
  $("editingName").textContent = blogName(editing.blog_id);
  $("editingPath").textContent = editing.path;
  document.querySelectorAll("#targets input").forEach(i => i.checked = i.value === editing.blog_id);
  $("overwrite").checked = true;
}
$("btnStopEditing").onclick = () => { setEditing(null); toast("已取消关联，之后发布当作新文章"); };

async function loadArticles(force = false) {
  if (!blogs.length) { $("artBody").innerHTML = '<div class="empty-row">还没有博客，先去「设置」添加</div>'; return; }
  const sel = $("artBlog");
  if (!sel.options.length || force) {
    const cur = sel.value || store.get("pf-art-blog");
    sel.innerHTML = blogs.map(b => `<option value="${esc(b.id)}">${esc(b.name)}</option>`).join("");
    if (blogs.some(b => b.id === cur)) sel.value = cur;
  }
  $("artBody").innerHTML = '<div class="empty-row">正在读取仓库…</div>'; $("artCount").textContent = "";
  try { articles = await api(`/api/blogs/${encodeURIComponent(sel.value)}/articles`); }
  catch (e) { $("artBody").innerHTML = `<div class="empty-row">${esc(e.message)}</div>`; return; }
  renderArticles();
}

function renderArticles() {
  const q = $("artSearch").value.trim().toLowerCase();
  const items = articles.filter(a => !q || a.path.toLowerCase().includes(q));
  $("artCount").textContent = `${items.length} / ${articles.length} 篇`;
  $("artBody").innerHTML = items.length ? items.map(a => `
    <div class="row" data-path="${esc(a.path)}"><div class="r-main">
      <div class="r-title">${esc(a.slug)}${a.dir ? ` <span class="tag">${esc(a.dir)}</span>` : ""}</div>
      <div class="r-sub mono">${esc(a.path)}</div>
    </div><div class="r-actions">
      ${a.url ? `<a class="btn ghost sm" href="${esc(a.url)}" target="_blank" rel="noopener">${icon("external")}查看</a>` : ""}
      <button class="btn secondary sm" data-act="edit">编辑</button>
      <button class="btn danger-ghost sm" data-act="delete">删除</button>
    </div></div>`).join("") : `<div class="empty-row">${q ? "没有匹配的文章" : "这个博客的文章目录里还没有文章"}</div>`;
  $("artBody").querySelectorAll("button").forEach(b => b.onclick = () => articleAction(b, b.closest(".row").dataset.path));
}
$("artBlog").onchange = () => { store.set("pf-art-blog", $("artBlog").value); loadArticles(); };
$("artSearch").addEventListener("input", renderArticles);
$("btnArtRefresh").onclick = () => busy($("btnArtRefresh"), () => loadArticles());

async function articleAction(btn, path) {
  const blogId = $("artBlog").value;
  if (btn.dataset.act === "edit") {
    if (DRAFT_FIELDS.some(k => k !== "date" && $(k).value.trim())) {
      const { ok } = await confirmDialog({ title: "载入这篇文章？", text: "会替换写作页里当前的内容（当前草稿不会保留）。", ok: "载入" });
      if (!ok) return;
    }
    await busy(btn, async () => {
      try {
        const { post } = await api(`/api/blogs/${encodeURIComponent(blogId)}/articles/file?path=${encodeURIComponent(path)}`);
        const j = a => (a || []).join(", ");
        fillAll({ ...post, date: post.date ? String(post.date).slice(0, 16) : "", tags: j(post.tags), categories: j(post.categories), keywords: j(post.keywords) });
        setEditing({ blog_id: blogId, path });
        location.hash = "write";
        toast("已载入，改完点发布会写回原文件");
      } catch (e) { toast(e.message, "err"); }
    });
    return;
  }
  const { ok } = await confirmDialog({
    title: "删除这篇文章？", danger: true, ok: "删除",
    text: `将从「${blogName(blogId)}」仓库删除 ${path}，并登记到放行名单；约 2 分钟后线上页面消失。已被搜索引擎收录的链接会变成 404，能改就尽量别删。`,
  });
  if (!ok) return;
  await busy(btn, async () => {
    try {
      await api(`/api/blogs/${encodeURIComponent(blogId)}/articles/delete`, { path });
      if (editing && editing.blog_id === blogId && editing.path === path) setEditing(null);
      toast("已删除，约 2 分钟后从线上消失");
      await loadArticles();
    } catch (e) { toast(e.message, "err"); }
  });
}

/* ---------- 设置 ---------- */
const adapterLabel = name => adapters.find(a => a.name === name)?.label || name;

async function loadConfig() {
  let cfg;
  try { cfg = await api("/api/config"); } catch (e) { return toast(e.message, "err"); }
  adapters = cfg.adapters;
  for (const key of ["github_token", "anthropic_api_key"]) {
    const s = cfg.secrets[key], el = $(`st_${key}`);
    el.className = `badge ${s.set ? "ok" : "warn"}`;
    el.textContent = s.set ? `已设置 ${s.hint}${s.source === "env" ? " · 环境变量" : ""}` : "未设置";
    document.querySelector(`[data-clear="${key}"]`).classList.toggle("hidden", s.source !== "page");
  }
  $("model").value = cfg.secrets.anthropic_model;
  $("aiProvider").innerHTML = Object.entries(cfg.ai_providers).map(([k, v]) => `<option value="${esc(k)}">${esc(v)}</option>`).join("");
  $("aiProvider").value = cfg.secrets.ai_provider; $("aiBaseUrl").value = cfg.secrets.ai_base_url || "";
  aiFormHints(); $("aiTestMsg").textContent = "";
  const ak = cfg.secrets.anthropic_api_key;
  $("aiState").className = `badge ${ak.set ? "ok" : "warn"}`;
  $("aiState").textContent = ak.set ? (cfg.secrets.ai_base_url ? "中转站" : (cfg.secrets.ai_provider === "anthropic" ? "官方" : "已配置")) : "未配置";
  $("blogList").innerHTML = cfg.blogs.length ? cfg.blogs.map(b => `
    <div class="row" data-id="${esc(b.id)}"><div class="r-main">
      <div class="r-title">${esc(b.name)} <span class="tag">${esc(b.id)}</span>${b.token_set ? `<span class="badge" title="这个博客用自己的 GitHub Token">专用 Token ${esc(b.token_hint)}</span>` : ""}<span class="badge" data-check></span></div>
      <div class="r-sub">${esc(adapterLabel(b.adapter))}</div>
      <div class="r-sub mono">${esc(b.repo)}@${esc(b.branch)} → ${esc(b.posts_dir)}/${esc(b.filename)}</div>
    </div><div class="r-actions">
      <button class="btn ghost sm" data-act="check">检查连接</button>
      <button class="btn ghost sm" data-act="edit">编辑</button>
      <button class="btn danger-ghost sm" data-act="delete">删除</button>
    </div></div>`).join("") : '<div class="empty-row">还没有博客，点右上角「添加博客」</div>';
  $("blogList").querySelectorAll("button").forEach(btn => btn.onclick = () => blogAction(btn, cfg.blogs.find(b => b.id === btn.closest(".row").dataset.id)));
}

async function blogAction(btn, blog) {
  if (btn.dataset.act === "edit") return openBlogForm(blog);
  if (btn.dataset.act === "delete") {
    const { ok } = await confirmDialog({ title: `删除「${blog.name}」？`, text: "只删除这里的配置，不会动 GitHub 仓库；历史记录保留。", ok: "删除", danger: true });
    if (!ok) return;
    try { await api(`/api/config/blogs/${encodeURIComponent(blog.id)}/delete`, {}); toast("已删除"); await afterBlogsChanged(); }
    catch (e) { toast(e.message, "err"); }
    return;
  }
  const badge = btn.closest(".row").querySelector("[data-check]");
  await busy(btn, async () => {
    try {
      const r = await api(`/api/config/blogs/${encodeURIComponent(blog.id)}/check`, {});
      badge.className = `badge ${r.ok ? "ok" : "err"}`;
      badge.textContent = r.ok ? "连接正常" : "有问题";
      if (!r.ok) toast(r.problems.join("；"), "err");
    } catch (e) { toast(e.message, "err"); }
  });
}

async function afterBlogsChanged() {
  blogs = (await api("/api/me")).blogs;
  renderTargets();
  await loadConfig();
}

function openBlogForm(blog) {
  editingBlog = blog || null;
  $("blogFormTitle").textContent = blog ? `编辑「${blog.name}」` : "添加博客";
  $("f_adapter").innerHTML = adapters.map(a => `<option value="${esc(a.name)}">${esc(a.label)}</option>`).join("");
  const b = blog || { id: "", name: "", repo: "", branch: "main", adapter: "classic-hexo", post_url: "",
                      category_dirs_yaml: "", default_category_dir: "", options_yaml: "" };
  const preset = adapters.find(a => a.name === b.adapter) || adapters[0];
  for (const k of ["id", "name", "repo", "branch", "post_url", "default_category_dir"]) $(`f_${k}`).value = b[k] || "";
  $("f_adapter").value = b.adapter;
  $("f_posts_dir").value = b.posts_dir || preset?.posts_dir || "";
  $("f_filename").value = b.filename || preset?.filename || "{slug}.md";
  $("f_category_dirs").value = b.category_dirs_yaml || "";
  $("f_options").value = b.options_yaml || "";
  $("f_id").disabled = !!blog;
  $("f_token").value = ""; clearBlogToken = false;
  setTokenState(!!b.token_set, b.token_hint);
  $("blogMsg").textContent = "";
  $("dlgBlog").querySelector(".adv").open = !!(b.post_url || b.category_dirs_yaml || b.options_yaml);
  $("f_adapter").dataset.prev = b.adapter;
  $("dlgBlog").showModal();
  (blog ? $("f_name") : $("f_adapter")).focus();
}

$("f_adapter").onchange = () => {
  // 只替换还是上一个预设默认值的目录/文件名，手改过的不动
  const prev = adapters.find(a => a.name === $("f_adapter").dataset.prev), next = adapters.find(a => a.name === $("f_adapter").value);
  for (const k of ["posts_dir", "filename"]) if (!$(`f_${k}`).value || $(`f_${k}`).value === prev?.[k]) $(`f_${k}`).value = next[k];
  $("f_adapter").dataset.prev = next.name;
};

let clearBlogToken = false;
function setTokenState(set, hint = "") {
  $("f_token_state").className = `badge ${set ? "ok" : ""}`;
  $("f_token_state").textContent = set ? `已设置 ${hint}` : "";
  $("btnClearBlogToken").classList.toggle("hidden", !set);
}
$("btnClearBlogToken").onclick = () => { clearBlogToken = true; $("f_token").value = ""; setTokenState(false); toast("保存后改用全局 Token"); };

$("btnNewBlog").onclick = () => openBlogForm(null);

$("blogForm").onsubmit = e => {
  e.preventDefault();
  const data = {};
  for (const k of ["id", "name", "repo", "branch", "posts_dir", "filename", "adapter", "post_url", "default_category_dir"]) data[k] = $(`f_${k}`).value.trim();
  data.category_dirs_yaml = $("f_category_dirs").value; data.options_yaml = $("f_options").value;
  if ($("f_token").value.trim()) data.token = $("f_token").value.trim();
  else if (clearBlogToken) data.token = "";
  busy($("btnSaveBlog"), async () => {
    try {
      await api(editingBlog ? `/api/config/blogs/${encodeURIComponent(editingBlog.id)}` : "/api/config/blogs", data);
      $("dlgBlog").close(); toast("已保存"); await afterBlogsChanged();
    } catch (err) { $("blogMsg").textContent = err.message; }
  });
};

$("btnSaveGithub").onclick = () => {
  if (!$("ghToken").value.trim()) return toast("先填 Token", "err");
  busy($("btnSaveGithub"), async () => {
    try { await api("/api/config/secrets", { github_token: $("ghToken").value.trim() }); $("ghToken").value = ""; toast("已保存"); await loadConfig(); }
    catch (e) { toast(e.message, "err"); }
  });
};

/* AI 接口：两种格式的地址、模型提示不同 */
const AI_HINTS = {
  anthropic: { base: "留空 = 官方 api.anthropic.com；中转站填它给的地址", placeholder: "https://api.anthropic.com",
               models: ["claude-opus-5-5", "claude-sonnet-5-5", "claude-haiku-5-5"] },
  openai: { base: "必填，一般到 /v1，如 https://api.deepseek.com/v1", placeholder: "https://api.deepseek.com/v1",
            models: ["deepseek-chat", "kimi-k2", "qwen-plus", "gpt-5"] },
};
function aiFormHints() {
  const h = AI_HINTS[$("aiProvider").value] || AI_HINTS.anthropic;
  $("aiBaseHint").textContent = h.base; $("aiBaseUrl").placeholder = h.placeholder;
  $("modelList").innerHTML = h.models.map(m => `<option value="${m}">`).join("");
}
$("aiProvider").onchange = () => { aiFormHints(); $("aiTestMsg").textContent = ""; };

function aiForm() {
  const body = { ai_provider: $("aiProvider").value, ai_base_url: $("aiBaseUrl").value.trim(), anthropic_model: $("model").value.trim() };
  if ($("akKey").value.trim()) body.anthropic_api_key = $("akKey").value.trim();
  return body;
}

$("btnTestAI").onclick = () => busy($("btnTestAI"), async () => {
  const f = aiForm(), msg = $("aiTestMsg");
  msg.className = "hint"; msg.textContent = "正在测试…";
  try {
    const r = await api("/api/config/ai/test", { provider: f.ai_provider, base_url: f.ai_base_url, model: f.anthropic_model, api_key: f.anthropic_api_key || null });
    msg.className = `hint ${r.ok ? "ok-text" : "err"}`;
    msg.textContent = r.ok ? `✓ 连接正常：${r.model} 回复「${r.reply}」，用时 ${(r.ms / 1000).toFixed(1)} 秒` : `✗ ${r.error}`;
  } catch (e) { msg.className = "hint err"; msg.textContent = `✗ ${e.message}`; }
});

$("btnSaveAI").onclick = () => {
  const f = aiForm();
  if (!f.anthropic_model) return toast("先填模型名", "err");
  busy($("btnSaveAI"), async () => {
    try { await api("/api/config/secrets", f); $("akKey").value = ""; toast("已保存"); await loadConfig(); }
    catch (e) { toast(e.message, "err"); }
  });
};

document.querySelectorAll("[data-clear]").forEach(b => b.onclick = async () => {
  const label = b.dataset.clear === "github_token" ? "GitHub Token" : "AI API Key";
  const { ok } = await confirmDialog({ title: `清除 ${label}？`, text: "清除页面里保存的值；若环境变量里也有，会改用环境变量的。", ok: "清除", danger: true });
  if (!ok) return;
  try { await api("/api/config/secrets", { [b.dataset.clear]: "" }); toast("已清除"); await loadConfig(); }
  catch (e) { toast(e.message, "err"); }
});

$("btnChangePw").onclick = () => {
  if ($("pwNew").value.length < 8) return toast("新密码至少 8 位", "err");
  busy($("btnChangePw"), async () => {
    try { const r = await api("/api/password", { current: $("pwCur").value, new: $("pwNew").value }); csrf = r.csrf || csrf; $("pwCur").value = $("pwNew").value = ""; toast("密码已修改，其他设备需要重新登录"); }
    catch (e) { toast(e.message, "err"); }
  });
};

boot();
