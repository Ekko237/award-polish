# award-polish

**一个打磨网站、网页应用和 App 界面的 agent 技能：拿 Awwwards 获奖站当标杆，评审分数靠得住。**

技能本身就是 Markdown 文档加 Python 脚本，能读文件、能跑命令的编程 agent 都能用；Claude Code 和 Codex 可以直接当技能装。

[English](README.md)

## 用它打磨过的作品

![用 award-polish 打磨过的六个作品，电脑版和手机版](media/showcase-zh-v2.png)

- [Island Evolution](https://islandevolution.com/)：像素解谜游戏的官网，最值得看的是往下滚动时一步步演示一局游戏的那一段。
- [今食喵 Today's Mealow](https://mealow.app/)：让小猫从附近真实的店里帮你挑吃什么的网页应用。
- [Milo](https://devpost.com/software/milo-shopping-that-understands-older-adults)：黑客松上四人队做的作品，老人开口就能用的平板端，加上子女用的手机端。
- [SONIFIZZ 声汽海报机](https://ekko237.github.io/sonifizz-poster/)（[源码](https://github.com/Ekko237/sonifizz-poster)）：音乐节展位上的竖屏触摸机原型，一分钟印出一张自己的海报。
- [顺路侠](https://ekko237.github.io/shunluxia-campus-errand/?lang=zh)（[源码](https://github.com/Ekko237/shunluxia-campus-errand)）：校园跑腿互助 App 原型。
- [三角洲国际服改枪码](https://dfgqm.com/)：游戏改枪码站，做了两轮改版。

同一份需求，大家做出来的功能差不多，一个产品能不能拉开差距，靠的是视觉、交互、动效和流畅度。光靠 AI 自己打磨很难做好：它给自己打分偏松，小修小补会卡住，「做得更好」也没有终点。这个技能把打磨变成一个有尺子的循环。

能在浏览器里打开的界面都适用，网站、网页应用、触屏原型、平板和手机上的 App 界面都行，因为检查脚本靠无头浏览器来跑。

Awwwards 只是我们对照的标杆，上面这些作品还没有一个拿过 Awwwards 奖。

循环怎么走：

- **先看标杆**：实际打开 6-8 个近期同类的 Awwwards / Webby / FWA 获奖站，记下能借的手法。
- **按批推进**：评审一次给出完整问题清单，AI 一口气改完，一条改动一个提交，再请下一次评审。
- **评审靠得住**：每次开两个没参与开发的新评审；用一份固定的定标卷抵消评审偏严或偏松；这一批算不算数，看它和目前最好版本的逐项盲比。10 项打分的尺子拿 5 个真实的 Site of the Day 和 1 个模板站校准过：10 分 = 顶尖 SOTD，9 分 = 一般 SOTD，8 分 = Honorable Mention。
- **最后由你拍板**：定期把前后对比图发给你，因为 AI 评审会集体看走眼；你挑中的版本就是基准，评审分再高也不推翻。
- **刹车写全**：截止时间、卡住、没进展、来回摆，各有处理办法。
- **黑客松和多人协作**：标准不降，设计挪到开赛前做，打磨跟着团队的检查点。

![终端里的循环：在演示站上一批改动前后的布局体检，再由盲比定出新的最好版本](media/loop.gif)

## 一分钟试一个工具

布局体检脚本对任何网站都能用，不用先装技能：

```bash
git clone https://github.com/Ekko237/award-polish && cd award-polish
pip install playwright pillow && playwright install chromium
python3 skills/award-polish/scripts/layout_check.py https://你的网站 --out check --keep "main=.你的主按钮"
```

会得到 375、768、1024、1280、1440 五档宽度的截图和 `check/report.json`：横向溢出、被裁掉的描边和阴影、被截断的文字、超过两行的标题、控制台报错、坏图、小于 44px 的点击区、实际显示小于 12px 的字，还有主按钮在不在第一屏、有没有被横幅盖住。

## 安装

**Claude Code（插件）**：

```
/plugin install award-polish --marketplace Ekko237/award-polish
```

旧版本先 `/plugin marketplace add Ekko237/award-polish`，再 `/plugin install award-polish@award-polish`。

**任何 agent（普通技能文件夹）**：

```bash
bash install.sh                   # 自动装到已有的 ~/.claude/skills 和/或 ~/.codex/skills
bash install.sh claude            # 只装 Claude Code
bash install.sh codex             # 只装 Codex
bash install.sh /你的/skills/目录   # 别的 agent：装到它读取技能的那个文件夹
```

Windows 可以手动把 `skills/award-polish` 复制到 `%USERPROFILE%\.claude\skills\award-polish` 或 `%USERPROFILE%\.codex\skills\award-polish`。Git Bash 安装了 `rsync` 后也能运行 `install.sh`。

没有技能文件夹的 agent，直接让它读 `skills/award-polish/SKILL.md` 就行。装好后，说「把这个网站打磨到获奖水平」或者「用 award-polish 技能」；支持斜杠命令的 agent 也可以用 `/award-polish`。技能正文是英文写的，AI 跟你说话照样用你的语言。

## 里面有什么

- `skills/award-polish/SKILL.md`：循环本身（目标、过程、检查迭代）、收工条件和红线。
- `skills/award-polish/references/`：新站和改版两种模式、怎么看获奖站、打分的尺子、怎么开评审、打磨清单、上线、黑客松，以及从真实项目里攒下的经验。
- `skills/award-polish/scripts/`（用法见 `skills/award-polish/references/scripts.md`），都在真实网站上跑过：
  - `layout_check.py`：多宽度截图和布局检查、首屏关键元素、操作后的状态。
  - `record_moment.py`：用虚拟时钟逐格录动效，评审看静态图也能打动效分。
  - `sound_levels.py`：逐步记录音量电平，给在无头浏览器里听不到声音的评审看。
  - `review_prompt.py`：生成盲评提示词，截图换成看不出版本的目录名。
  - `calibrate.py`：定标卷校正、取平均、Awwwards 加权分，并按盲比定结论。
  - `side_by_side.py`：从网址或图片拼出带标签的前后对比图。
  - `seo_keep.py`：对照改版前后的标题、描述、规范链接和结构化数据，改版不丢搜索字段。
  - `wait_live.py`：等线上页面和它引用的样式、脚本真的换成新版本。
  - `asset_check.py`：不开浏览器，查全站每个页面引用的本地文件在不在。
  - `snapshot.py`：给评审的快照只从提交导出，没提交的文件不会变成 404。
  - `split_commits.py`：工作区攒了几件改动时，按关键词拆成一件一个提交。
- `skills/award-polish/templates/`：任务说明、迭代日志、评审提示词和评审配置。

## 需要什么

Python 3、Playwright 和 Chromium、Pillow；`asset_check.py` 还要 beautifulsoup4 和 tinycss2，`seo_keep.py` 要 requests 和 beautifulsoup4。可选：一个前端设计规则技能（比如 design-taste-frontend），以及一个生图工具，画面优先用生成图。

## 许可

MIT
