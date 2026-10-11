// 页面渲染前先套用上次选的主题，避免闪一下（单独文件：CSP 不允许内联脚本）
try { const t = localStorage.getItem("pf-theme"); if (t === "light" || t === "dark") document.documentElement.dataset.theme = t; } catch {}
