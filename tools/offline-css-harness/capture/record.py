import asyncio, sys, os, re, hashlib, json
from playwright.async_api import async_playwright
BASE = "https://ics2.reika.sg"
OUT = os.environ.get("HARNESS_ROOT", "/tmp/claude-0/-home-user/cc5a650a-0655-55a3-841b-dd3395e06354/scratchpad") + "/bulk2/har"
W = int(sys.argv[1]) if len(sys.argv) > 1 else 1440
pages = [l.strip() for l in open(os.path.join(os.path.dirname(OUT), "pages.txt")) if l.strip()]
def slug(u):
    p = u.replace(BASE, "") or "/"
    return (re.sub(r"[^a-zA-Z0-9]+", "_", p).strip("_") or "home")[:120] + "_" + hashlib.md5(u.encode()).hexdigest()[:6]
async def rec(b, u, sem, log):
    async with sem:
        har = os.path.join(OUT, f"{slug(u)}_{W}.har")
        if os.path.exists(har) and os.path.getsize(har) > 1000:
            log.append({"url": u, "skip": True}); return
        ctx = await b.new_context(viewport={"width": W, "height": 900}, device_scale_factor=1, record_har_path=None)
        await ctx.route_from_har(har, update=True, update_content="embed", update_mode="full")
        pg = await ctx.new_page()
        status = None
        try:
            r = await pg.goto(u, wait_until="load", timeout=60000)
            status = r.status if r else None
            await pg.wait_for_timeout(500)
            h = await pg.evaluate("document.body.scrollHeight")
            y = 0
            while y < h:
                await pg.evaluate(f"window.scrollTo(0,{y})"); await pg.wait_for_timeout(120); y += 500
            await pg.evaluate("window.scrollTo(0,0)")
            await pg.wait_for_timeout(800)
        except Exception as e:
            log.append({"url": u, "err": str(e)[:200]})
        await ctx.close()
        log.append({"url": u, "status": status, "har": os.path.basename(har)})
async def main():
    sem = asyncio.Semaphore(2); log = []
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path="/usr/bin/google-chrome", args=["--no-sandbox"])
        async def guarded(u):
            try: await asyncio.wait_for(rec(b, u, sem, log), timeout=180)
            except Exception as e: log.append({'url': u, 'err': 'timeout/' + type(e).__name__})
        await asyncio.gather(*(guarded(u) for u in pages))
        await b.close()
    json.dump(log, open(os.path.join(os.path.dirname(OUT), f"record-{W}.json"), "w"), indent=1)
    print("done", len(log), "errors", sum(1 for x in log if "err" in x))
asyncio.run(main())
