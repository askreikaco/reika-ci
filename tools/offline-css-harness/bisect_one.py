"""usage: bisect_one.py <ids_file> <tag_prefix> [pages_file] [max_tests] [widths]
Bisection: test(ids)=0 shifts (excluding header-container auto-margin flake) -> accept; else halve. Writes <tag>_result.json"""
import json, subprocess, sys, os, glob, time
S = os.environ.get("HARNESS_ROOT", "/tmp/claude-0/-home-user/cc5a650a-0655-55a3-841b-dd3395e06354/scratchpad"); L = S + "/layer"
ids = [int(x) for x in open(sys.argv[1]).read().split()]; pre = sys.argv[2]
pages = sys.argv[3] if len(sys.argv) > 3 else L + "/conf/pages_torn.txt"; budget = int(sys.argv[4]) if len(sys.argv) > 4 else 40
widths = sys.argv[5] if len(sys.argv) > 5 else "1440,768,390"
n = [0]; accepted = []; rejected = []; unres = []; log = []; t0 = time.time()
def shifts(tag):
    tot = 0; det = []
    for p in glob.glob(f"{L}/res/{tag}/*_*.json"):
        if p.endswith("_log.json"): continue
        R = json.load(open(p))
        for s in R["shifted_detail"]:
            if s["path"] == "html>body:2>header:2>section:1>div:1" and set(s["props"]) <= {"margin-left", "margin-right"} and s["rectA"] == s["rectB"]: continue
            tot += 1; det.append((R["url"], R["w"], s["path"], list(s["props"])))
    return tot, det
def test(sub):
    n[0] += 1; k = f"{pre}{n[0]}"; budget_left = budget - n[0]
    d = f"{L}/fix/{k}"; os.makedirs(d, exist_ok=True)
    idf = f"{d}/sel_ids.txt"; open(idf, "w").write(" ".join(map(str, sub)))
    r = subprocess.run(["python3", L + "/strip_one.py", L + "/fix/v1/F_css.json", "bundle-torn-motion.css", d, idf], capture_output=True, text=True)
    if r.returncode: raise SystemExit(r.stderr[-400:])
    env = dict(os.environ, PAGES=pages, VARDIR=d, TAG=k, BASE_SPEC="L2:F", TEST_SPEC="L2:B", SKIPPX="1", BASE_CACHE=L + "/fix/cache_L2F", MASKS=S + "/bulk2/masks.json")
    subprocess.run(["python3", L + "/measure_layer3.py", widths], env=env, cwd=L, capture_output=True, text=True)
    tot, det = shifts(k); log.append({"test": k, "n_ids": len(sub), "shifted": tot, "min": round((time.time() - t0) / 60, 1)})
    print(k, len(sub), "shifted", tot, f"{(time.time()-t0)/60:.1f}min", flush=True)
    return tot
def bis(sub, depth):
    if not sub: return
    if n[0] >= budget: unres.extend(sub); return   # budget: left unresolved
    if test(sub) == 0: accepted.extend(sub); return
    if len(sub) == 1: rejected.extend(sub); return
    h = len(sub) // 2; bis(sub[:h], depth + 1); bis(sub[h:], depth + 1)
bis(ids, 0)
json.dump({"accepted": sorted(accepted), "rejected_single": sorted(rejected), "unresolved": sorted(unres), "tests": n[0], "log": log, "minutes": round((time.time() - t0) / 60, 1)}, open(f"{L}/fix/{pre}_result.json", "w"), indent=1)
print("accepted", len(accepted), "rejected", len(rejected), "unresolved", len(unres), "tests", n[0])
