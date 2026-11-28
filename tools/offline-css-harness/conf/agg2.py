import json, glob, re, sys, collections, os
L = "/tmp/claude-0/-home-user/cc5a650a-0655-55a3-841b-dd3395e06354/scratchpad/layer"
IN = L + "/conf/" + (sys.argv[1] if len(sys.argv) > 1 else "raw2")
OUTTSV = sys.argv[2] if len(sys.argv) > 2 else L + "/conflicts.tsv"
src = json.load(open(L + "/conf/srcindex.json"))
def norm(s): return re.sub(r'\s*([>+~,()])\s*', r'\1', re.sub(r'\s+', ' ', s.replace("'", '"'))).strip()
idx = collections.defaultdict(list)
for r in src: idx[(r['file'], norm(r['sel']))].append(r)
def relfile(u): return u.split('?')[0].split('/themes/bricks-child/')[-1]
def booster(sel): return bool(re.search(r'#[A-Za-z_]|html body|:root|\.z_', sel))
def locate(file, sel, prop):
    c = idx.get((file, norm(sel)), [])
    c2 = [r for r in c if prop in r['props'] or any(k in r['props'] for k in (prop.rsplit('-', 1)[0], prop.split('-')[0]))]
    c = c2 or c
    return c[0]['line'] if c else None
def bsig(sel): return re.sub(r'brxe-[a-z0-9]{6}', 'brxe-*', sel)
def elid(sel, rowid):
    m = re.search(r'brxe-[a-z0-9]{6}', sel); return m.group(0) if m else (rowid or '')
def postof(sh):
    m = re.search(r'/css/post-(\d+)\.min\.css', sh.get('url', ''))
    if m: return m.group(1)
    k = sh.get('kind', '?'); return k
G = collections.OrderedDict(); stats = collections.Counter(); per_el = set(); allsh = 0; detail = []
for f in glob.glob(IN + "/*_*.json"):
    D = json.load(open(f)); url, w = D['url'], D['w']
    for r in D['rows']:
        allsh += 1
        if not r['okpath']: stats['badpath'] += 1; continue
        recs = [x for x in r['rec'] if x['kind'] in ('decl', 'var')]
        if not recs: stats['derived_only'] += 1; continue
        stats['root_elems'] += 1
        for x in recs:
            p = x['prop']
            if x['kind'] == 'decl': P_, L_ = x['P'], x['L']; label = p
            else:
                vn, v = next(iter(x['vars'].items())); P_, L_ = v['P'], v['L']; label = f"{vn} (var via {p})"
            lk = L_['sheet']['kind'] if L_ else 'none'
            tf = relfile(L_['sheet']['url']) if L_ and lk == 'theme' else ''
            tsel = norm(L_['sel']) if tf else f"(L:{lk} {L_['sel'] if L_ else ''})"[:90]
            key = (tf, tsel, label if x['kind'] == 'decl' else label.split(' ')[0] + ' (var)')
            g = G.setdefault(key, {'inst': 0, 'el': set(), 'pages': set(), 'bsel': collections.Counter(), 'post': collections.Counter(), 'elid': set(), 'P': collections.Counter(), 'Lv': collections.Counter(), 'pk': collections.Counter(), 'ldecl': collections.Counter(), 'pdecl': collections.Counter(), 'imp': 0, 'kind': x['kind'], 'props': collections.Counter(), 'msel': collections.Counter(), 'media': collections.Counter()})
            g['inst'] += 1; g['el'].add((url, r['path'])); g['pages'].add(url); g['props'][p] += 1
            pk = P_['sheet']['kind'] if P_ else 'none'; g['pk'][pk] += 1
            if P_:
                g['bsel'][bsig(P_['msel'])] += 1; g['post'][postof(P_['sheet'])] += 1; g['elid'].add((elid(P_['msel'], r['id']), postof(P_['sheet'])))
                g['pdecl'][P_['name'] + ':' + P_['val']] += 1
            g['P'][x['va'] or ''] += 1; g['Lv'][x['vb'] or ''] += 1
            if L_: g['ldecl'][L_['name'] + ':' + L_['val']] += 1; g['imp'] += int(L_['imp']); g['msel'][L_['msel']] += 1; g['media'][','.join(L_['media'])] += 1
            detail.append((url, w, r['path'], x['kind'], p, tf, tsel, L_ and L_['val'], P_ and (P_['sheet'].get('url') or P_['sheet'].get('kind')), P_ and P_['msel'], P_ and P_['val'], x['va'], x['vb']))
GENERIC_OK = {'ics-bg-black', 'ics-pc', 'z_'}
def generic(sel):
    t = re.sub(r'#z_', '', sel)
    cls = set(re.findall(r'\.([A-Za-z_][\w-]*)', t)) - GENERIC_OK
    return not cls
def classify(key, g):
    tf, tsel, p = key
    if not tf: return 'x'
    ld = g['ldecl'].most_common(1)[0][0].split(':', 1)[1] if g['ldecl'] else ''
    pd = g['pdecl'].most_common(1)[0][0].split(':', 1)[1] if g['pdecl'] else ''
    if g['pdecl'] and norm(ld) == norm(pd): return 'b'
    # (a) generic base rule (no component class) whose declaration is dead on Bricks-styled elements; (c) component-specific rule (names a class / booster) that was meant to win but loses today
    return 'a' if generic(tsel) else 'c'
rows = []
for k, g in G.items():
    c = classify(k, g); tf, tsel, p = k
    line = locate(tf, tsel, p.replace(' (var)', '')) if tf else None
    bs = [f"{s}({n})" for s, n in g['bsel'].most_common(3)]
    posts = [f"{s}({n})" for s, n in g['post'].most_common(6)]
    els = sorted({e for e, _ in g['elid'] if e})
    rows.append([tf, f"{tsel}  @L{line}" if line else tsel, p, ' | '.join(bs), ','.join(posts), f"{len(els)}:" + ','.join(els[:4]), len(g['pages']), len(g['el']), g['inst'],
                 g['P'].most_common(1)[0][0][:50] if g['P'] else '', g['Lv'].most_common(1)[0][0][:50] if g['Lv'] else '', c, g['kind']])
rows.sort(key=lambda r: -r[7])
with open(OUTTSV, 'w') as f:
    f.write('\t'.join(['theme_file', 'theme_selector', 'prop', 'bricks_selector', 'post_id', 'element_id', 'pages', 'elements', 'instances', 'P_value', 'L_value', 'class', 'kind']) + '\n')
    for r in rows: f.write('\t'.join(str(x).replace('\t', ' ').replace('\n', ' ') for x in r) + '\n')
with open(OUTTSV.replace('.tsv', '_detail.tsv'), 'w') as f:
    for d in detail: f.write('\t'.join(str(x).replace('\t', ' ').replace('\n', ' ') for x in d) + '\n')
cc = collections.defaultdict(lambda: [0, 0, 0])
for r in rows: cc[r[11]][0] += 1; cc[r[11]][1] += r[7]; cc[r[11]][2] += r[8]
print('shifted rows', allsh, dict(stats)); print('groups', len(rows), {k: v for k, v in cc.items()})
for r in rows[:int(os.environ.get('TOP', 15))]: print(r[11], r[12], 'el', r[7], 'pg', r[6], r[0].split('/')[-1], r[1][:80], '|', r[2], '| P:', r[3][:50], '|', r[4][:20])

rl = collections.OrderedDict()
for k, g in G.items():
    key = (k[0], k[1]); e = rl.setdefault(key, {'el': set(), 'inst': 0, 'props': set(), 'pages': set(), 'cls': classify(k, g)})
    e['el'] |= g['el']; e['inst'] += g['inst']; e['props'].add(k[2]); e['pages'] |= g['pages']
rc = collections.defaultdict(lambda: [0, 0, 0])
with open(OUTTSV.replace('.tsv', '_rules.tsv'), 'w') as f:
    f.write('class\ttheme_file\ttheme_selector\tprops\tpages\telements\tinstances\n')
    for (tf, ts), e in sorted(rl.items(), key=lambda kv: -len(kv[1]['el'])):
        f.write(f"{e['cls']}\t{tf}\t{ts[:160]}\t{','.join(sorted(e['props']))}\t{len(e['pages'])}\t{len(e['el'])}\t{e['inst']}\n")
        rc[e['cls']][0] += 1; rc[e['cls']][1] += len(e['el']); rc[e['cls']][2] += e['inst']
print('RULE-level (rules, distinct elements, instances) by class:', dict(rc))
