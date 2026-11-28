"""usage: prep_fix.py <repo> <outdir> [strip_file_rel] : writes <outdir>/F_css.json (minified css of repo, url-keyed like A_css.json); with strip_file also runs transform on ALL rules to get markers for that file
"""
import json, subprocess, sys, os
from urllib.parse import urlsplit
S = os.environ.get("HARNESS_ROOT", "/tmp/claude-0/-home-user/cc5a650a-0655-55a3-841b-dd3395e06354/scratchpad"); B = S + "/bulk2"; L = S + "/layer"
repo, outdir = sys.argv[1], sys.argv[2]; os.makedirs(outdir, exist_ok=True)
A = json.load(open(L + "/variants/A_css.json"))
src = []
for url in A:
    rel = urlsplit(url).path.split('/themes/bricks-child/', 1)[1]
    rf = repo + "/themes/bricks-child/" + rel
    src.append({"path": url, "file": rf})
mini = subprocess.run(["node", B + "/tools/minify.mjs"], input=json.dumps({"files": src}), capture_output=True, text=True)
if mini.returncode: raise SystemExit(mini.stderr[:800])
F = {f["path"]: f["css"] for f in json.loads(mini.stdout)["files"]}
json.dump(F, open(outdir + "/F_css.json", "w"))
print("F files", len(F), "changed vs A:", sum(1 for k in F if F[k] != A[k]), [k.split('bricks-child/')[1].split('?')[0] for k in F if F[k] != A[k]])
