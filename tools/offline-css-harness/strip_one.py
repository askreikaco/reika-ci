"""usage: strip_one.py <F_css.json> <file_substr> <outdir> [ids_file|ALL]
Builds <outdir>/B_css.json + markers.json: only candidate rules in files matching file_substr (and in ids_file if given) are transformed. ids = numbering over ALL candidates of the F input (stable)."""
import json, subprocess, sys, os
S = os.environ.get("HARNESS_ROOT", "/tmp/claude-0/-home-user/cc5a650a-0655-55a3-841b-dd3395e06354/scratchpad"); B = S + "/bulk2"
fjson, fsub, outdir = sys.argv[1:4]; ids = sys.argv[4] if len(sys.argv) > 4 else "ALL"
os.makedirs(outdir, exist_ok=True)
F = json.load(open(fjson)); inp = outdir + "/in_F.json"
json.dump({"files": [{"path": k, "css": v} for k, v in F.items()]}, open(inp, "w"))
full = outdir + "/all_raw.json"; allm = os.path.dirname(fjson) + "/all_markers.json"
if not os.path.exists(allm):
    r = subprocess.run(["node", B + "/tools/transform.mjs", full], input=open(inp).read(), capture_output=True, text=True)
    if r.returncode: raise SystemExit(r.stderr)
    json.dump(json.load(open(full))["markers"], open(allm, "w"))
    print(r.stderr.strip())
allmk = json.load(open(allm))
tid = sorted(int(k) for k, m in allmk.items() if fsub in m["file"])
if ids != "ALL": sel = set(int(x) for x in open(ids).read().replace(",", " ").split()); tid = [i for i in tid if i in sel]
idf = outdir + "/ids.txt"; open(idf, "w").write(" ".join(map(str, tid)))
out = outdir + "/raw.json"
r = subprocess.run(["node", B + "/tools/transform.mjs", out, idf], input=open(inp).read(), capture_output=True, text=True)
if r.returncode: raise SystemExit(r.stderr)
d = json.load(open(out))
json.dump({f["path"]: f["css"] for f in d["files"]}, open(outdir + "/B_css.json", "w"))
json.dump(d["markers"], open(outdir + "/markers.json", "w"))
print("applied", len(d["markers"]), "of target ids", len(tid))
import shutil; shutil.copy(fjson, outdir + "/F_css.json")
