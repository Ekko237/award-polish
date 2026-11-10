import argparse
import json
import secrets
import shlex
import shutil
import sys
from pathlib import Path
from string import Template

DIMS = ['排版', '留白', '视觉层级', '色彩', '动效', '微互动', '响应式', '原创性', '好用程度', '留存吸引力']
STATIC = ['排版', '留白', '视觉层级', '色彩', '响应式', '原创性']
LISTS = ['页面', '参照', '招牌时刻', '故意留的问题', '不碰的样子', '操作说明']
STRINGS = ['产品', '地址', '场景口径', '机器限制']


def main():
    parser = argparse.ArgumentParser(description='生成盲评截图、评审提示词和对应关系。')
    parser.add_argument('--config', required=True)
    parser.add_argument('--anchor-shots', required=True)
    parser.add_argument('--current', required=True)
    parser.add_argument('--round', required=True)
    parser.add_argument('--best')
    parser.add_argument('--live-best')
    parser.add_argument('--reviewers', type=int, default=2)
    args = parser.parse_args()
    target = Path(args.round).resolve()
    if target.exists():
        sys.exit(f'轮次目录已存在，不能覆盖：{target}')
    if args.live_best and not args.best:
        sys.exit('--live-best 必须和 --best 一起使用')
    if args.reviewers < 2:
        sys.exit('评审人数至少为 2')
    with open(args.config, encoding='utf-8') as f:
        config = json.load(f)
    if not isinstance(config, dict):
        sys.exit(f'{args.config} 必须是 JSON 对象')
    for key in LISTS + STRINGS + ['每项各分数长什么样']:
        if key not in config:
            sys.exit(f'{args.config} 缺少「{key}」')
    for key in LISTS:
        if not isinstance(config[key], list) or any(not isinstance(x, str) for x in config[key]):
            sys.exit(f'{args.config} 的「{key}」必须是字符串列表')
    for key in STRINGS:
        if not isinstance(config[key], str):
            sys.exit(f'{args.config} 的「{key}」必须是字符串')
    if not isinstance(config.get('声音', []), list) or any(not isinstance(x, str) for x in config.get('声音', [])):
        sys.exit(f'{args.config} 的「声音」必须是字符串列表')
    rubric = config['每项各分数长什么样']
    if not isinstance(rubric, dict) or set(rubric) != set(DIMS):
        sys.exit(f'{args.config} 的「每项各分数长什么样」必须正好包含十项维度：' + '、'.join(DIMS))
    if any(not isinstance(rubric[d], str) for d in DIMS):
        sys.exit(f'{args.config} 的评分口径必须都是字符串')
    sources = {'定标卷': Path(args.anchor_shots).resolve(), '当前': Path(args.current).resolve()}
    if args.best:
        sources['最好'] = Path(args.best).resolve()
    shots = {}
    for name, source in sources.items():
        if not source.is_dir():
            sys.exit(f'{name}截图目录不存在：{source}')
        shots[name] = sorted(p for p in source.iterdir() if p.is_file() and p.suffix.lower() == '.png')
        if not shots[name]:
            sys.exit(f'{name}截图目录没有 PNG：{source}')
    template = Template((Path(__file__).resolve().parent.parent / 'templates' / 'REVIEW_PROMPT.md').read_text(encoding='utf-8'))
    target.mkdir(parents=True)
    sets = target / 'sets'
    sets.mkdir()
    directories = {}

    def copy_set(name):
        code = secrets.token_hex(3)
        while code in directories:
            code = secrets.token_hex(3)
        path = sets / code
        path.mkdir()
        for shot in shots[name]:
            shutil.copy2(shot, path / shot.name)
        directories[code] = name
        return str(path)

    anchor_dir, current_dir = copy_set('定标卷'), copy_set('当前')
    if args.best:
        compare_current, compare_best = copy_set('当前'), copy_set('最好')
    first, compare_first = secrets.randbelow(2), secrets.randbelow(2)
    mappings = {}
    example = {'甲': {d: 7 for d in DIMS}, '乙': {d: 7 for d in DIMS}, 'awwwards': {'设计': 6.8, '可用性': 7.0, '创意': 6.5, '内容': 6.9}}
    if args.best:
        example['对比'] = {d: ['丙', '平', '丁'][i % 3] for i, d in enumerate(DIMS if args.live_best else STATIC)}
    example_text = json.dumps(example, ensure_ascii=False, indent=2)
    if args.best:
        example_text += '\n「对比」每项填「丙」「丁」或「平」（哪组更好；看不出差别填「平」）。'
    for i in range(args.reviewers):
        reviewer = f'r{i + 1}'
        out = target / reviewer
        out.mkdir()
        order = (first + i) % 2
        labels = [('定标卷', anchor_dir), ('当前', current_dir)]
        labels = labels[order:] + labels[:order]
        mapping = {'甲': labels[0][0], '乙': labels[1][0]}
        compare_materials = '本轮没有上一个最好版本，不用做逐项比较。'
        if args.best:
            compare_order = (compare_first + i) % 2
            pairs = [('当前', compare_current), ('最好', compare_best)]
            pairs = pairs[compare_order:] + pairs[:compare_order]
            mapping.update({'丙': pairs[0][0], '丁': pairs[1][0]})
            compare_materials = f'截图丙：{pairs[0][1]}；截图丁：{pairs[1][1]}（一组是上面这个地址的版本，另一组是上一个最好版本，同页面、同宽度。逐项比较哪组更好，填进 JSON 的「对比」。）'
            if args.live_best:
                compare_materials += f'上一个最好版本也能打开：{args.live_best}，动效、微互动、好用程度、留存吸引力也请两边各点一遍再比。'
            else:
                compare_materials += '上一个最好版本只有截图，动效、微互动、好用程度、留存吸引力看不出差别，「对比」里只填排版、留白、视觉层级、色彩、响应式、原创性六项。'
        mappings[reviewer] = mapping
        values = dict(product=config['产品'], url=config['地址'], pages='\n'.join('- ' + x for x in config['页面']), set_a=labels[0][1], set_b=labels[1][1], compare_materials=compare_materials, refs='\n'.join('- ' + x for x in config['参照']), moments='\n'.join(config['招牌时刻']) or '无', sounds=('这个网站有声音，你在无头浏览器里听不到。每个操作出不出声、多大声，看下面的电平文件（测试浏览器里给音频输出接探头量的最大电平，0 是没声音，1 是满幅）；说「没有声音反馈」之前先查它：\n' + '\n'.join(config['声音']) + '\n') if config.get('声音') else '', deliberate='\n'.join(config['故意留的问题']) or '无', operate='\n'.join(['- ' + x for x in config['操作说明']] + (['- ' + config['机器限制']] if config['机器限制'] else [])), out_dir=str(out) + '/', scenario=config['场景口径'], rubric='\n'.join(f'- {d}：{rubric[d]}' for d in DIMS), rejected='、'.join(config['不碰的样子']) or '无', compare_output='- 逐项比较丙、丁两组：每项写哪组更好、为什么。' if args.best else '', json_example=example_text, review_path=str(out / 'review.md'), json_path=str(out / 'scores.json'))
        prompt_path = target / f'prompt-{reviewer}.md'
        prompt_path.write_text(template.substitute(values), encoding='utf-8')
        print(f'提示词：{prompt_path}')
    blind = {'评审': mappings, '有最好版本': bool(args.best), '最好版本可打开': bool(args.live_best), '目录': directories, '来源': {k: str(v) for k, v in sources.items()}}
    blind_path = target / 'blind.json'
    blind_path.write_text(json.dumps(blind, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'盲评对应关系：{blind_path}')
    script = shlex.quote(str(Path(__file__).with_name('calibrate.py').resolve()))
    print(f'下一步：python3 {script} --round {shlex.quote(str(target))} --anchor <定标卷标准分.json> --model "评审模型和档位"' + (' --best <best.json>' if args.best else ''))


if __name__ == '__main__':
    main()
