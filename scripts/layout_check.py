import argparse
import json
import os
import re
from playwright.sync_api import sync_playwright

JS = r"""
() => {
  const vw = document.documentElement.clientWidth;
  const out = {overflowX: document.documentElement.scrollWidth > vw + 1,
               scrollWidth: document.documentElement.scrollWidth, viewport: vw,
               offscreen: [], clipped: [], smallTargets: [], truncated: [], brokenImages: []};
  const label = el => {
    const t = (el.innerText || el.getAttribute('aria-label') || el.alt || '').trim().slice(0, 40);
    return el.tagName.toLowerCase() + (el.id ? '#' + el.id : '') +
      (el.className && typeof el.className === 'string' ? '.' + el.className.trim().split(/\s+/).slice(0,2).join('.') : '') +
      (t ? ' "' + t + '"' : '');
  };
  const visible = el => { const r = el.getBoundingClientRect(); const s = getComputedStyle(el);
    return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none' && +s.opacity > 0; };
  const all = [...document.querySelectorAll('body *')].filter(visible);
  for (const el of all) {
    const r = el.getBoundingClientRect();
    let fixed = false;
    for (let q = el; q; q = q.parentElement) if (getComputedStyle(q).position === 'fixed') fixed = true;
    if (r.right > vw + 1 && !fixed) {
      // 跑马灯、轮播这类被祖先 overflow 裁掉的内容是有意藏在外面的，不算
      let clippedByAncestor = false, q = el.parentElement;
      while (q && q !== document.body) {
        const qs = getComputedStyle(q);
        if (qs.overflowX !== 'visible' || qs.overflow !== 'visible') { clippedByAncestor = true; break; }
        q = q.parentElement;
      }
      if (!clippedByAncestor) out.offscreen.push({el: label(el), right: Math.round(r.right)});
    }
    const s = getComputedStyle(el);
    // 描边、阴影外框
    let pad = 0;
    const sh = s.boxShadow; if (sh && sh !== 'none') {
      const nums = sh.match(/-?\d+(\.\d+)?px/g) || []; pad = Math.max(pad, nums.reduce((a, n) => a + Math.abs(parseFloat(n)), 0) / 2);
    }
    if (s.outlineStyle !== 'none') pad = Math.max(pad, parseFloat(s.outlineWidth) + parseFloat(s.outlineOffset || 0));
    if (pad > 0 || parseFloat(s.borderTopWidth) > 0) {
      let p = el.parentElement;
      while (p && p !== document.body) {
        const ps = getComputedStyle(p);
        if (ps.overflow !== 'visible' || ps.overflowX !== 'visible' || ps.overflowY !== 'visible') {
          const pr = p.getBoundingClientRect();
          const o = {l: r.left - pad, t: r.top - pad, r: r.right + pad, b: r.bottom + pad};
          if (o.l < pr.left - 0.5 || o.t < pr.top - 0.5 || o.r > pr.right + 0.5 || o.b > pr.bottom + 0.5) {
            // 滚动容器里的内容本来就会超出，只记离边很近、看起来像被切了一刀的
            const inScroller = /auto|scroll/.test(ps.overflow + ps.overflowX + ps.overflowY);
            if (!inScroller || pad > 0) out.clipped.push({el: label(el), by: label(p)});
          }
          break;
        }
        p = p.parentElement;
      }
    }
    const clickable = el.matches('a[href],button,input:not([type=hidden]),select,textarea,[role=button],[onclick],[tabindex]:not([tabindex="-1"])');
    if (vw < 768 && clickable && (r.width < 44 || r.height < 44)) out.smallTargets.push({el: label(el), w: Math.round(r.width), h: Math.round(r.height)});
    if ((s.overflow !== 'visible' || s.textOverflow === 'ellipsis') && el.scrollWidth > el.clientWidth + 1 && el.children.length === 0 && el.innerText)
      out.truncated.push({el: label(el)});
  }
  for (const img of document.images) if (img.complete && img.naturalWidth === 0 && visible(img)) out.brokenImages.push(img.currentSrc || img.src);
  for (const k of ['offscreen','clipped','smallTargets','truncated']) out[k] = out[k].slice(0, 40);
  return out;
}
"""

ANALYTICS = re.compile(r'google-analytics|googletagmanager|/g/collect|/ga/|doubleclick|segment\.io|hotjar|plausible|clarity\.ms|facebook\.net', re.I)

KEEP_HEADINGS = r"""
({keep, maxLines}) => {
  const vw = document.documentElement.clientWidth, vh = document.documentElement.clientHeight;
  const visible = el => {
    const r = el.getBoundingClientRect();
    return r.width > 0 && r.height > 0 && el.checkVisibility({checkOpacity: true, checkVisibilityCSS: true});
  };
  const label = el => el.tagName.toLowerCase() + (el.id ? '#' + el.id : '') +
    (typeof el.className === 'string' && el.className.trim() ? '.' + el.className.trim().split(/\s+/).slice(0,2).join('.') : '');
  const headings = [...document.querySelectorAll('h1,h2')].filter(visible).map(el => {
    const range = document.createRange(); range.selectNodeContents(el);
    const tops = [];
    for (const r of range.getClientRects()) if (r.width && r.height && !tops.some(t => Math.abs(t-r.top) < 2)) tops.push(r.top);
    return {tag: el.tagName.toLowerCase(), text: el.innerText.trim().slice(0,40), lines: tops.length};
  });
  const results = keep.map(({name, selector}) => {
    const el = [...document.querySelectorAll(selector)].find(visible);
    if (!el) return {name, selector, top: null, bottom: null, height: vh, keepMissing: true, notInFirstScreen: false, keepCovered: []};
    const r = el.getBoundingClientRect();
    const points = [[r.x+r.width/2,r.y+r.height/2],[r.left+1,r.top+1],[r.right-1,r.top+1],[r.left+1,r.bottom-1],[r.right-1,r.bottom-1]];
    const covered = [];
    for (const [x,y] of points) {
      if (x < 0 || x >= vw || y < 0 || y >= vh) continue;
      const hit = document.elementFromPoint(x,y);
      // 点到元素自己的祖先说明这个角是圆角外的空白，不算被盖住
      if (hit && hit !== el && !el.contains(hit) && !hit.contains(el) && !covered.some(c => c.by === label(hit))) covered.push({by: label(hit), x, y});
    }
    return {name, selector, top: r.top, bottom: r.bottom, height: vh,
      keepMissing: false, notInFirstScreen: r.bottom > vh || r.top < 0, keepCovered: covered};
  });
  return {headings, keep: results, h1TooManyLines: maxLines > 0 ? headings.filter(h => h.tag === 'h1' && h.lines > maxLines) : []};
}
"""


def context_options(width, height=900, phone_height=812):
    mobile = width < 768
    return dict(viewport={'width': width, 'height': phone_height if mobile else height},
                device_scale_factor=2 if mobile else 1, is_mobile=mobile, has_touch=mobile)


def execute_step(page, step):
    if 'click' in step:
        page.locator(step['click']).filter(visible=True).first.click()
    elif 'hover' in step:
        page.locator(step['hover']).filter(visible=True).first.hover()
    elif 'fill' in step:
        page.locator(step['fill']).filter(visible=True).first.fill(step['value'])
    elif 'press' in step:
        page.keyboard.press(step['press'])
    elif 'scroll' in step:
        page.mouse.wheel(0, step['scroll'])
    elif 'wait' in step:
        page.wait_for_timeout(step['wait'])
    else:
        raise ValueError(f'未知步骤：{step}')


def check_page(page, keep=None, max_h1_lines=2):
    result = page.evaluate(JS)
    result.update(page.evaluate(KEEP_HEADINGS, {'keep': keep or [], 'maxLines': max_h1_lines}))
    return result


def main():
    ap = argparse.ArgumentParser(description='多宽度整页及分屏截图，检查布局、关键元素首屏可见性、标题行数和操作后的状态。')
    ap.add_argument('urls', nargs='*')
    ap.add_argument('--widths', default='375,768,1024,1280,1440')
    ap.add_argument('--height', type=int, default=900)
    ap.add_argument('--phone-height', type=int, default=812)
    ap.add_argument('--settle', type=int, default=800)
    ap.add_argument('--out', default='check-out')
    ap.add_argument('--slices', type=int, default=0)
    ap.add_argument('--forbid', default='', help='禁用字符串，以逗号分隔')
    ap.add_argument('--keep', action='append', default=[], metavar='名字=选择器')
    ap.add_argument('--max-h1-lines', type=int, default=2)
    ap.add_argument('--states', help='状态数组 JSON，每项含名字、网址、步骤')
    a = ap.parse_args()
    widths = [int(x) for x in a.widths.split(',')]
    if not widths or min(widths) <= 0 or min(a.height, a.phone_height) <= 0 or min(a.settle, a.slices, a.max_h1_lines) < 0:
        ap.error('宽高必须大于 0，settle、slices、max-h1-lines 不能为负数')
    states = json.load(open(a.states, encoding='utf-8')) if a.states else []
    if not a.urls and not states:
        ap.error('请提供网址或 --states')
    keep = []
    for item in a.keep:
        if '=' not in item:
            ap.error('--keep 需要 名字=选择器')
        name, selector = item.split('=', 1)
        if not name or not selector:
            ap.error('--keep 的名字和选择器都不能为空')
        keep.append(dict(name=name, selector=selector))
    os.makedirs(a.out, exist_ok=True)
    report = []
    cases = [(url, None, []) for url in a.urls] + [(s['网址'], s['名字'], s['步骤']) for s in states]
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for w in widths:
            for index, (url, state, steps) in enumerate(cases, 1):
                ctx = browser.new_context(**context_options(w, a.height, a.phone_height))
                page = ctx.new_page()
                errors, failed = [], []
                page.on('console', lambda m: errors.append(m.text) if m.type == 'error' else None)
                page.on('pageerror', lambda e: errors.append(str(e)))
                def on_failed(request):
                    if request.resource_type in ('document', 'script', 'stylesheet', 'image', 'font', 'media') and not ANALYTICS.search(request.url):
                        failed.append(request.url)
                page.on('requestfailed', on_failed)
                page.goto(url, wait_until='load')
                page.wait_for_timeout(a.settle)
                for step in steps:
                    execute_step(page, step)
                r = check_page(page, keep, a.max_h1_lines)
                r['forbidden'] = [x for x in a.forbid.split(',') if x and x in page.inner_text('body')]
                slug = re.sub(r'[^a-zA-Z0-9]+', '-', url.split('://')[-1]).strip('-')[:60] or 'page'
                state_slug = re.sub(r'[^\w-]+', '-', state or '', flags=re.UNICODE)
                slug += f'-{index}' + (f'-{state_slug}' if state else '')
                shot = os.path.join(a.out, f'{slug}-{w}.png')
                page.screenshot(path=shot, full_page=True)
                if a.slices:
                    height = page.viewport_size['height']
                    total = page.evaluate('document.documentElement.scrollHeight')
                    for i in range(min(a.slices, -(-total // height))):
                        page.evaluate('(y) => window.scrollTo(0,y)', i * height)
                        page.wait_for_timeout(a.settle)
                        page.screenshot(path=os.path.join(a.out, f'{slug}-{w}-screen{i+1:02d}.png'))
                r.update(url=url, width=w, state=state, screenshot=shot, consoleErrors=errors[:20], failedRequests=failed[:20])
                r['pass'] = not any(r[k] for k in ('overflowX','offscreen','clipped','truncated','brokenImages','forbidden','consoleErrors','failedRequests','h1TooManyLines')) and not any(k['keepMissing'] or k['notInFirstScreen'] or k['keepCovered'] for k in r['keep'])
                report.append(r)
                ctx.close()
        browser.close()
    path = os.path.join(a.out, 'report.json')
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    for r in report:
        flags = [k for k in ('overflowX','offscreen','clipped','smallTargets','truncated','brokenImages','forbidden','consoleErrors','failedRequests','h1TooManyLines') if r.get(k)]
        flags += [k for k in ('keepMissing','notInFirstScreen','keepCovered') if any(x[k] for x in r['keep'])]
        print(f"{'PASS' if r['pass'] else 'FAIL'} {r['width']:>5} {r['url']} 状态：{r['state']} {' '.join(flags)}")
    if keep:
        print('\n关键元素首屏位置')
        print('宽度 | 网址 / 状态 | 元素 | y 范围 | 屏高 | 结果')
        for r in report:
            for k in r['keep']:
                bounds = '未找到' if k['keepMissing'] else f"{k['top']:.1f} 至 {k['bottom']:.1f}"
                status = ', '.join(key for key in ('keepMissing','notInFirstScreen','keepCovered') if k[key]) or 'OK'
                print(f"{r['width']} | {r['url']} / {r['state']} | {k['name']} | {bounds} | {k['height']} | {status}")
                for cover in k['keepCovered']:
                    print(f"  遮挡元素：{cover['by']}")
    print('report:', path)


if __name__ == '__main__':
    main()

