import argparse
import time
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from playwright.sync_api import sync_playwright


def main():
    ap = argparse.ArgumentParser(description='用一个浏览器页面等待线上 HTML、样式表及脚本满足新版字符串条件。')
    ap.add_argument('url')
    ap.add_argument('--has', nargs='+', default=[])
    ap.add_argument('--gone', nargs='+', default=[])
    ap.add_argument('--timeout', type=float, default=1500)
    ap.add_argument('--every', type=float, default=15)
    ap.add_argument('--settle', type=int, default=800)
    a = ap.parse_args()
    if not a.has and not a.gone:
        ap.error('请提供 --has 或 --gone')
    if a.timeout < 0 or a.every <= 0 or a.settle < 0:
        ap.error('timeout、settle 不能为负数，every 必须大于 0')
    parts = urlsplit(a.url)
    query = [(key, value) for key, value in parse_qsl(parts.query, keep_blank_values=True) if key != 'v']
    start = time.monotonic()
    deadline = start + a.timeout
    missing, present = list(a.has), list(a.gone)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        round_number = 0
        while True:
            round_number += 1
            url = urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query + [('v', str(round_number))]), parts.fragment))
            page.goto(url, wait_until='load')
            page.wait_for_timeout(a.settle)
            documents = [(page.url, page.content())]
            urls = page.evaluate("""() => [...new Set([
                ...[...document.styleSheets].map(s => s.href),
                ...[...document.scripts].map(s => s.src)
            ].filter(Boolean))]""")
            for resource_url in urls:
                response = page.request.get(resource_url)
                if not response.ok:
                    raise RuntimeError(f'资源请求失败：{response.status} {resource_url}')
                documents.append((resource_url, response.text()))
                response.dispose()
            found = {needle: [path for path, body in documents if needle in body] for needle in a.has}
            missing = [needle for needle, paths in found.items() if not paths]
            present = [needle for needle in a.gone if any(needle in body for _, body in documents)]
            elapsed = time.monotonic() - start
            if not missing and not present:
                print(f'已经是新版本：第 {round_number} 轮，等了 {elapsed:.1f} 秒')
                for needle, paths in found.items():
                    print(f"  {needle}: {', '.join(paths)}")
                browser.close()
                return 0
            print(f'第 {round_number} 轮，等了 {elapsed:.1f} 秒，缺少：{missing}，仍然存在：{present}', flush=True)
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            # 在截止时直接报告，避免超时后再发一整轮网络请求。
            time.sleep(min(a.every, remaining))
            if time.monotonic() >= deadline:
                break
        browser.close()
    print(f'等待超时，等了 {time.monotonic() - start:.1f} 秒，还差：缺少 {missing}；仍然存在 {present}')
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
