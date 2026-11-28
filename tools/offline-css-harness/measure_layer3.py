import asyncio, json, os, re, sys, subprocess, hashlib, time
from playwright.async_api import async_playwright
S_ = os.environ.get("HARNESS_ROOT", "/tmp/claude-0/-home-user/cc5a650a-0655-55a3-841b-dd3395e06354/scratchpad")
B = S_ + "/bulk2"
BASE = "https://ics2.reika.sg"
WIDTHS = [int(x) for x in sys.argv[1].split(",")] if len(sys.argv) > 1 else [1440, 768, 390]
LIMIT = int(sys.argv[2]) if len(sys.argv) > 2 else 10**9
CONC = 4
SKIPPX = os.environ.get("SKIPPX","0")=="1"
RES_DIR = os.environ["TAG"]
L = S_ + "/layer"
VARDIR = os.environ.get("VARDIR", L + "/variants")
BMAP = json.load(open(VARDIR + "/B_css.json")) if os.path.exists(VARDIR + "/B_css.json") else {}
AMAP = json.load(open(L + "/variants/A_css.json"))
FMAP = json.load(open(VARDIR + "/F_css.json")) if os.path.exists(VARDIR + "/F_css.json") else {}
MARK = json.load(open(VARDIR + "/markers.json")) if os.path.exists(VARDIR + "/markers.json") else {}
MASKS = set()
if os.environ.get("MASKS"):
    MASKS = set((u, p) for u, p in json.load(open(os.environ["MASKS"])))
PROPS = ['color','background-color','background-image','font-size','font-weight','line-height',
 'margin-top','margin-right','margin-bottom','margin-left','padding-top','padding-right','padding-bottom','padding-left',
 'width','height','top','left','transform','display','position','z-index','opacity',
 'border-top-width','border-right-width','border-bottom-width','border-left-width',
 'border-top-style','border-right-style','border-bottom-style','border-left-style',
 'border-top-color','border-right-color','border-bottom-color','border-left-color','mask-image','-webkit-mask-image']
LAYOUT = {'width','height','top','left','transform','display','position','margin-top','margin-right','margin-bottom','margin-left','padding-top','padding-right','padding-bottom','padding-left','border-top-width','border-right-width','border-bottom-width','border-left-width'}
# Test-harness freeze only (nothing ships): seeded randomness, constant clock, reduced motion.
INIT = """(() => { let s = 20261127 >>> 0;
  Math.random = () => { s = (Math.imul(s, 1664525) + 1013904223) >>> 0; return s / 4294967296; };
  const T0 = 1795000000000; Date.now = () => T0; performance.now = () => 1000; })();"""
# After settle: top, 300ms, pause every Web Animation/transition at t=0, two frames.
FINTR = os.environ.get("FINTR","1")=="1"
FREEZE = ("(()=>{const FINTR=" + ("true" if FINTR else "false") + ";return ") + """() => new Promise((res) => {
  window.scrollTo(0, 0);
  setTimeout(() => {
    for (const a of document.getAnimations()) { if (FINTR && a instanceof CSSTransition) { a.finish(); } else { a.pause(); a.currentTime = 0; } }
    requestAnimationFrame(() => requestAnimationFrame(() => res(document.getAnimations().length)));
  }, 300);
})""" + "})()"
COLLECT = """(props) => {
  const pathOf = (el) => { const parts = []; while (el && el.nodeType === 1) {
    const p = el.parentElement; const tag = el.tagName.toLowerCase();
    if (!p) { parts.unshift(tag); break; }
    parts.unshift(tag + ':' + ([...p.children].indexOf(el) + 1)); el = p; } return parts.join('>'); };
  const all = [...document.querySelectorAll('*')]; const ix = new Map(all.map((e, i) => [e, i]));
  return all.map((el) => {
    const cs = getComputedStyle(el); const o = {};
    for (const p of props) o[p] = cs.getPropertyValue(p);
    const r = el.getBoundingClientRect();
    o.__rect = [r.x + scrollX, r.y + scrollY, r.width, r.height];
    const cls = typeof el.className === 'string' ? el.className : (el.getAttribute('class') || '');
    return [el.tagName.toLowerCase(), cls.slice(0, 100), el.id || '', o, pathOf(el), ix.get(el.parentElement) ?? -1];
  });
}"""
MARKERS = """() => {
  const els = [...document.querySelectorAll('*')]; const idx = new Map(els.map((e, i) => [e, i]));
  const rules = [];
  const walk = (list) => { for (const r of list) {
    if (r.selectorText !== undefined && r.style) { const v = r.style.getPropertyValue('--ics-strip').trim(); if (v) rules.push([v, r.selectorText]); }
    if (r.cssRules) { try { walk(r.cssRules); } catch (e) {} } } };
  for (const s of document.styleSheets) { if (!(s.href || '').includes('/bricks-child/assets/')) continue; try { walk(s.cssRules); } catch (e) {} }
  const out = {};
  for (const [id, sel] of rules) {
    let list = null;
    try { list = document.querySelectorAll(sel); }
    catch (e) { const s2 = sel.replace(/::?[a-zA-Z-]+(\\([^)]*\\))?/g, '').trim(); try { list = s2 ? document.querySelectorAll(s2) : []; } catch (e2) { continue; } }
    for (const el of list) { const i = idx.get(el); if (i === undefined) continue; (out[i] = out[i] || []).push(+id); }
  }
  return out;
}"""
def slug(u):
    p = u.replace(BASE, "") or "/"
    return (re.sub(r"[^a-zA-Z0-9]+", "_", p).strip("_") or "home")[:120] + "_" + hashlib.md5(u.encode()).hexdigest()[:6]
def related(p, props):
    return any(p == q or p.startswith(q + '-') or q.startswith(p + '-') for q in props)
async def scroll_all(pg):
    h = await pg.evaluate("document.body.scrollHeight"); y = 0
    while y < h:
        await pg.evaluate(f"window.scrollTo(0,{y})"); await pg.wait_for_timeout(120); y += 500
    await pg.evaluate("window.scrollTo(0,0)"); await pg.wait_for_timeout(2500)

sys.path.insert(0, L)
from layer_html import unlayer, layer_owner
from layer_html2 import layer_owner2
SMAP = {}
BASE_SPEC = os.environ["BASE_SPEC"]; TEST_SPEC = os.environ["TEST_SPEC"]   # "html:css", html in raw|A|L|Lnoinl, css in A|B
OUTD = os.path.join(L, "res", os.environ["TAG"]); SHOTD = os.path.join(L, "shots", os.environ["TAG"])
os.makedirs(OUTD, exist_ok=True); os.makedirs(SHOTD, exist_ok=True)
_raw = {}
def raw_doc(har):
    if har not in _raw: _raw[har] = json.load(open(har))['log']['entries'][0]['response']['content']['text']
    return _raw[har]
def html_for(mode, raw):
    if mode == 'raw': return raw
    a = unlayer(raw)
    if mode == 'A': return a
    if mode == 'L': return layer_owner(a)
    if mode == 'Lnoinl': return layer_owner(a, inline=False)
    if mode == 'L2': return layer_owner2(a)
    if mode == 'Lp': return layer_owner(a, post=False)
    if mode == 'Lpnoinl': return layer_owner(a, inline=False, post=False)
    raise ValueError(mode)
async def run_variant(b, url, w, spec, har, shot_path):
    hmode, cmode = spec.split(":")
    ctx = await b.new_context(viewport={"width": w, "height": 900}, device_scale_factor=1, reduced_motion="reduce")
    await ctx.add_init_script(INIT)
    await ctx.route_from_har(har, not_found="abort")
    if hmode != 'raw':
        body = html_for(hmode, raw_doc(har)).encode('utf-8')
        async def hd(route, request):
            await route.fulfill(status=200, body=body, content_type="text/html; charset=UTF-8", headers={"cache-control": "no-store"})
        await ctx.route(re.compile("^" + re.escape(url) + "$"), hd)
    cmap = {'B': BMAP, 'S': SMAP, 'F': FMAP}.get(cmode, AMAP)
    async def h(route, request):
        body = cmap.get(request.url)
        if body is None: await route.fallback()
        else: await route.fulfill(status=200, body=body, content_type="text/css", headers={"cache-control": "no-store"})
    await ctx.route(re.compile(r".*/themes/bricks-child/assets/.*\.css.*"), h)
    pg = await ctx.new_page()
    await pg.goto(url, wait_until="load", timeout=60000)
    await pg.wait_for_timeout(400)
    await scroll_all(pg)
    await pg.evaluate(FREEZE)
    data = await pg.evaluate(COLLECT, PROPS)
    marks = await pg.evaluate(MARKERS) if cmode == 'B' else {}
    if not SKIPPX: await pg.screenshot(path=shot_path, full_page=True, animations="disabled")
    await ctx.close()
    return data, marks
async def job(b, sem, url, w, log):
    s = slug(url); har = os.path.join(B, "har", f"{s}_1440.har")
    res_path = os.path.join(OUTD, f"{s}_{w}.json")
    if os.path.exists(res_path): return
    if not os.path.exists(har): return
    async with sem:
        sa = os.path.join(SHOTD, f"{s}_{w}_base.png"); sb = os.path.join(SHOTD, f"{s}_{w}_test.png"); sd = os.path.join(SHOTD, f"{s}_{w}_diff.png")
        try:
            cp = os.environ.get("BASE_CACHE")
            cf = f"{cp}/{s}_{w}.json" if cp else None
            if cf and os.path.exists(cf): A = json.load(open(cf))
            else:
                A, _ = await run_variant(b, url, w, BASE_SPEC, har, sa)
                if cf: os.makedirs(cp, exist_ok=True); json.dump(A, open(cf, "w"))
            Bd, marks = await run_variant(b, url, w, TEST_SPEC, har, sb)
        except Exception as e:
            log.append({"url": url, "w": w, "err": str(e)[:300]}); return
        d = {} if SKIPPX else json.loads(subprocess.run(["node", B + "/tools/diff.mjs", sa, sb, sd], capture_output=True, text=True).stdout or "{}")
        shifted = []; attributed = {}; unattr = 0; masked_shifted = 0; mstats = {}
        for i in range(min(len(A), len(Bd))):
            ta, ca, ia, oa, pa, _pa = A[i]; tb, cb, ib, ob, pb, _pb = Bd[i]
            masked = (url, pa) in MASKS
            cands = marks.get(str(i), [])
            for mid in cands:
                st = mstats.setdefault(str(mid), [0, 0]); st[0] += 1; st[1] += int(masked)
            changed = [p for p in PROPS if oa[p] != ob[p]]
            ra, rb = oa['__rect'], ob['__rect']
            layout = any(abs(x - y) > 0.5 for x, y in zip(ra, rb))
            if not changed and not layout: continue
            if masked: masked_shifted += 1; continue
            hit = False
            for mid in cands:
                m = MARK[str(mid)]
                if changed: props = [p for p in changed if related(p, m["props"])]
                else: props = ["(layout)"] if any(q in LAYOUT for q in m["props"]) else []
                if props:
                    hit = True
                    e = attributed.setdefault(str(mid), {"props": set(), "elements": 0})
                    e["props"].update(props); e["elements"] += 1
            if not hit: unattr += 1
            chain = []; j = i; depth = 0
            while j >= 0 and depth < 60:
                chain += marks.get(str(j), []); j = Bd[j][5]; depth += 1
            shifted.append({"i": i, "chain": sorted(set(chain)), "path": pa, "tag": ta, "cls": ca[:80], "id": ia, "props": {p: [oa[p], ob[p]] for p in changed}, "layout": layout,
                            "rectA": [round(x, 1) for x in ra], "rectB": [round(x, 1) for x in rb], "attr": [int(c) for c in cands if str(c) in attributed]})
        for k in attributed: attributed[k]["props"] = sorted(attributed[k]["props"])
        out = {"url": url, "w": w, "base": BASE_SPEC, "test": TEST_SPEC, "elements": len(A), "elements_B": len(Bd), "shifted": len(shifted), "shifted_pct": round(100 * len(shifted) / max(1, len(A)), 2),
               "masked_shifted": masked_shifted, "unattributed": unattr, "pixel": d, "attributed": attributed, "mask_stats": mstats,
               "matched": sorted(mstats.keys()), "shifted_detail": shifted}
        json.dump(out, open(res_path, "w"))
        log.append({"url": url, "w": w, "shifted": len(shifted), "masked": masked_shifted, "px": d.get("pct")})
        print(url, w, "shifted", len(shifted), "masked", masked_shifted, "px%", d.get("pct"), flush=True)
async def main():
    pages = [l.strip() for l in open(os.environ.get("PAGES") or os.path.join(B, "pages.txt")) if l.strip()][:LIMIT]
    sem = asyncio.Semaphore(CONC); log = []
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path="/usr/bin/google-chrome", args=["--no-sandbox"])
        await asyncio.gather(*[job(b, sem, u, w, log) for w in WIDTHS for u in pages])
        await b.close()
    json.dump(log, open(os.path.join(OUTD, "_log.json"), "w"), indent=1)
    print("finished", len(log), flush=True)
asyncio.run(main())
