import json, glob, sys, collections
d = sys.argv[1]
rows = [json.load(open(p)) for p in glob.glob(d + "/*_*.json") if not p.endswith("_log.json")]
print("results:", len(rows), "base/test:", rows[0]["base"] if rows else "", rows[0]["test"] if rows else "")
for w in sorted({r["w"] for r in rows}):
    rr = [r for r in rows if r["w"] == w]
    sh = sum(r["shifted"] for r in rr); pages = sum(1 for r in rr if r["shifted"])
    px = [r["pixel"].get("pct", 0) for r in rr]
    print(f"w={w}: pages={len(rr)} pages_with_shift={pages} shifted_elems={sh} unmasked_px_pages={sum(1 for x in px if x>0)} max_px%={max(px):.3f}")
tot = sum(r["shifted"] for r in rows); print("TOTAL shifted (unmasked):", tot)
pc = collections.Counter(); sel = collections.Counter(); tag = collections.Counter(); cls = collections.Counter()
for r in rows:
    for s in r["shifted_detail"]:
        for p in s["props"]: pc[p] += 1
        tag[s["tag"]] += 1
        cls[s["cls"][:50]] += 1
print("changed props:", pc.most_common(10)); print("tags:", tag.most_common(8))
print("top classes:", cls.most_common(12))
worst = sorted(rows, key=lambda r: -r["shifted"])[:8]
for r in worst: print("  worst", r["w"], r["shifted"], r["pixel"].get("pct"), r["url"])
