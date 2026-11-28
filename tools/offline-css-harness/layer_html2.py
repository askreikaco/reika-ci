"""L2: layer order wp, plugins, bricks, theme-base, bricks-post. post-N + Bricks inline element blocks -> bricks-post; core/plugins as in L. Theme unlayered except @layer theme-base{} blocks in theme css."""
import re, html as H
from layer_html import cls_href, LINK_RE, STYLE_RE
DECL2 = '<style id="ics-layers-decl">@layer wp, plugins, bricks, theme-base, bricks-post;</style>'
def layer_owner2(t, inline=True):
    def fl(m):
        tag = m.group(0)
        if not re.search(r'rel\s*=\s*["\']stylesheet', tag, re.I): return tag
        h = re.search(r'href\s*=\s*["\']([^"\']+)', tag)
        if not h: return tag
        href = H.unescape(h.group(1)); layer = cls_href(href)
        if layer in (None, 'theme'): return tag
        if '/uploads/bricks/css/post-' in href: layer = 'bricks-post'
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
            if 'bricks' in i: layer = 'bricks-post'
            elif i.startswith('wp-') or 'wp-' in i: layer = 'wp'
            else: return m.group(0)
            return f'<style{attrs}>@layer {layer}{{{body}}}</style>'
        t = STYLE_RE.sub(fs, t)
    t = re.sub(r'<head\b([^>]*)>', lambda m: f'<head{m.group(1)}>{DECL2}', t, count=1, flags=re.I)
    return t
