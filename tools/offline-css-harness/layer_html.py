"""HTML variants for the layer experiment. raw = HAR document (production-layered for links)."""
import re, html as H
from urllib.parse import urlsplit
DECL_PROD = '<style id="ics-layers-decl">@layer plugins, bricks;</style>'
LAYER_RE = re.compile(r'<style id="([^"]*?)-layered">@import url\("([^"]+)"\) layer\((\w+)\)( [^;]*)?;</style>')
LINK_RE = re.compile(r'<link\b[^>]*>', re.I)
STYLE_RE = re.compile(r'<style\b([^>]*)>(.*?)</style>', re.S | re.I)

def cls_href(u):
    p = urlsplit(u).path
    if '/themes/bricks-child/' in p: return 'theme'
    if '/uploads/bricks/css/post-' in p: return 'bricks'   # owner spec: uploads/bricks/css/* is Bricks
    if '/themes/bricks/' in p or '/uploads/bricks/' in p: return 'bricks'
    if '/plugins/' in p: return 'plugins'
    if '/wp-includes/' in p or '/wp-admin/' in p: return 'wp'
    return None

def unlayer(t):
    """Reverse production layering -> true unlayered source (variant A)."""
    n = t.count(DECL_PROD); t = t.replace(DECL_PROD, '')
    def f(m):
        idv, href, media = m.group(1), m.group(2).replace('&', '&amp;'), (m.group(4) or '').strip()
        ma = f' media="{media}"' if media else ''
        return f'<link rel="stylesheet" id="{idv}" href="{href}"{ma}>'
    t, k = LAYER_RE.subn(f, t)
    return t

def layer_owner(t, inline=True, post=True):
    """Variant L (owner spec) from an unlayered document. inline=False keeps Bricks/WP inline blocks unlayered."""
    def fl(m):
        tag = m.group(0)
        if not re.search(r'rel\s*=\s*["\']stylesheet', tag, re.I): return tag
        h = re.search(r'href\s*=\s*["\']([^"\']+)', tag)
        if not h: return tag
        href = H.unescape(h.group(1)); layer = cls_href(href)
        if layer in (None, 'theme'): return tag
        if not post and '/uploads/bricks/css/post-' in href: return tag
        media = re.search(r'media\s*=\s*["\']([^"\']*)', tag)
        med = media.group(1).strip() if media else ''
        med = '' if med in ('', 'all') else ' ' + med
        return f'<style>@import url("{href.replace(chr(34), "%22")}") layer({layer}){med};</style>'
    t = LINK_RE.sub(fl, t)
    if inline:
        def fs(m):
            attrs, body = m.group(1), m.group(2)
            if '@import' in body or 'ics-layers-decl' in attrs: return m.group(0)
            idm = re.search(r'\bid\s*=\s*["\']([^"\']*)', attrs); i = idm.group(1) if idm else ''
            if i.startswith('ics-') or not i: return m.group(0)
            if 'bricks' in i: layer = 'bricks'
            elif i.startswith('wp-') or 'wp-' in i: layer = 'wp'
            else: return m.group(0)
            return f'<style{attrs}>@layer {layer}{{{body}}}</style>'
        t = STYLE_RE.sub(fs, t)
    t = re.sub(r'<head\b([^>]*)>', lambda m: f'<head{m.group(1)}><style id="ics-layers-decl">@layer wp, plugins, bricks;</style>', t, count=1, flags=re.I)
    return t
