from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from app.config import BASE_DIR, DATA_DIR, OUTPUT_DIR, ensure_directories, load_json_config
from app.models import Candidate, CommentPack, NewsItem, TopicCard


def _tag() -> str:
    return datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')


def _log(event: str, payload: dict) -> None:
    p = DATA_DIR / 'usage_log.json'
    data = {'events': []}
    if p.exists():
        data = json.loads(p.read_text(encoding='utf-8'))
    data['events'].append({'ts': _tag(), 'event': event, 'payload': payload})
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')


def _source_level(url_or_text: str) -> str:
    wl = load_json_config('source_whitelist.json')
    for s in wl['sources']:
        if any(k in url_or_text for k in s['domain_keywords']):
            return s['source_level']
    return 'D_CLUE'


def _ctype(text: str) -> str:
    t = text.lower()
    if any(k in t for k in ['policy', '政策', '通知']):
        return 'policy'
    if any(k in t for k in ['研究', 'paper']):
        return 'research'
    if any(k in t for k in ['课堂', '教师', 'school']):
        return 'case'
    if any(k in t for k in ['产品', 'platform', 'tool']):
        return 'product'
    return 'news'


def build_news_item(raw: str | dict) -> NewsItem:
    if isinstance(raw, dict):
        url = raw.get('url', 'manual://item')
        title = raw.get('title', url)
        summary = raw.get('summary', '')
    else:
        url = raw
        title = raw[:80]
        summary = '待补充摘要'
    return NewsItem(
        id=hashlib.md5(url.encode()).hexdigest()[:12],
        title=title,
        url=url,
        source_level=_source_level(url),
        content_type=_ctype(url + ' ' + summary),
        summary=summary,
    )


def evaluate_candidate(n: NewsItem) -> Candidate:
    base = {'A_OFFICIAL': 95, 'B_AUTH_MEDIA': 75, 'C_WECHAT': 55, 'D_CLUE': 30}.get(n.source_level, 20)
    score = min(base + (5 if n.content_type in {'policy', 'research', 'case'} else 0), 100)
    if n.source_level == 'C_WECHAT':
        return Candidate(f'cand_{n.id}', n.id, score, False, False, 'C_WECHAT 默认不得直接推荐为正式评论')
    if n.source_level == 'D_CLUE':
        return Candidate(f'cand_{n.id}', n.id, score, False, False, 'D_CLUE 默认不得进入正式评论包')
    return Candidate(f'cand_{n.id}', n.id, score, True, True, '')


def _topic(n: NewsItem, c: Candidate) -> TopicCard:
    if n.content_type == 'policy':
        name, tp, desc = 'AI课程政策', 'policy', '围绕政策条文与执行路径的教育治理议题'
    elif n.content_type == 'case':
        name, tp, desc = '教师使用AI', 'practice', '聚焦教师工作流与课堂实践变化'
    elif n.content_type == 'product':
        name, tp, desc = '教育产品进校园', 'product', '聚焦平台产品进入校园后的真实适配'
    else:
        name, tp, desc = 'AI教育动态', 'general', '跨来源动态追踪与议题归档'
    pri = 'high' if c.eligible_for_formal_pack and n.content_type in {'policy', 'research'} else 'medium'
    return TopicCard(
        id=f'topic_{n.id}',
        topic_name=name,
        topic_type=tp,
        description=desc,
        related_items=[n.id],
        trend_note='本轮新增',
        status='READY' if c.eligible_for_formal_pack else 'HOLD',
        priority_level=pri,
        watch_reason='长期影响教育系统配置',
        history=[{'ts': _tag(), 'related_count': 1}],
    )


def _merge(cards: list[TopicCard]) -> list[TopicCard]:
    latest = OUTPUT_DIR / 'json' / 'topic_cards_latest.json'
    old = {}
    if latest.exists():
        for x in json.loads(latest.read_text(encoding='utf-8')):
            old[x['topic_name']] = x
    merged: dict[str, TopicCard] = {}
    for c in cards:
        if c.topic_name not in merged:
            merged[c.topic_name] = c
        else:
            merged[c.topic_name].related_items += c.related_items
    for k, v in merged.items():
        if k in old:
            v.related_items = sorted(set(old[k].get('related_items', []) + v.related_items))
            v.history = old[k].get('history', []) + [{'ts': _tag(), 'related_count': len(v.related_items)}]
    return list(merged.values())


def _planning(n: NewsItem) -> dict:
    angles = {
        'policy': '从政策执行成本与学校治理能力切入',
        'research': '从证据质量与教育效果可迁移性切入',
        'case': '从教师真实工作流变化切入',
        'product': '从产品承诺与课堂真实需求错位切入',
        'news': '从舆论热度与长期议题错位切入',
    }
    return {
        'core question': '这条信息真正改变了教育系统哪个关键环节？',
        'possible angle': angles[n.content_type],
        'likely audience': ['教师', '学校管理者'],
        'debate/tension': '效率提升 vs 教育目标异化',
    }


def _fact_candidates(n: NewsItem) -> list[str]:
    text = f'{n.title} {n.summary}'.lower()
    placeholder_summary = n.summary.strip() in {'待补充摘要', '', '暂无'}
    facts: list[str] = []

    if any(k in text for k in ['发布', '印发', '出台', '通知', '方案', 'policy', '政策']):
        facts.append('政策动作事实：材料明确指向“发布/出台政策动作”，而非一般舆情转述。')
    if any(k in text for k in ['学校', '教师', '学生', '课程', '中小学', '高校']):
        facts.append('实施对象事实：文本涉及学校、教师、学生或课程等明确教育实施对象。')
    if any(k in text for k in ['规范', '标准', '评价', '治理', '监管', '责任', '边界']):
        facts.append('治理要求事实：材料出现规范、评价、治理或边界等制度性要求。')
    if any(k in text for k in ['公平', '质量', '课堂', '学习', '育人', '负担', '效果']):
        facts.append('教育后果事实：文本触及课堂效果、教育公平、学习质量等教育后果。')

    if not placeholder_summary:
        facts.append(f'摘要事实：{n.summary}')

    return facts


def _core_problem_for(n: NewsItem) -> str:
    mapping = {
        'policy': 'AI课程推进中，课程组织与学校治理能力是否匹配。',
        'research': '研究证据如何转化为可执行的课堂与评价安排。',
        'case': '教师角色变化是否被制度和培训体系有效承接。',
        'product': '产品进入校园后，教学目标是否被技术目标替代。',
        'news': '公共议题热度与教育长期目标之间的偏差如何校正。',
    }
    return mapping.get(n.content_type, mapping['news'])


def _judgement_units(n: NewsItem) -> tuple[str, str, str, str]:
    main = 'AI课程政策的价值不在“有没有工具”，而在能否把技术纳入可治理、可追责、可持续的教育秩序。'
    arg1 = '制度层面上，政策一旦进入课程体系，就会重塑教学目标、课程安排与评价规则，学校治理能力将成为成败关键。'
    arg2 = '实践层面上，教师将直接面对备课、授课和评价的流程重构，若缺少能力建设与边界规范，课堂可能被“效率叙事”牵着走。'
    counter = '反方可能认为先大规模试点再补规则更高效，但现实阻力在于学校资源与教师能力差异，先上车后补票容易放大不公平。'
    if n.content_type != 'policy':
        main = 'AI进入教育后，真正要讨论的不是工具新不新，而是教育目标是否被稳定守住。'
    return main, arg1, arg2, counter


def _full_draft(n: NewsItem, core_question: str, main_judgement: str, arg1: str, arg2: str, counter: str) -> str:
    p1 = f'围绕“{n.title}”的讨论，表面上看是一次AI应用信息更新，真正值得追问的是：{core_question} 这不是一条可以被当作技术新闻快速消费的消息，而是教育系统如何吸收新工具、又不偏离育人目标的现实考题。'
    p2 = f'就本文所依据的信息看，至少有几条关键事实不能跳过：第一，事件指向的主题明确是AI与教育结合；第二，信息来源可回溯到 {n.url}；第三，该来源层级判定为 {n.source_level}，具备进入公共讨论的基础；第四，内容类型判定为 {n.content_type}；第五，现有摘要强调“{n.summary}”，说明讨论焦点已从技术能力转向教学与治理边界。'
    p3 = f'因此，这件事真正改变的不是课堂里多了一个功能，而是课程组织、教师角色与学校治理之间的关系。过去我们把技术当作教学附加项，现在它正在变成教学结构变量：谁来决定使用边界、如何评价学习效果、怎样保障不同学校的实施条件，这些问题都被同时抛到了台前。'
    p4 = (
        f'{arg1} 更关键的是，政策一旦写入课程组织链条，就不再是“教师个人愿不愿意尝试”的选择题，而是'
        '学校系统如何重排时间、资源、评价和问责机制的治理题。学校管理层需要决定：AI环节是进入学科课堂、综合实践'
        '还是校本课程；不同学段的学习目标如何分层；对学生AI使用行为采取允许、引导还是限制；评价体系中哪些结果可以由'
        'AI辅助、哪些必须由教师独立判断。若这些前置规则缺位，政策执行会迅速退化成“形式上线、质量失真”：看起来工具普及率上去了，'
        '但课程目标、学习证据与评价公正性并没有同步提升。换句话说，政策文本的价值不在口号，而在它能否把学校治理从“经验型应对”'
        '推进到“规则型执行”，这是决定政策能否走到课堂深处的第一道门槛。'
    )
    p5 = (
        f'{arg2} 反方常见观点是“先大规模试点、边跑边改”，理由是教育技术变化太快，先铺开才能积累经验。'
        f'这一观点有现实吸引力，但并不充分。{counter} 具体到实施层面，若把规则设计完全滞后于应用扩张，最先暴露的问题通常不是'
        '“技术不好用”，而是“谁来承担后果”——学生学习偏差如何纠正、教师评价争议如何仲裁、学校间资源差距如何补偿。更稳妥的路径应是'
        '“有限试点 + 规则并行 + 证据评估”：先在可控范围内验证场景，建立最小治理清单（责任边界、数据规范、评价红线、教师支持方案），'
        '再按证据扩容。这样做并非保守，而是避免将教育公平与课堂质量押注在不确定的执行条件上。'
    )
    p6 = f'归根到底，{main_judgement} 对这类AI教育议题的评价标准，不应是“是否更快”或“是否更炫”，而应是是否让教育更公平、更有质量、也更能被长期治理。'
    return '\n\n'.join([p1, p2, p3, p4, p5, p6])


def _quality_status(candidate_ok: bool, verified_facts: list[str], core_q: str, main_j: str, arg1: str, arg2: str, draft: str) -> tuple[str, str, str]:
    has_continuous_draft = len([p for p in draft.split('\n\n') if p.strip()]) >= 6
    paragraphs = [p.strip() for p in draft.split('\n\n') if p.strip()]
    p4_expanded = len(paragraphs[3]) >= 160 if len(paragraphs) >= 5 else False
    p5_expanded = len(paragraphs[4]) >= 160 if len(paragraphs) >= 5 else False
    draft_len = len(draft)
    enough_policy_facts = len(verified_facts) >= 3
    quality_ready = (
        candidate_ok
        and enough_policy_facts
        and all([core_q, main_j, arg1, arg2])
        and has_continuous_draft
        and p4_expanded
        and p5_expanded
        and 1000 <= draft_len <= 1500
    )
    if quality_ready:
        return 'READY', 'READY', ''
    if not enough_policy_facts:
        return 'HOLD', 'HOLD', '事实提炼不足，无法形成可发评论底稿'
    return 'HOLD', 'HOLD', '未满足评论底稿READY最低门槛（事实、判断或成文结构不足）'


def build_comment_pack(n: NewsItem, c: Candidate) -> CommentPack:
    profile = load_json_config('author_profile.json')
    tone = profile.get('preferred_tone', '稳健')
    core_question = _core_problem_for(n)
    main_judgement, arg1, arg2, counter = _judgement_units(n)
    facts = _fact_candidates(n)[:5]
    draft = _full_draft(n, core_question, main_judgement, arg1, arg2, counter)
    status, quality, hold_reason = _quality_status(c.eligible_for_formal_pack, facts, core_question, main_judgement, arg1, arg2, draft)

    titles = [
        f'{n.title}：真正的考题是教育治理能力',
        'AI进课堂之后，先回答“谁来负责、如何评价”',
        '比技术更难的是：把AI放进可持续的教育秩序',
    ]

    return CommentPack(
        id=f'comment_pack_{n.id}',
        candidate_id=c.id,
        status=status,
        hold_reason=hold_reason or c.hold_reason,
        basic_info={
            'title': n.title,
            'url': n.url,
            'source_level': n.source_level,
            'content_type': n.content_type,
            'target_audience': profile.get('preferred_target_audience', []),
        },
        one_sentence_summary='这条信息表面谈AI应用，实质关乎教育系统如何重构治理与实践。',
        verified_facts=facts,
        pending_checks=['需补充政策原文条款与发布时间', '需补充地方执行口径差异'],
        comment_value='具备评论价值' if status == 'READY' else '线索价值优先',
        angle_options=['制度治理', '教师实践', '教育公平'],
        author_judgement_seed=f'建议采用{tone}语气，先判断后论证。',
        short_comment='见“作者底稿层”六段正文，可直接压缩为短评。',
        long_comment='见“作者底稿层”六段正文，可直接扩展为长评。',
        sources=[{'url': n.url, 'source_level': n.source_level}],
        author_decision_points=['结论强度是“审慎推进”还是“先立规后扩容”', '是否加入地方样本作为补强证据'],
        education_core_question=core_question,
        main_judgement=main_judgement,
        supporting_argument_1=arg1,
        supporting_argument_2=arg2,
        counterargument=counter,
        full_draft=draft,
        draft_quality_level=quality,
        planning=_planning(n),
        recommended_title_options=titles,
        opening_hook_options=['这条信息真正触及的不是工具更新，而是教育治理能力。'],
        key_claims=[main_judgement, arg1, arg2],
        possible_counterarguments=[counter],
        primary_title=titles[0],
        alternative_titles=titles[1:],
        suggested_opening_paragraph='当AI真正进入课堂，教育系统首先失去的往往不是效率，而是边界感。',
        ending_suggestion='结尾回到教育目标：技术应用必须服务于更公平、更高质量、可持续的教育。',
    )


def export_outputs(pack: CommentPack) -> None:
    ensure_directories()
    pref = 'hold_' if pack.status == 'HOLD' else ''
    jp = OUTPUT_DIR / 'json' / f'{pref}{pack.id}.json'
    mp = OUTPUT_DIR / 'markdown' / f'{pref}{pack.id}.md'
    tp = OUTPUT_DIR / 'txt' / f'{pref}{pack.id}.txt'
    jp.write_text(json.dumps(pack.to_dict(), ensure_ascii=False, indent=2), encoding='utf-8')

    internal_lines = [
        '# 内部分析层',
        '## 新闻基本信息',
        f"- 标题: {pack.basic_info['title']}",
        f"- URL: {pack.basic_info['url']}",
        f"- 来源层级: {pack.basic_info['source_level']}",
        f"- 内容类型: {pack.basic_info['content_type']}",
        '## 一句话摘要',
        pack.one_sentence_summary,
        '## 已核实事实',
        *[f'- {x}' for x in pack.verified_facts],
        '## 待核实信息',
        *[f'- {x}' for x in pack.pending_checks],
        '## 教育核心问题',
        pack.education_core_question,
        '## 主判断句',
        pack.main_judgement,
        '## 两个支撑论点',
        f'- 论点一: {pack.supporting_argument_1}',
        f'- 论点二: {pack.supporting_argument_2}',
        '## 一个可能的反方意见',
        f'- {pack.counterargument}',
        '## 需作者拍板处',
        *[f'- {x}' for x in pack.author_decision_points],
        '## 状态',
        f'- status: {pack.status}',
        f'- draft_quality_level: {pack.draft_quality_level}',
        f"- hold_reason: {pack.hold_reason or '无'}",
        '## 评论策划',
        f"- core question: {pack.planning.get('core question', '')}",
        f"- possible angle: {pack.planning.get('possible angle', '')}",
        f"- likely audience: {', '.join(pack.planning.get('likely audience', []))}",
        f"- debate/tension: {pack.planning.get('debate/tension', '')}",
    ]

    author_lines = [
        '# 作者底稿层',
        f'# {pack.primary_title}',
        '## 备选标题',
        *[f'- {x}' for x in pack.alternative_titles],
        '## 建议开头段',
        pack.suggested_opening_paragraph,
        '## 六段式评论正文初稿',
        pack.full_draft,
        '## 核心论点列表',
        *[f'- {x}' for x in pack.key_claims],
        '## 可能反方意见',
        f'- {pack.counterargument}',
        '## 结尾收束建议',
        pack.ending_suggestion,
    ]

    content = '\n'.join(author_lines + ['', '---', ''] + internal_lines)
    mp.write_text(content, encoding='utf-8')
    tp.write_text(content, encoding='utf-8')
    _log('build', {'candidate_id': pack.candidate_id, 'topic': pack.basic_info['content_type'], 'status': pack.status})


def _load_inputs() -> list[str | dict]:
    fixture = json.loads((BASE_DIR / 'tests/fixtures/scan_inputs.json').read_text(encoding='utf-8')).get('items', [])
    manual_path = DATA_DIR / 'raw' / 'manual_inputs.json'
    manual = json.loads(manual_path.read_text(encoding='utf-8')).get('items', []) if manual_path.exists() else []
    return fixture + manual


def run_scan() -> dict[str, str]:
    ensure_directories()
    ts = _tag()
    items = _load_inputs()
    records = []
    cards = []
    ready_records = []

    for raw in items:
        n = build_news_item(raw)
        c = evaluate_candidate(n)
        p = build_comment_pack(n, c)
        t = _topic(n, c)
        t.status = p.status
        record = {
            'news_item': asdict(n),
            'candidate': asdict(c),
            'topic_card': t.to_dict(),
            'draft_quality_level': p.draft_quality_level,
            'hold_reason': p.hold_reason,
            'main_judgement': p.main_judgement,
        }
        records.append(record)
        cards.append(t)
        if p.status == 'READY':
            ready_records.append(record)

    grouped = _merge(cards)
    cp = OUTPUT_DIR / 'json' / f'candidates_{ts}.json'
    cp.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding='utf-8')
    tp = OUTPUT_DIR / 'json' / f'topic_cards_{ts}.json'
    payload = [x.to_dict() for x in grouped]
    tp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    (OUTPUT_DIR / 'json' / 'topic_cards_latest.json').write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')

    fact_thin_reason = '事实提炼不足，无法形成可发评论底稿'
    filtered_records = [r for r in records if r.get('hold_reason') != fact_thin_reason]
    ranked_pool = ready_records or filtered_records or records
    ranked = sorted(ranked_pool, key=lambda r: (r['candidate']['priority_score'], r['draft_quality_level'] == 'READY'), reverse=True)[:3]
    brief = ['# 本轮更新简报', '', '## 本轮最值得关注的3条']
    dash = ['# 作者工作台', '', '## 本轮最值得写的3条（优先READY）']
    for r in ranked:
        n, c, t = r['news_item'], r['candidate'], r['topic_card']
        pref = '长评' if c['priority_score'] >= 85 else '短评'
        brief += [f"- {n['title']}：核心问题={_core_problem_for(NewsItem(**n))}；主判断={r['main_judgement']}"]
        dash += [
            f"- {n['title']}",
            f"  - 状态：{r['draft_quality_level']}",
            f"  - 主判断：{r['main_judgement']}",
            f"  - 对应 topic card：{t['topic_name']}",
            f"  - 推荐优先级：{c['priority_score']}",
            f"  - 建议写作长度：{pref}",
        ]

    bp = OUTPUT_DIR / 'briefs' / f'briefs_{ts}.md'
    bp.write_text('\n'.join(brief), encoding='utf-8')
    dp = OUTPUT_DIR / 'briefs' / f'writer_dashboard_{ts}.md'
    dp.write_text('\n'.join(dash), encoding='utf-8')
    return {'brief': str(bp), 'candidates': str(cp), 'topics': str(tp), 'dashboard': str(dp), 'count': str(len(records))}


def run_weekly_review() -> Path:
    ensure_directories()
    cand = sorted((OUTPUT_DIR / 'json').glob('candidates_*.json'), key=lambda p: p.stat().st_mtime, reverse=True)
    topics = sorted((OUTPUT_DIR / 'json').glob('topic_cards_*.json'), key=lambda p: p.stat().st_mtime, reverse=True)
    if not cand or not topics:
        run_scan()
        cand = sorted((OUTPUT_DIR / 'json').glob('candidates_*.json'), key=lambda p: p.stat().st_mtime, reverse=True)
        topics = sorted((OUTPUT_DIR / 'json').glob('topic_cards_*.json'), key=lambda p: p.stat().st_mtime, reverse=True)

    records = json.loads(cand[0].read_text(encoding='utf-8'))
    tps = json.loads(topics[0].read_text(encoding='utf-8'))
    top3 = tps[:3]
    lines = ['# 周度专题简报', '', '## 本周最值得关注的3个AI+教育议题']
    for t in top3:
        lines += [
            f"### {t['topic_name']}",
            f"- 为什么值得持续观察：{t.get('watch_reason', '长期影响教育系统配置')}",
            '- 可延展的评论方向：从制度后果、实践摩擦与教育公平展开。',
            '- 关联条目：',
        ]
        rel = set(t.get('related_items', []))
        for r in records:
            n = r['news_item']
            if n['id'] in rel:
                lines.append(f"  - {n['title']} ({n['content_type']})")

    fact_thin_reason = '事实提炼不足，无法形成可发评论底稿'
    filtered_records = [r for r in records if r.get('hold_reason') != fact_thin_reason]
    preferred_pool = filtered_records or records
    preferred = sorted(preferred_pool, key=lambda r: (r.get('draft_quality_level') == 'READY', r['candidate']['priority_score']), reverse=True)[0]
    lines += [
        '',
        '## 本周最建议下笔的一篇评论',
        f"- 推荐条目：{preferred['news_item']['title']}",
        '- 推荐理由：已形成主判断与连续正文，可直接进入作者改写流程。',
        f"- 建议主判断：{preferred.get('main_judgement', '')}",
        '- 建议结构：六段式成文 -> 补证据 -> 强化结论。',
    ]
    out = OUTPUT_DIR / 'briefs' / f'weekly_{_tag()}.md'
    out.write_text('\n'.join(lines), encoding='utf-8')
    _log('weekly', {'recommended_topic': preferred['topic_card']['topic_name'], 'recommended_news_id': preferred['news_item']['id']})
    return out
