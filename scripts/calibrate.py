import argparse
import json
import math
import sys
from pathlib import Path

DIMS = ['排版', '留白', '视觉层级', '色彩', '动效', '微互动', '响应式', '原创性', '好用程度', '留存吸引力']
STATIC = ['排版', '留白', '视觉层级', '色彩', '响应式', '原创性']
DYNAMIC = [d for d in DIMS if d not in STATIC]
WEIGHTS = {'设计': 0.4, '可用性': 0.3, '创意': 0.2, '内容': 0.1}


def load(path):
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def scores(value, keys, location):
    if not isinstance(value, dict):
        sys.exit(f'{location} 必须是分数字典')
    missing = [k for k in keys if k not in value]
    extra = [k for k in value if k not in keys]
    if missing or extra:
        sys.exit(f'{location} 维度不正确，缺少：{missing or "无"}；多出：{extra or "无"}')
    for key in keys:
        if not number(value[key]) or not 1 <= value[key] <= 10:
            sys.exit(f'{location} 的「{key}」必须是 1 到 10 的数字')


def main():
    parser = argparse.ArgumentParser(description='校正盲评分数，并按并排比较结果决定最好版本。')
    parser.add_argument('--round', required=True)
    parser.add_argument('--anchor', required=True)
    parser.add_argument('--model', required=True)
    parser.add_argument('--best')
    parser.add_argument('--save')
    parser.add_argument('--live-anchor', action='store_true')
    parser.add_argument('--max-shift', type=float, default=1.0)
    args = parser.parse_args()
    if not math.isfinite(args.max_shift) or args.max_shift < 0:
        sys.exit('--max-shift 必须是非负数字')
    std = load(args.anchor)
    scores(std, DIMS, args.anchor)
    round_path = Path(args.round).resolve()
    blind_path = round_path / 'blind.json'
    blind = load(blind_path)
    if not isinstance(blind, dict) or not isinstance(blind.get('评审'), dict) or len(blind['评审']) < 2 or type(blind.get('有最好版本')) is not bool or type(blind.get('最好版本可打开')) is not bool:
        sys.exit(f'{blind_path} 的评审或最好版本信息不正确')
    has_best = blind['有最好版本']
    live_best = blind['最好版本可打开']
    if live_best and not has_best:
        sys.exit(f'{blind_path} 没有最好版本，不能标为可打开')
    if args.best and not has_best:
        sys.exit(f'{blind_path} 没有最好版本，请重新生成提示词时加 --best')
    if has_best and not args.best:
        sys.exit(f'{blind_path} 带了最好版本的截图，要用 --best 给出最好版本的分数文件')
    best = None
    if args.best:
        best = load(args.best)
        message = f'{args.best} 格式应为：{{"分": {{十项}}, "总分": 74.0, "模型": "模型", "轮次": "r3", "awwwards": {{四项}} 或 null}}'
        if not isinstance(best, dict) or set(best) != {'分', '总分', '模型', '轮次', 'awwwards'} or not number(best['总分']) or not isinstance(best['模型'], str) or not isinstance(best['轮次'], str):
            sys.exit(message)
        scores(best['分'], DIMS, args.best + ' 的分')
        if best['awwwards'] is not None:
            scores(best['awwwards'], list(WEIGHTS), args.best + ' 的 awwwards')
    corrected, raws, awards, reviews = [], [], [], []
    for name, mapping in blind['评审'].items():
        if not isinstance(name, str) or not name.startswith('r') or not name[1:].isdigit() or not isinstance(mapping, dict):
            sys.exit(f'{blind_path} 的评审名称或映射不正确：{name}')
        if {mapping.get('甲'), mapping.get('乙')} != {'定标卷', '当前'}:
            sys.exit(f'{blind_path} 的 {name} 甲乙对应关系不正确')
        if has_best and {mapping.get('丙'), mapping.get('丁')} != {'当前', '最好'}:
            sys.exit(f'{blind_path} 的 {name} 丙丁对应关系不正确')
        path = round_path / name / 'scores.json'
        review = load(path)
        if not isinstance(review, dict):
            sys.exit(f'{path} 必须是 JSON 对象')
        for label in ('甲', '乙'):
            scores(review.get(label), DIMS, f'{path} 的「{label}」')
        if 'awwwards' in review:
            scores(review['awwwards'], list(WEIGHTS), f'{path} 的 awwwards')
            awards.append(review['awwwards'])
        if has_best:
            compare = review.get('对比')
            required = DIMS if live_best else STATIC
            if not isinstance(compare, dict) or set(compare) != set(required):
                sys.exit(f'{path} 的「对比」必须正好包含：' + '、'.join(required))
            for d in required:
                if compare[d] not in ('丙', '丁', '平'):
                    sys.exit(f'{path} 的「对比」中「{d}」只能是丙、丁或平')
        anchor_key = next(k for k in ('甲', '乙') if mapping[k] == '定标卷')
        current_key = next(k for k in ('甲', '乙') if mapping[k] == '当前')
        raw = review[current_key]
        adjusted = {}
        for d in DIMS:
            shift = 0 if not args.live_anchor and d in DYNAMIC else max(-args.max_shift, min(args.max_shift, std[d] - review[anchor_key][d]))
            adjusted[d] = raw[d] + shift
        raws.append(raw)
        corrected.append(adjusted)
        reviews.append((name, mapping, review))
    count = len(reviews)
    avg = {d: round(sum(c[d] for c in corrected) / count, 1) for d in DIMS}
    raw_avg = {d: sum(c[d] for c in raws) / count for d in DIMS}
    total = round(sum(avg.values()), 1)
    print('校正后平均分：')
    for d in DIMS:
        spread = max(c[d] for c in corrected) - min(c[d] for c in corrected)
        print(f'  {d} {avg[d]:.1f}' + ('  两位评审差 3 分以上，看一下理由' if spread >= 3 else ''))
    print(f'总分 {total:.1f} / 100')
    print('低于 9 的项：' + ('、'.join(d for d in DIMS if avg[d] < 9) or '无'))
    print(f'校正前平均总分 {sum(raw_avg.values()):.1f}')
    moved = [f'{d} {raw_avg[d]:.1f}→{avg[d]:.1f}' for d in DIMS if round(abs(sum(c[d] for c in corrected) / count - raw_avg[d]), 10) >= 1]
    print('校正挪动 1 分以上的项：' + ('、'.join(moved) + '。检查看定标卷的条件是不是和当初一样。' if moved else '无'))
    aw = None
    weighted = None
    if awards:
        aw = {k: round(sum(x[k] for x in awards) / len(awards), 2) for k in WEIGHTS}
        weighted = round(sum(aw[k] * WEIGHTS[k] for k in WEIGHTS), 2)
        print('Awwwards：' + ' · '.join(f'{k} {aw[k]:.2f}' for k in WEIGHTS) + f'；加权总分 {weighted:.2f}（Honorable Mention 6.5+，SOTD 加权常在 7.2-7.7）')
    else:
        print('Awwwards：无评分')
    conclusion = '第一轮'
    results = {}
    if best:
        print('并排比较：')
        for d in DIMS:
            if live_best or d in STATIC:
                votes = []
                for name, mapping, review in reviews:
                    choice = review['对比'][d]
                    vote = 0 if choice == '平' else (1 if mapping[choice] == '当前' else -1)
                    votes.append(vote)
                if all(v == -1 for v in votes):
                    result = '差（两位都判定）'
                elif 1 in votes and -1 in votes and sum(votes) == 0:
                    result = '分歧'
                elif sum(votes) >= 1:
                    result = '好'
                elif sum(votes) <= -1:
                    result = '差'
                else:
                    result = '平'
                vote_text = '、'.join(f'{reviews[i][0]} {v:+d}' for i, v in enumerate(votes))
            else:
                vote_text = '截图无法比较'
                if args.model != best['模型']:
                    result = '平（换了评审模型，没法比）'
                elif round(avg[d] - best['分'][d], 10) >= 1:
                    result = '好'
                elif round(best['分'][d] - avg[d], 10) >= 1:
                    result = '差'
                else:
                    result = '平'
            results[d] = result
            print(f'  {d}：{vote_text}，{result}')
        good = [d for d in DIMS if results[d] == '好']
        bad = [d for d in DIMS if results[d] in ('差', '差（两位都判定）')]
        unanimous = [d for d in DIMS if results[d] == '差（两位都判定）']
        disagreements = [d for d in DIMS if results[d] == '分歧']
        if unanimous:
            conclusion = '退回'
            print('退回：' + '、'.join(unanimous) + ' 两位评审都判定最好版本更好。把这批里动到这几项的改动，用编辑改回最好版本的样子，作为新提交加在最后，其余保留；最好版本不变。')
        elif len(good) > len(bad):
            conclusion = '新的最好版本'
            print('新的最好版本。')
            if bad or disagreements:
                print('下一批先看：' + '、'.join(d for d in DIMS if d in bad or d in disagreements) + '。')
        elif len(good) == len(bad):
            conclusion = '持平'
            print('持平：这一版留作下一批的底版，最好版本不变。')
            print('差和分歧的项：' + ('、'.join(d for d in DIMS if d in bad or d in disagreements) or '无'))
        else:
            conclusion = '比最好版本差'
            print('比最好版本差：把判定变差的几项（' + '、'.join(bad) + '）改回最好版本的样子，最好版本不变。')
        delta = round(total - best['总分'], 10)
        print(f'绝对分：最好版本 {best["总分"]:.1f}（{best["模型"]}）→ 这一轮 {total:.1f}（{args.model}）')
        if args.model != best['模型']:
            print('评审模型不同，绝对分不直接比，以并排比为准。')
        elif abs(delta) < 3:
            print('差 3 分以内，算评审误差。')
        elif (delta < 0 and conclusion == '新的最好版本') or (delta > 0 and conclusion in ('退回', '比最好版本差')):
            print(f'绝对分和并排比方向相反（差 {abs(delta):.1f} 分），看两位评审的理由再定，日志里写明。')
    if args.save and (not best or conclusion == '新的最好版本'):
        saved = {'分': avg, '总分': total, '模型': args.model, '轮次': round_path.name, 'awwwards': aw}
        Path(args.save).write_text(json.dumps(saved, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        print(f'已存到：{args.save}')
    elif args.save:
        print(f'结论不是新的最好版本，没有改动 {args.save}')
    log = f'日志用：独立评审（{args.model}，{count} 位）校正后 ' + ' · '.join(f'{d}{avg[d]:.1f}' for d in DIMS) + f'（合计 {total:.1f}）；Awwwards 加权 ' + (f'{weighted:.2f}' if weighted is not None else '无')
    if best:
        good_count = sum(v == '好' for v in results.values())
        bad_count = sum(v in ('差', '差（两位都判定）') for v in results.values())
        log += f'；并排比 好 {good_count} · 平 {len(DIMS) - good_count - bad_count} · 差 {bad_count} → {conclusion}'
    print(log)


if __name__ == '__main__':
    main()
