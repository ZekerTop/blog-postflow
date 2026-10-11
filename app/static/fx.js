// 登录页背景：漂移的节点互相连线，光点沿连线流动（文章流向各个博客）；跟随鼠标；登录成功时向外爆开。
// 只在登录页可见时运行；系统开了「减少动态效果」就不启动。
window.fx = (() => {
  const canvas = document.getElementById("fx");
  const ctx = canvas.getContext("2d");
  const COLORS = ["139,125,255", "45,212,240", "224,73,155"];
  const LINK = 150;
  let w = 0, h = 0, dpr = 1, nodes = [], packets = [], sparks = [], raf = 0, last = 0, spawnAt = 0;
  const mouse = { x: -1e4, y: -1e4 };
  const still = matchMedia("(prefers-reduced-motion: reduce)").matches;

  function resize() {
    dpr = Math.min(devicePixelRatio || 1, 2);
    w = canvas.clientWidth; h = canvas.clientHeight;
    canvas.width = w * dpr; canvas.height = h * dpr;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    const n = Math.min(110, Math.round((w * h) / 14000));
    nodes = Array.from({ length: n }, () => ({
      x: Math.random() * w, y: Math.random() * h,
      vx: (Math.random() - .5) * .25, vy: (Math.random() - .5) * .25,
      r: Math.random() * 1.6 + .6, c: COLORS[Math.random() * 3 | 0], tw: Math.random() * Math.PI * 2,
    }));
    packets = [];
  }

  function neighbors(a) {
    return nodes.filter(b => b !== a && Math.hypot(a.x - b.x, a.y - b.y) < LINK);
  }

  function spawnPacket() {
    const a = nodes[Math.random() * nodes.length | 0];
    const near = a && neighbors(a);
    if (near?.length) packets.push({ a, b: near[Math.random() * near.length | 0], t: 0, hops: 3 + (Math.random() * 4 | 0), c: a.c });
  }

  function step(now) {
    raf = requestAnimationFrame(step);
    const dt = Math.min(48, now - (last || now)); last = now;
    ctx.clearRect(0, 0, w, h);

    for (const n of nodes) {
      const dx = mouse.x - n.x, dy = mouse.y - n.y, d = Math.hypot(dx, dy);
      if (d < 180) { n.vx += (dx / d) * .004; n.vy += (dy / d) * .004; }
      n.vx *= .995; n.vy *= .995;
      n.x += n.vx * dt * .06; n.y += n.vy * dt * .06;
      if (n.x < -20) n.x = w + 20; if (n.x > w + 20) n.x = -20;
      if (n.y < -20) n.y = h + 20; if (n.y > h + 20) n.y = -20;
      n.tw += dt * .002;
    }

    ctx.lineWidth = 1;
    for (let i = 0; i < nodes.length; i++) {
      const a = nodes[i];
      for (let j = i + 1; j < nodes.length; j++) {
        const b = nodes[j], d = Math.hypot(a.x - b.x, a.y - b.y);
        if (d < LINK) {
          const md = Math.hypot(mouse.x - (a.x + b.x) / 2, mouse.y - (a.y + b.y) / 2);
          const boost = md < 160 ? (1 - md / 160) * .35 : 0;
          ctx.strokeStyle = `rgba(${a.c},${(1 - d / LINK) * .16 + boost})`;
          ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y); ctx.stroke();
        }
      }
    }

    for (const n of nodes) {
      ctx.fillStyle = `rgba(${n.c},${.45 + Math.sin(n.tw) * .25})`;
      ctx.beginPath(); ctx.arc(n.x, n.y, n.r, 0, Math.PI * 2); ctx.fill();
    }

    if (now > spawnAt && packets.length < 14) { spawnPacket(); spawnAt = now + 260; }
    packets = packets.filter(p => {
      p.t += dt * .0016;
      if (p.t >= 1) {
        if (--p.hops <= 0) return false;
        const near = neighbors(p.b);
        if (!near.length) return false;
        p.a = p.b; p.b = near[Math.random() * near.length | 0]; p.t = 0;
      }
      const x = p.a.x + (p.b.x - p.a.x) * p.t, y = p.a.y + (p.b.y - p.a.y) * p.t;
      const g = ctx.createRadialGradient(x, y, 0, x, y, 14);
      g.addColorStop(0, `rgba(${p.c},.9)`); g.addColorStop(1, `rgba(${p.c},0)`);
      ctx.fillStyle = g; ctx.beginPath(); ctx.arc(x, y, 14, 0, Math.PI * 2); ctx.fill();
      ctx.fillStyle = "rgba(255,255,255,.95)"; ctx.beginPath(); ctx.arc(x, y, 1.6, 0, Math.PI * 2); ctx.fill();
      return true;
    });

    sparks = sparks.filter(s => {
      s.life -= dt; s.x += s.vx * dt; s.y += s.vy * dt; s.vx *= .985; s.vy *= .985;
      const a = Math.max(0, s.life / s.max);
      ctx.fillStyle = `rgba(${s.c},${a})`; ctx.beginPath(); ctx.arc(s.x, s.y, 2 * a + .4, 0, Math.PI * 2); ctx.fill();
      return s.life > 0;
    });
  }

  addEventListener("resize", () => { if (raf) resize(); });
  addEventListener("pointermove", e => { mouse.x = e.clientX; mouse.y = e.clientY; });
  document.addEventListener("pointerleave", () => { mouse.x = mouse.y = -1e4; });

  return {
    start() { if (still || raf) return; resize(); last = 0; raf = requestAnimationFrame(step); },
    stop() { cancelAnimationFrame(raf); raf = 0; },
    burst(x = w / 2, y = h / 2) {
      if (still) return;
      for (let i = 0; i < 90; i++) {
        const a = Math.random() * Math.PI * 2, v = Math.random() * .6 + .15, max = 600 + Math.random() * 500;
        sparks.push({ x, y, vx: Math.cos(a) * v, vy: Math.sin(a) * v, life: max, max, c: COLORS[i % 3] });
      }
      nodes.forEach(n => { const d = Math.hypot(n.x - x, n.y - y) || 1; n.vx += (n.x - x) / d * 1.2; n.vy += (n.y - y) / d * 1.2; });
    },
  };
})();
