# 脚本用法

`S=<技能目录>/scripts`（`<技能目录>` 见 SKILL.md「脚本放在哪」）。都用 Python Playwright 起无头浏览器；8GB 内存的机器一次只跑一个。

**步骤文件**（layout_check 的状态、record_moment、sound_levels 共用）：JSON 数组，每项一个动作：
`{"click": 选择器}`、`{"hover": 选择器}`、`{"fill": 选择器, "value": 文字}`、`{"press": "Enter"}`、`{"scroll": 像素}`、`{"js": 代码}`、`{"wait": 毫秒}`、`{"wait_for": 选择器}`。点的是第一个看得见的匹配元素。

## 布局体检 layout_check.py

```
python3 $S/layout_check.py <url...> --widths 375,768,1024,1280,1440 --out <目录> [--keep 名字=选择器] [--states states.json] [--slices 8] [--forbid "—,-"] [--clock 2026-11-09T12:30]
```

- 每档宽度截整页，查横向溢出、超出视口、被裁的描边阴影、文字截断、h1 超过 2 行、控制台报错、坏图和加载失败（统计广告请求不算），出 `report.json`。
- `--keep`：量首屏关键元素，不在第一屏、被横幅浮层盖住都算不过，最后打印各宽度的 y 值表。不同页面的关键元素不同就分开跑。笔记本屏幕加 `--widths 1536 --height 864`、`--widths 1280 --height 800`。
- `--states`：操作后的状态。每项 `{"名字", "网址", "步骤"}`，每档宽度点过去再查。
- `--slices 8`：一屏一张，给评审和定标卷用。`--forbid`：页面上不许出现的字。`--clock`：固定时钟，问候语、营业状态随钟点变的页面每次结果一致。
- 只报告、不算不过的三栏：`smallTargets`（点击区不到 44px，含绝对定位的 `::before`、`::after`，只在手机宽度查）、`smallVisible`（看得见的大小不到 44px、点击区够）、`smallText`（按祖先缩放算的实际字号低于 12px）。整块缩放的画面里这三栏都算不过。
- `clipped` 每条带 `over`（越界几像素）和 `kind`：`shadow` 是只有描边阴影越界，几像素以内一般看不出；`box` 是元素本身越界，有意放大裁切的图片也在这类。祖先透明度为 0 的元素和 1px 的读屏文字不查。
- 报出来的每条都核对，归成误报的写一句理由。放在外框里左右滑动的整块界面只在它的设计宽度上查。

## 全站资源 asset_check.py

`python3 $S/asset_check.py <网站目录> [--skip 子目录]`：不开浏览器，查每个 HTML 和 CSS 引用的本地文件（src、srcset、href、poster、url()）是否都在磁盘上，缺一个退出码 1。体检只覆盖打开过的页面，这个几秒查完全站。

## 评审快照 snapshot.py

`python3 $S/snapshot.py <仓库> <网站目录> <快照目录> [--ref HEAD] [--link 快照内路径=实际路径] [--skip 子目录]`：只从提交导出（git archive），网站目录下有没提交的文件就拒绝，导出后自动跑 asset_check。不进仓库的大文件用 `--link` 软链接进去。要构建的项目改在干净的检出上构建。

## 招牌时刻逐格图 record_moment.py

`python3 $S/record_moment.py <url> --steps steps.json --out <目录> --every 40 [--phone]`：要录的那一步加 `"frames": 800`（录多少毫秒），可加 `"名字"`。用虚拟时钟推进 JS 和 CSS 动画，机器忙也不漏帧。出 `contact-NN.png`（每格标毫秒）、`animations.json`（时长、缓动、延迟，含 View Transition 伪元素）、`motion.json`（画面从第几毫秒动到第几毫秒）。最后一格还在动会提醒 frames 不够。

## 声音电平 sound_levels.py

`python3 $S/sound_levels.py <url> --steps steps.json --out levels.json [--phone] [--fake-mic]`：给 WebAudio 输出接探头（只注入测试浏览器），每步记最大电平（0 无声、1 满幅）和播放的媒体文件。步骤可加 `"label"`、`"listen"`（听多少毫秒，默认 700）；`wait`、`wait_for` 只等待不计电平。浏览器第一下点击才建音频，先加一步热身点击。`--fake-mic` 用测试音当麦克风并自动授权。

## 评审提示词 review_prompt.py

```
python3 $S/review_prompt.py --config <review.json> --anchor-shots <定标卷截图> --current <这一版截图> --round <.work/rN> [--best <最好版本截图>] [--live-best <最好版本地址>]
```

把几组截图复制进轮次目录、换成看不出来源的目录名，给每位评审随机定甲乙、丙丁，写出 `prompt-r1.md`、`prompt-r2.md` 和对照表 `blind.json`。配置从 `templates/review.json` 复制，模板是 `templates/REVIEW_PROMPT.md`，改评审规则只改模板。

## 算分 calibrate.py

```
python3 $S/calibrate.py --round <.work/rN> --anchor <anchor.json> --model "<模型 档位>" [--best <best.json>] [--save <best.json>] [--live-anchor]
```

按 blind.json 认出定标卷，逐项校正（默认最多 ±1，只有截图时动效、微互动、好用程度、留存吸引力不校正，`--live-anchor` 才校正）、取平均，按丙丁盲比定结论，最后一行直接贴进日志。结论是新的最好版本时 `--save` 才写 best.json。**一轮之内算法不换**：开工时把它复制进项目工作目录，这一轮都用那份。

## 前后对比 side_by_side.py

```
python3 $S/side_by_side.py --urls "改版前=<地址>" "新版=<地址>" [第三列] --pages / <关键页> --widths 1440,375 --out <目录> [--dismiss <横幅关闭按钮>] [--clock ...] [--full]
```

每列一个全新浏览器上下文，同页面同宽度截图再拼成带标签的对比图。地址可以带子路径（`http://localhost:8790/a/`）。只拼现成图片：`side_by_side.py 图1 图2 --labels 改动前,改动后 --out x.png`。

## 搜索字段 seo_keep.py

`python3 $S/seo_keep.py --base <线上> --new <本地> --pages <页面…> [--sitemap 前 N 页] [--files /robots.txt /sitemap.xml] [--dump refs/seo-baseline.json]`：逐页比标题、描述、规范链接、多语言链接、robots、结构化数据类型、H1、lang、分享卡片字段，有不同退出码 1。`--dump` 把 base 的字段原文存成搜索基线。

## 等上线 wait_live.py

`python3 $S/wait_live.py <网址> --has <这一版才有的字> [--gone <旧版的字>] [--timeout 1500]`：每轮带新的 `?v=` 打开页面，连同页面引用的样式和脚本一起查，CDN 继续发旧样式也查得出。

## 拆提交 split_commits.py

工作区攒了几件改动时用（正常做法是改完一条就提交）。拆法写成 JSON：

```
{"ctx": {"styles.css": 1},
 "items": [
   {"name": "hero", "msg": "提交说明", "hunks": {"src/site.js": ["关键词"], "pages/*/index.html": ["关键词"]}},
   {"name": "palette", "msg": "…", "files": ["assets/raw"]},
   {"name": "stamps", "msg": "…", "files": ["pages"], "only": "?v="}]}
```

- `hunks`：改动块的增删行里出现任一关键词就归这一件，路径带 `*` 按 glob 展开。`files`：整个文件或目录归这一件。
- `only`：暂存后每行增删都要含这个字样，混进别的改动就拒绝。资源指纹这类整站跟着变的放最后一件、用它把关。
- `ctx`：上下文行数，默认 3；几件改动只隔一两行时用 1，不许用 0（零上下文的块只暂存一部分时，git apply 会按过时的行号放错位置）。
- `python3 $S/split_commits.py <仓库> <拆法.json> plan` 列出没归属或归了两件的块，改关键词直到全部清楚；再 `run [--dry] [--items a,b] [--sign "Co-Authored-By: …"]` 逐件提交。关键词挑只属于这一件的字样，几件都用的类名会让一块归两件。
