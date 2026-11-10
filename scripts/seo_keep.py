import argparse
import json
from pathlib import Path
import xml.etree.ElementTree as ET
from urllib.parse import urljoin, urlsplit, urlunsplit

import requests
from bs4 import BeautifulSoup


def html_fields(content):
    soup = BeautifulSoup(content, 'html.parser')
    def text(selector):
        el = soup.select_one(selector)
        return el.get_text(' ', strip=True) if el else None
    def attr(selector, key):
        el = soup.select_one(selector)
        return el.get(key) if el else None
    types = []
    def visit(value):
        if isinstance(value, list):
            for item in value:
                visit(item)
        elif isinstance(value, dict):
            kind = value.get('@type', [])
            types.extend(kind if isinstance(kind, list) else [kind])
            for key, item in value.items():
                if key != '@type':
                    visit(item)
    for script in soup.select('script[type="application/ld+json"]'):
        visit(json.loads(script.string if script.string is not None else script.get_text()))
    fields = {'title': text('title'),
              'description': attr('meta[name="description"]', 'content'),
              'canonical': attr('link[rel="canonical"]', 'href'),
              'hreflang': sorted(f"{el.get('hreflang')}={el.get('href')}" for el in soup.select('link[hreflang]')),
              'robots': attr('meta[name="robots"]', 'content'),
              'jsonld_types': sorted(types), 'h1': text('h1'), 'lang': attr('html', 'lang')}
    for prop in ('og:title', 'og:description', 'og:image'):
        fields[prop] = attr(f'meta[property="{prop}"]', 'content')
    fields['twitter:card'] = attr('meta[name="twitter:card"],meta[property="twitter:card"]', 'content')
    return fields


def page_fields(response):
    return {'status': response.status_code, **html_fields(response.content)}


def sitemap_paths(session, url, count):
    response = session.get(url, timeout=30)
    response.raise_for_status()
    root = ET.fromstring(response.content)
    local = root.tag.rsplit('}', 1)[-1]
    paths = []
    for node in root:
        loc = next((child.text for child in node if child.tag.rsplit('}', 1)[-1] == 'loc'), None)
        if loc is None:
            continue
        if local == 'sitemapindex':
            paths.extend(sitemap_paths(session, urljoin(url, loc), count - len(paths)))
        else:
            parts = urlsplit(loc)
            paths.append(urlunsplit(('', '', parts.path or '/', parts.query, '')))
        if len(paths) >= count:
            break
    return paths[:count]


def main():
    ap = argparse.ArgumentParser(description='比对线上与新版页面的 SEO 字段及指定文件，任何差异退出码为 1。')
    ap.add_argument('--base', required=True)
    ap.add_argument('--new', required=True)
    ap.add_argument('--pages', nargs='+', default=[])
    ap.add_argument('--sitemap', type=int)
    ap.add_argument('--files', nargs='+', default=[])
    ap.add_argument('--dump', help='把 base 每页的字段原文存成这个 JSON 文件，当作搜索基线写进日志')
    a = ap.parse_args()
    if not a.pages and not a.sitemap:
        ap.error('请提供 --pages 和/或 --sitemap 正整数')
    if a.sitemap is not None and a.sitemap <= 0:
        ap.error('--sitemap 需要正整数')
    differences = 0
    baseline = {}
    with requests.Session() as session:
        pages = list(dict.fromkeys(a.pages + (sitemap_paths(session, urljoin(a.base, '/sitemap.xml'), a.sitemap) if a.sitemap else [])))
        for path in pages:
            before = page_fields(session.get(urljoin(a.base.rstrip('/') + '/', path), timeout=30))
            after = page_fields(session.get(urljoin(a.new.rstrip('/') + '/', path), timeout=30))
            baseline[path] = before
            changed = [key for key in before if before[key] != after[key]]
            differences += len(changed)
            print(f"{'DIFF' if changed else 'OK'} {path}")
            for key in changed:
                print(f'  {key}: base={json.dumps(before[key], ensure_ascii=False)} new={json.dumps(after[key], ensure_ascii=False)}')
        for path in a.files:
            before = session.get(urljoin(a.base, path), timeout=30)
            after = session.get(urljoin(a.new, path), timeout=30)
            before.raise_for_status()
            after.raise_for_status()
            changed = before.content != after.content
            differences += int(changed)
            print(f"{'DIFF' if changed else 'OK'} 文件 {path}")
            if changed:
                print(f'  bytes: base={before.content!r} new={after.content!r}')
    if a.dump:
        Path(a.dump).write_text(json.dumps(baseline, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        for path, fields in baseline.items():
            print(f'基线 {path}：' + '；'.join(f'{k}={json.dumps(v, ensure_ascii=False)}' for k, v in fields.items()))
        print(f'搜索基线已存：{a.dump}')
    print(f'{len(pages)} 页，{differences} 处不同')
    return int(differences > 0)


if __name__ == '__main__':
    raise SystemExit(main())
