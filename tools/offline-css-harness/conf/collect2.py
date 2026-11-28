"""v2: full computed-style diff of every shifted element (P vs T), then CDP matched-style winners per differing prop, resolving var() custom-property winners.
env: SRC_RES, OUT, ONLY_PX, BASE_SPEC (raw:A), TEST_SPEC (L:A), TEST_CSS (json url->css override for theme files in TEST variant), CONC, LIMIT, PAGES(file with urls)"""
import asyncio, json, os, re, sys, glob
S_ = os.environ.get("HARNESS_ROOT", "/tmp/claude-0/-home-user/cc5a650a-0655-55a3-841b-dd3395e06354/scratchpad"); L = S_ + "/layer"
os.environ.setdefault("TAG", "conf_tmp"); os.environ.setdefault("BASE_SPEC", "raw:A"); os.environ.setdefault("TEST_SPEC", "L:A")
src = open(L + "/measure_layer3.py").read().split("async def job(")[0]
exec(compile(src, "measure_layer_head", "exec"))
SRC_RES = os.environ.get("SRC_RES", "cmp_L_vs_P"); OUT = L + "/conf/" + os.environ.get("OUT", "raw2"); os.makedirs(OUT, exist_ok=True)
CONC_N = int(os.environ.get("CONC", "4"))
EXTRA = {}
if os.environ.get("TEST_CSS"): EXTRA['T'] = json.load(open(os.environ["TEST_CSS"]))
LAYER_ORDER = {'wp': 0, 'plugins': 1, 'bricks': 2}
SHORT = {
 'margin-top':['margin'],'margin-right':['margin'],'margin-bottom':['margin'],'margin-left':['margin'],
 'padding-top':['padding'],'padding-right':['padding'],'padding-bottom':['padding'],'padding-left':['padding'],
 'border-top-width':['border-width','border-top','border'],'border-right-width':['border-width','border-right','border'],'border-bottom-width':['border-width','border-bottom','border'],'border-left-width':['border-width','border-left','border'],
 'border-top-style':['border-style','border-top','border'],'border-right-style':['border-style','border-right','border'],'border-bottom-style':['border-style','border-bottom','border'],'border-left-style':['border-style','border-left','border'],
 'border-top-color':['border-color','border-top','border'],'border-right-color':['border-color','border-right','border'],'border-bottom-color':['border-color','border-bottom','border'],'border-left-color':['border-color','border-left','border'],
 'background-color':['background'],'background-image':['background'],'background-position-x':['background','background-position'],'background-position-y':['background','background-position'],'background-size':['background'],'background-repeat':['background'],
 'top':['inset'],'left':['inset'],'right':['inset'],'bottom':['inset'],'line-height':['font'],'font-size':['font'],'font-weight':['font'],'font-family':['font'],
 'flex-grow':['flex'],'flex-shrink':['flex'],'flex-basis':['flex'],'flex-direction':['flex-flow'],'flex-wrap':['flex-flow'],
 'row-gap':['gap'],'column-gap':['gap'],'overflow-x':['overflow'],'overflow-y':['overflow'],
 'justify-content':['place-content'],'align-content':['place-content'],'align-items':['place-items'],'justify-items':['place-items'],'align-self':['place-self'],'justify-self':['place-self'],
 'grid-template-columns':['grid-template','grid'],'grid-template-rows':['grid-template','grid'],
 'border-top-left-radius':['border-radius'],'border-top-right-radius':['border-radius'],'border-bottom-left-radius':['border-radius'],'border-bottom-right-radius':['border-radius'],
 'mask-image':['mask','-webkit-mask'],'-webkit-mask-image':['mask','-webkit-mask','mask-image'],
 'text-decoration-line':['text-decoration'],'text-decoration-color':['text-decoration'],'outline-width':['outline'],'outline-style':['outline'],'outline-color':['outline'],
 'transition-property':['transition'],'transition-duration':['transition'],'animation-name':['animation'],'list-style-type':['list-style'],
}

LOG = {'margin-top':['margin-block-start','margin-block'],'margin-bottom':['margin-block-end','margin-block'],'margin-left':['margin-inline-start','margin-inline'],'margin-right':['margin-inline-end','margin-inline'],
 'padding-top':['padding-block-start','padding-block'],'padding-bottom':['padding-block-end','padding-block'],'padding-left':['padding-inline-start','padding-inline'],'padding-right':['padding-inline-end','padding-inline'],
 'top':['inset-block-start','inset-block'],'bottom':['inset-block-end','inset-block'],'left':['inset-inline-start','inset-inline'],'right':['inset-inline-end','inset-inline'],
 'min-height':['min-block-size'],'min-width':['min-inline-size'],'max-height':['max-block-size'],'max-width':['max-inline-size'],
 'border-top-width':['border-block-start-width','border-block-width','border-block-start','border-block'],'border-bottom-width':['border-block-end-width','border-block-width','border-block-end','border-block'],
 'border-left-width':['border-inline-start-width','border-inline-width','border-inline-start','border-inline'],'border-right-width':['border-inline-end-width','border-inline-width','border-inline-end','border-inline'],
 'overflow-x':['overflow-inline'],'overflow-y':['overflow-block']}
for k,v in LOG.items(): SHORT.setdefault(k,[]).extend(v)
# computed props that are used-value consequences of layout, never a cause
DERIVED = {'perspective-origin','transform-origin'}
LOGICAL = re.compile(r'(^|-)(block|inline)(-|$)')
INHERITED = {'color','font-size','font-weight','line-height','font-family','font-style','letter-spacing','text-align','text-transform','white-space','visibility','cursor','list-style-type','word-spacing','text-indent','font-variant','text-shadow','fill','stroke','direction'}
def covers(name, prop): return name == prop or name in SHORT.get(prop, [])
def layer_rank(rule):
    ls = rule.get('layers') or []
    if not ls: return 99
    for x in ls:
        if x.get('text') in LAYER_ORDER: return LAYER_ORDER[x['text']]
    return 50
def rank_key(c):
    if c['inline']: return (2, 0, 0, c['idx']) if c['imp'] else (1, 99.5, 0, c['idx'])
    return (2, -c['layer'], 0, c['idx']) if c['imp'] else (1, c['layer'], 0, c['idx'])
ALLCOMP = """(idxs) => { const els = document.querySelectorAll('*'); const out = {};
  for (const i of idxs) { const cs = getComputedStyle(els[i]); const o = {}; for (let k = 0; k < cs.length; k++) { const p = cs[k]; if (p.startsWith('--')) continue; o[p] = cs.getPropertyValue(p); } out[i] = o; } return out; }"""
def cands_of(rules, inline, keep):
    cs = []
    for k, mr in enumerate(rules):
        r = mr['rule']
        if r.get('origin') != 'regular': continue
        sel = r['selectorList']['text']; sels = r['selectorList']['selectors']; ms = mr.get('matchingSelectors') or []
        msel = ', '.join(sels[j]['text'] for j in ms if j < len(sels)) or sel
        lr = layer_rank(r); media = [x['text'] for x in (r.get('media') or [])]
        expl = {q['name']: q['value'] for q in r['style']['cssProperties'] if q.get('value') and not q.get('implicit')}
        for pr in r['style']['cssProperties']:
            if pr.get('disabled') or not pr.get('parsedOk', True): continue
            if keep and not keep(pr['name']): continue
            if not pr.get('value'):
                pr = dict(pr); pr['value'] = next((v for n_, v in expl.items() if covers(n_, pr['name'])), '')
            cs.append([pr['name'], pr['value'], bool(pr.get('important')), lr, False, k, r.get('styleSheetId'), sel, msel, media])
    if inline:
        for pr in inline['cssProperties']:
            if pr.get('disabled') or not pr.get('parsedOk', True): continue
            if keep and not keep(pr['name']): continue
            cs.append([pr['name'], pr['value'], bool(pr.get('important')), 100, True, 10**6, None, '[style]', '[style]', []])
    return cs
def mk(c): return {'name': c[0], 'val': c[1], 'imp': c[2], 'layer': c[3], 'inline': c[4], 'idx': c[5], 'ssid': c[6], 'sel': c[7], 'msel': c[8], 'media': c[9]}
def pick(own, inh, prop, inheritable):
    cs = [mk(c) for c in own if covers(c[0], prop)]; src = 'own'
    if not cs and inheritable:
        for lvl, ic in enumerate(inh):
            cs = [mk(c) for c in ic if covers(c[0], prop)]
            if cs: src = f'inh{lvl+1}'; break
    if not cs: return None, src
    return max(cs, key=rank_key), src
async def render(b, url, w, spec, har, idxs):
    hmode, cmode = spec.split(":")
    ctx = await b.new_context(viewport={"width": w, "height": 900}, device_scale_factor=1, reduced_motion="reduce")
    await ctx.add_init_script(INIT)
    await ctx.route_from_har(har, not_found="abort")
    if hmode != 'raw':
        body = html_for(hmode, raw_doc(har)).encode('utf-8')
        async def hd(route, request):
            await route.fulfill(status=200, body=body, content_type="text/html; charset=UTF-8", headers={"cache-control": "no-store"})
        await ctx.route(re.compile("^" + re.escape(url) + "$"), hd)
    cmap = {'B': BMAP, 'S': SMAP}.get(cmode, AMAP)
    if cmode == 'T' and EXTRA.get('T') is not None: cmap = EXTRA['T']
    async def h(route, request):
        bd = cmap.get(request.url)
        if bd is None: await route.fallback()
        else: await route.fulfill(status=200, body=bd, content_type="text/css", headers={"cache-control": "no-store"})
    await ctx.route(re.compile(r".*/themes/bricks-child/assets/.*\.css.*"), h)
    pg = await ctx.new_page(); cdp = await ctx.new_cdp_session(pg); sheets = {}
    def on_added(ev):
        x = ev['header']; sheets[x['styleSheetId']] = {'url': x.get('sourceURL', ''), 'inline': x.get('isInline', False), 'owner': x.get('ownerNode')}
    cdp.on("CSS.styleSheetAdded", on_added)
    await cdp.send("DOM.enable"); await cdp.send("CSS.enable")
    await pg.goto(url, wait_until="load", timeout=60000)
    await pg.wait_for_timeout(400); await scroll_all(pg); await pg.evaluate(FREEZE)
    data = await pg.evaluate(COLLECT, PROPS)
    comp = await pg.evaluate(ALLCOMP, idxs)
    for ssid, s in sheets.items():
        u = s['url']; s['id'] = ''
        if s['owner'] and (s['inline'] or not u):
            try:
                d = await cdp.send("DOM.describeNode", {"backendNodeId": s['owner']}); at = d['node'].get('attributes', []); s['id'] = dict(zip(at[::2], at[1::2])).get('id', '')
            except Exception: pass
        s['kind'] = 'theme' if '/themes/bricks-child/' in u else 'bricks-post' if '/uploads/bricks/css/post-' in u else 'bricks' if ('/themes/bricks/' in u or '/uploads/bricks/' in u) else 'plugin' if '/plugins/' in u else ('inline:' + s['id']) if (s['inline'] or not u) else 'other'
    await cdp.send("DOM.getDocument", {"depth": 0})
    matched = {}
    keep_inh = lambda n: n.startswith('--') or n in INHERITED or any(n in v for v in () )
    for i in idxs:
        r = await cdp.send("Runtime.evaluate", {"expression": f"document.querySelectorAll('*')[{i}]"})
        oid = r['result'].get('objectId')
        if not oid: continue
        try:
            n = await cdp.send("DOM.requestNode", {"objectId": oid})
            m = await cdp.send("CSS.getMatchedStylesForNode", {"nodeId": n['nodeId']})
            matched[i] = {'own': cands_of(m.get('matchedCSSRules', []), m.get('inlineStyle'), None),
                          'inh': [cands_of(x.get('matchedCSSRules', []), None, lambda nm: nm.startswith('--') or nm in INHERITED or nm in ('font','text-decoration','list-style')) for x in m.get('inherited', [])]}
        except Exception as e: matched[i] = {'own': [], 'inh': [], 'err': str(e)[:80]}
        await cdp.send("Runtime.releaseObject", {"objectId": oid})
    await ctx.close()
    return data, comp, matched, sheets
def sheet_desc(sheets, ssid):
    s = sheets.get(ssid) if ssid else None
    if not s: return {'kind': 'inline-attr' if ssid is None else 'unknown', 'url': ''}
    return {'kind': s['kind'], 'url': s['url']}
def win_desc(sheets, w, src):
    if not w: return None
    return {'src': src, 'name': w['name'], 'val': w['val'], 'imp': w['imp'], 'sel': w['sel'], 'msel': w['msel'], 'media': w['media'], 'layer': w['layer'], 'sheet': sheet_desc(sheets, w['ssid'])}
def ident(d): return None if not d else (d['sheet']['kind'], d['sheet']['url'].split('?')[0], d['sel'], d['name'], d['val'], d['imp'])
def analyse(i, ca, cb, ma, mb, sa, sb):
    alld = [p for p in cb if ca.get(p) != cb.get(p)]
    diff = [p for p in alld if p not in DERIVED and not LOGICAL.search(p)]
    out = []
    for p in diff:
        inh = p in INHERITED
        wa, srca = pick(ma['own'], ma['inh'], p, inh); wb, srcb = pick(mb['own'], mb['inh'], p, inh)
        da, db = win_desc(sa, wa, srca), win_desc(sb, wb, srcb)
        rec = {'prop': p, 'va': ca.get(p), 'vb': cb.get(p), 'P': da, 'L': db, 'vars': {}}
        if ident(da) == ident(db):
            # same declaration: cause is a var() it uses, or it is a used-value consequence
            seen = set(); stack = [(vn, 0) for vn in set(re.findall(r'var\((--[\w-]+)', (da or {}).get('val', '')))]
            while stack:
                vn, dep = stack.pop()
                if vn in seen or dep > 6: continue
                seen.add(vn)
                pa, _ = pick_var(ma, vn); pb, _ = pick_var(mb, vn)
                dpa, dpb = win_desc(sa, pa, ''), win_desc(sb, pb, '')
                if ident(dpa) != ident(dpb): rec['vars'][vn] = {'P': dpa, 'L': dpb}
                for d_ in (dpa, dpb):
                    if d_:
                        for v2 in re.findall(r'var\((--[\w-]+)', d_['val']): stack.append((v2, dep + 1))
            if not rec['vars']:
                if da and da['src'] == 'own' and p not in ('top','left','right','bottom','margin-left','margin-right','margin-top','margin-bottom','min-height','min-width','max-width','max-height') : rec['kind'] = 'unexplained'
                else: continue   # derived
            else: rec['kind'] = 'var'
        else: rec['kind'] = 'decl'
        out.append(rec)
    return diff, out
def pick_var(m, name):
    cs = [mk(c) for c in m['own'] if c[0] == name]; src = 'own'
    if not cs:
        for lvl, ic in enumerate(m['inh']):
            cs = [mk(c) for c in ic if c[0] == name]
            if cs: src = f'inh{lvl+1}'; break
    if not cs: return None, src
    return max(cs, key=rank_key), src
async def job(b, sem, R):
    url, w = R['url'], R['w']; s = slug(url); har = os.path.join(B, "har", f"{s}_1440.har"); outp = f"{OUT}/{s}_{w}.json"
    if os.path.exists(outp): return
    idxs = [d['i'] for d in R['shifted_detail']]
    if not idxs: return
    async with sem:
        try:
            dA, cA, mA, sA = await render(b, url, w, BASE_SPEC, har, idxs)
            dB, cB, mB, sB = await render(b, url, w, TEST_SPEC, har, idxs)
        except Exception as e:
            print("ERR", url, w, str(e)[:200], flush=True); return
    rows = []
    for d in R['shifted_detail']:
        i = d['i']; k = str(i)
        if k not in cA or k not in cB or i not in mA or i not in mB: continue
        diff, rec = analyse(i, cA[k], cB[k], mA[i], mB[i], sA, sB)
        rows.append({'i': i, 'path': d['path'], 'okpath': i < len(dA) and dA[i][4] == d['path'] and i < len(dB) and dB[i][4] == d['path'], 'tag': d['tag'], 'cls': d['cls'], 'id': d['id'], 'ndiff': len(diff), 'diff': diff, 'rec': rec, 'layout': d['layout']})
    json.dump({'url': url, 'w': w, 'n_shifted': R['shifted'], 'rows': rows}, open(outp, 'w'))
    print("done", url, w, len(rows), flush=True)
async def main():
    only_px = os.environ.get("ONLY_PX", "0") == "1"; pages = set(l.strip() for l in open(os.environ["PAGES"])) if os.environ.get("PAGES") else None
    Rs = []
    for f in sorted(glob.glob(f"{L}/res/{SRC_RES}/*_*.json")):
        if f.endswith("_log.json"): continue
        R = json.load(open(f))
        if only_px and not (R['pixel'].get('pct', 0) or 0) > 0: continue
        if pages and R['url'] not in pages: continue
        if not R['shifted_detail']: continue
        Rs.append(R)
    if os.environ.get("LIMIT"): Rs = Rs[:int(os.environ["LIMIT"])]
    print("jobs", len(Rs), flush=True)
    sem = asyncio.Semaphore(CONC_N)
    async with async_playwright() as p:
        bb = await p.chromium.launch(executable_path="/usr/bin/google-chrome", args=["--no-sandbox"])
        await asyncio.gather(*[job(bb, sem, R) for R in Rs]); await bb.close()
asyncio.run(main())
