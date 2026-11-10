import argparse
import json
from pathlib import Path

from playwright.sync_api import sync_playwright

# 给评审的声音材料：评审在无头浏览器里听不到声音，只看截图会判「没有声音反馈」。
# 这个脚本在测试页里给 WebAudio 的输出接一个电平探头（只注入测试浏览器，不改网站代码），
# 按步骤文件逐步操作，每一步记下这段时间里的最大电平（0 是没声音，1 是满幅）；<audio>/<video> 播放了哪个文件也记下来。
# 步骤文件是 JSON 数组，每项一个动作加 label，可选 listen（这一步之后听多少毫秒，默认 700）：
#   {"label": "点开始", "click": "#start"} / {"fill": "#name", "value": "Kiki"} / {"press": "Enter"}
#   {"js": "localStorage.setItem('mute','1')"} / {"wait_for": "#result"}（等元素出现，不计电平）/ {"wait": 500}
# 用法：python3 sound_levels.py <网址> --steps steps.json --out levels.json [--phone] [--fake-mic]
PROBE = """
(() => {
  const orig = AudioNode.prototype.connect;
  window.__peak = 0; window.__media = [];
  AudioNode.prototype.connect = function (dest, ...rest) {
    const r = orig.call(this, dest, ...rest);
    if (dest instanceof AudioDestinationNode && !this.__probed) {
      this.__probed = true;
      const an = this.context.createAnalyser(), mute = this.context.createGain();
      an.fftSize = 2048; mute.gain.value = 0;
      orig.call(this, an); orig.call(an, mute); orig.call(mute, this.context.destination);
      const buf = new Float32Array(an.fftSize);
      setInterval(() => { an.getFloatTimeDomainData(buf); for (const v of buf) window.__peak = Math.max(window.__peak, Math.abs(v)); }, 15);
    }
    return r;
  };
  const play = HTMLMediaElement.prototype.play;
  HTMLMediaElement.prototype.play = function () { window.__media.push(this.currentSrc || this.src); return play.call(this); };
})();
"""


def act(page, step):
    if 'click' in step:
        page.locator(step['click']).filter(visible=True).first.click()
    elif 'fill' in step:
        page.locator(step['fill']).filter(visible=True).first.fill(step['value'])
    elif 'press' in step:
        page.keyboard.press(step['press'])
    elif 'js' in step:
        page.evaluate(step['js'])
    elif 'wait' in step:
        page.wait_for_timeout(step['wait'])
    else:
        raise ValueError(f'未知步骤：{step}')


def main():
    ap = argparse.ArgumentParser(description='按步骤操作页面，记录每一步的最大音量电平和媒体播放。')
    ap.add_argument('url')
    ap.add_argument('--steps', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--phone', action='store_true', help='用 390×844 的手机视口')
    ap.add_argument('--fake-mic', action='store_true', help='浏览器用假麦克风并自动授权（测「对着麦克风说话」这类功能）')
    ap.add_argument('--settle', type=int, default=1000)
    a = ap.parse_args()
    steps = json.loads(Path(a.steps).read_text(encoding='utf-8'))
    args = ['--autoplay-policy=no-user-gesture-required']
    if a.fake_mic:
        args += ['--use-fake-device-for-media-stream', '--use-fake-ui-for-media-stream']
    rows, errors = [], []
    with sync_playwright() as p:
        browser = p.chromium.launch(args=args)
        view = dict(viewport={'width': 390, 'height': 844}, is_mobile=True, has_touch=True) if a.phone else dict(viewport={'width': 1440, 'height': 900})
        ctx = browser.new_context(**view)
        if a.fake_mic:
            ctx.grant_permissions(['microphone'], origin='/'.join(a.url.split('/')[:3]))
        page = ctx.new_page()
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.on('console', lambda m: errors.append(m.text) if m.type == 'error' else None)
        page.add_init_script(PROBE)
        page.goto(a.url, wait_until='load')
        page.wait_for_timeout(a.settle)
        for step in steps:
            if 'wait_for' in step:
                page.wait_for_selector(step['wait_for'], timeout=step.get('timeout', 20000))
                continue
            page.evaluate('window.__peak = 0; window.__media = []')
            act(page, step)
            page.wait_for_timeout(step.get('listen', 700))
            peak, media = page.evaluate('[window.__peak, window.__media]')
            row = {'label': step.get('label') or json.dumps(step, ensure_ascii=False), 'peak': round(peak, 3), 'media': media}
            rows.append(row)
            print(f"{row['label']}: 电平 {row['peak']:.3f}" + (f"  媒体 {', '.join(media)}" if media else ''))
        browser.close()
    Path(a.out).write_text(json.dumps({'url': a.url, 'steps': rows, 'errors': errors}, ensure_ascii=False, indent=2), encoding='utf-8')
    silent = [r['label'] for r in rows if r['peak'] < 0.01 and not r['media']]
    print('没出声的步骤：' + ('、'.join(silent) if silent else '无'))
    print('errors:', errors)


if __name__ == '__main__':
    main()
