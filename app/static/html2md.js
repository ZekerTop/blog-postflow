// 富文本（飞书文档、公众号后台、网页、Word/Google Docs）粘贴 → Markdown。不依赖外部库。
// window.htmlToMarkdown(html) → string；window.looksRich(html, plain) → 是否值得转换
(() => {
  const BLOCK = new Set(["P", "DIV", "SECTION", "ARTICLE", "MAIN", "HEADER", "FOOTER", "ASIDE", "NAV", "FIGURE", "FIGCAPTION",
    "H1", "H2", "H3", "H4", "H5", "H6", "UL", "OL", "LI", "PRE", "BLOCKQUOTE", "TABLE", "HR", "DL", "DT", "DD", "BODY"]);
  const SKIP = new Set(["SCRIPT", "STYLE", "META", "LINK", "HEAD", "NOSCRIPT", "TEMPLATE", "TITLE", "SVG", "BUTTON", "INPUT"]);
  const CJK = /[　-〿㐀-鿿＀-￯]/;

  const isBlock = el => el.nodeType === 1 && BLOCK.has(el.tagName);
  const hasBlockChild = el => [...el.children].some(c => isBlock(c) || hasBlockChild(c));
  const style = el => (el.getAttribute && el.getAttribute("style") || "").toLowerCase().replace(/\s+/g, "");

  // 文本节点里的换行是 HTML 排版用的：中文之间直接去掉，其他变空格
  function cleanText(s) {
    s = s.replace(/ /g, " ");
    s = s.replace(/([^\s])[\t\r\n]+([^\s])/g, (m, a, b) => (CJK.test(a) && CJK.test(b) ? a + b : a + " " + b));
    return s.replace(/[\t\r\n]+/g, " ").replace(/ {2,}/g, " ");
  }

  function wrap(text, mark) {
    // **  加粗  ** → 空白挪到标记外面，否则 Markdown 不认
    const m = text.match(/^(\s*)([\s\S]*?)(\s*)$/);
    return m[2] ? `${m[1]}${mark}${m[2]}${mark}${m[3]}` : text;
  }

  function inline(node) {
    if (node.nodeType === 3) return cleanText(node.nodeValue);
    if (node.nodeType !== 1 || SKIP.has(node.tagName)) return "";
    const t = node.tagName, st = style(node);
    if (t === "BR") return "\n";
    if (t === "IMG") return image(node);
    if (t === "CODE" || t === "KBD" || t === "SAMP") {
      const code = node.textContent.replace(/\n/g, " ");
      const ticks = code.includes("`") ? "``" : "`";
      return code.trim() ? `${ticks}${code}${ticks}` : "";
    }
    let inner = [...node.childNodes].map(inline).join("");
    if (t === "A") {
      const href = (node.getAttribute("href") || "").trim();
      const text = inner.trim();
      if (!href || href.startsWith("javascript:") || href.startsWith("#")) return inner;
      if (!text) return "";
      return text === href ? `<${href}>` : `[${text}](${href})`;
    }
    const bold = t === "STRONG" || t === "B" || /font-weight:(bold|[6-9]00)/.test(st);
    const italic = t === "EM" || t === "I" || /font-style:italic/.test(st);
    const strike = t === "DEL" || t === "S" || t === "STRIKE" || /text-decoration[^;]*line-through/.test(st);
    if (strike) inner = wrap(inner, "~~");
    if (italic) inner = wrap(inner, "*");
    if (bold) inner = wrap(inner, "**");
    return inner;
  }

  function image(img) {
    const src = (img.getAttribute("data-src") || img.getAttribute("data-original") || img.getAttribute("src") || "").trim();
    if (!src) return "";
    if (src.startsWith("data:")) return "<!-- 这里有一张粘贴进来的本地图片，请上传到图床后替换成链接 -->";
    const alt = (img.getAttribute("alt") || "").replace(/[\[\]]/g, "");
    return `![${alt}](${src})`;
  }

  function codeBlock(pre) {
    const code = pre.querySelector("code") || pre;
    const cls = (code.className || "") + " " + (pre.className || "");
    const lang = (cls.match(/(?:language|lang)-([\w+#-]+)/i) || [])[1] || pre.getAttribute("data-lang") || code.getAttribute("data-lang") || "";
    // 有的编辑器把每行包成 div / p，有的用 <br>
    const lines = [];
    const walk = n => {
      if (n.nodeType === 3) { lines.push(lines.pop() + n.nodeValue); return; }
      if (n.nodeType !== 1) return;
      if (n.tagName === "BR") { lines.push(""); return; }
      const blockLine = n !== code && (n.tagName === "DIV" || n.tagName === "P" || n.tagName === "LI");
      if (blockLine && lines[lines.length - 1] !== "") lines.push("");
      n.childNodes.forEach(walk);
      if (blockLine) lines.push("");
    };
    lines.push("");
    walk(code);
    const text = lines.join("\n").replace(/ /g, " ").replace(/^\n+|\n+$/g, "");
    const fence = text.includes("```") ? "````" : "```";
    return `${fence}${lang.toLowerCase()}\n${text}\n${fence}`;
  }

  function table(tbl) {
    const rows = [...tbl.querySelectorAll("tr")].map(tr => [...tr.children].filter(c => /^T[DH]$/.test(c.tagName))
      .map(c => blocks(c).join("<br>").replace(/\n+/g, "<br>").replace(/\|/g, "\\|").trim()));
    if (!rows.length) return "";
    const n = Math.max(...rows.map(r => r.length));
    const pad = r => [...r, ...Array(n - r.length).fill("")];
    const line = r => `| ${pad(r).join(" | ")} |`;
    return [line(rows[0]), `|${" --- |".repeat(n)}`, ...rows.slice(1).map(line)].join("\n");
  }

  // indent：这一层列表前面的空格；子列表缩进到父级编号后面的内容起点（「1. 」是 3 格，「- 」是 2 格）
  function list(el, indent) {
    const ordered = el.tagName === "OL";
    let i = parseInt(el.getAttribute("start") || "1", 10) || 1;
    const out = [];
    for (const li of el.children) {
      if (li.tagName !== "LI") { if (li.tagName === "UL" || li.tagName === "OL") out.push(list(li, indent + "  ")); continue; }
      const box = li.querySelector(":scope > input[type=checkbox], :scope > * > input[type=checkbox]");
      const checked = box ? (box.checked || box.hasAttribute("checked")) : null;
      const cls = (li.className || "") + " " + (li.getAttribute("data-list") || "");
      const task = checked !== null ? (checked ? "[x] " : "[ ] ") : /\b(checked|done)\b/.test(cls) ? "[x] " : /\btask|todo|check/.test(cls) ? "[ ] " : "";
      const marker = ordered ? `${i++}. ` : "- ";
      const inner = indent + " ".repeat(marker.length);
      const parts = blocks(li, inner);
      const first = (parts.shift() || "").replace(/\n/g, "\n" + inner);
      out.push(indent + marker + task + first);
      for (const p of parts) out.push(p.startsWith(inner) ? p : p.split("\n").map(l => (l ? inner + l : l)).join("\n"));
    }
    return out.join("\n");
  }

  // 把一个容器拆成 Markdown 块（段落、标题、列表……），连续的行内内容合成一个段落
  function blocks(el, indent = "") {
    const out = [];
    let buf = "";
    const flush = () => {
      const text = buf.replace(/[ \t]+\n/g, "\n").replace(/\n[ \t]+/g, "\n").trim();
      if (text) out.push(text.replace(/\n/g, "  \n"));
      buf = "";
    };
    for (const n of el.childNodes) {
      if (n.nodeType === 1 && SKIP.has(n.tagName)) continue;
      if (!(n.nodeType === 1 && (isBlock(n) || hasBlockChild(n)))) { buf += inline(n); continue; }
      flush();
      const t = n.tagName;
      if (/^H[1-6]$/.test(t)) {
        const text = inline(n).replace(/\s+/g, " ").trim().replace(/^\*\*(.*)\*\*$/, "$1");
        if (text) out.push(`${"#".repeat(+t[1])} ${text}`);
      } else if (t === "UL" || t === "OL") out.push(list(n, indent));
      else if (t === "PRE") out.push(codeBlock(n));
      else if (t === "TABLE") out.push(table(n));
      else if (t === "HR") out.push("---");
      else if (t === "BLOCKQUOTE") {
        const inner = blocks(n, indent).join("\n\n");
        if (inner) out.push(inner.split("\n").map(l => (l ? `> ${l}` : ">")).join("\n"));
      } else out.push(...blocks(n, indent));
    }
    flush();
    return out.filter(Boolean);
  }

  window.htmlToMarkdown = html => {
    const doc = new DOMParser().parseFromString(html, "text/html");
    const md = blocks(doc.body).join("\n\n");
    return md.replace(/\n{3,}/g, "\n\n").replace(/[ \t]+$/gm, (m, o, s) => (m === "  " ? m : "")).trim() + "\n";
  };

  // 有结构的富文本才转；本来就是 Markdown（编辑器 / 代码里复制的）就原样粘贴
  window.looksRich = (html, plain) => {
    if (!html) return false;
    const structural = /<(h[1-6]|strong|b|em|li|img|table|pre|blockquote|a\s[^>]*href)[\s>]|font-weight\s*:\s*(bold|[6-9]00)/i.test(html);
    if (!structural) return false;
    const plainIsMarkdown = /^(#{1,6} |```|[-*+] |\d+\. |> |!\[)/m.test(plain || "");
    const fromCodeEditor = /white-space:\s*pre/i.test(html) && !/<(h[1-6]|li|img|table)[\s>]/i.test(html);
    return !(plainIsMarkdown && fromCodeEditor);
  };
})();
