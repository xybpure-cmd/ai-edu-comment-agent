from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from app.config import BASE_DIR, DATA_DIR, OUTPUT_DIR, ensure_directories, load_json_config
from app.models import Candidate, CommentPack, NewsItem, TopicCard


MIN_LONG_DRAFT_CHARS = 900
MAX_LONG_DRAFT_CHARS = 1400


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


def _load_manual_item_by_url(url: str) -> dict | None:
    manual_path = DATA_DIR / 'raw' / 'manual_inputs.json'
    if not manual_path.exists():
        return None
    items = json.loads(manual_path.read_text(encoding='utf-8')).get('items', [])
    for x in items:
        if x.get('url') == url:
            return x
    return None


def build_news_item(raw: str | dict) -> NewsItem:
    if isinstance(raw, dict):
        url = raw.get('url', 'manual://item')
        title = raw.get('title', url)
        summary = raw.get('summary', '')
    else:
        url = raw
        manual = _load_manual_item_by_url(url)
        if manual:
            title = manual.get('title', url)
            summary = manual.get('summary', '待补充摘要')
        else:
            title = raw[:80]
            summary = '待补充摘要'
    return NewsItem(
        id=hashlib.md5(url.encode()).hexdigest()[:12],
        title=title,
        url=url,
        source_level=_source_level(url),
        content_type=_ctype(f'{title} {url} {summary}'),
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
    facts: list[str] = []
    summary = n.summary or ''

    if n.content_type == 'policy':
        facts.append(f'这条政策信息直接指向“{n.title}”，政策讨论对象是中小学课程组织与教学治理。')
        facts.append('该政策议题不是单点工具试用，而是课程规范、课堂使用边界与学校制度安排的协同调整。')
        facts.append('政策实施对象至少包含学校管理者、一线教师与教研组织，意味着执行链条横跨管理、教学与评价环节。')
        if '教师' in summary or '能力' in summary:
            facts.append('摘要已明确提到“教师能力建设”，说明政策动作包含培训、支持与能力升级，而非仅部署技术。')
        if '课程' in summary or '规范' in summary:
            facts.append('摘要明确提到“课程规范”，反映政策重点在教学活动可执行、可评估与可治理。')
        facts.append('从教育治理逻辑看，政策落地会同步影响课程进度安排、课堂任务设计与学习成果评价标准。')
    else:
        facts.extend([
            f'该信息标题为“{n.title}”，核心议题与AI教育应用相关。',
            f'该条来源链接为 {n.url}。',
            f'摘要信息为：{summary}',
            '事件牵涉至少一个教育行动主体（教师/学生/学校管理者）。',
        ])

    facts.append(f'来源链接为 {n.url}，来源层级判定为 {n.source_level}。')
    return facts[:6]


def _core_problem_for(n: NewsItem) -> str:
    mapping = {
        'policy': 'AI课程推进中，课程组织、评价方式与学校治理能力是否同步升级。',
        'research': '研究证据如何转化为可执行的课堂与评价安排。',
        'case': '教师角色变化是否被制度和培训体系有效承接。',
        'product': '产品进入校园后，教学目标是否被技术目标替代。',
        'news': '公共议题热度与教育长期目标之间的偏差如何校正。',
    }
    return mapping.get(n.content_type, mapping['news'])


def _judgement_units(n: NewsItem) -> tuple[str, str, str, str]:
    main = '教育部AI课程政策的关键价值，不在于增加多少技术功能，而在于能否把AI应用纳入可执行、可评估、可问责的教育治理框架。'
    arg1 = '制度层面上，AI一旦进入课程体系，就会牵动课程标准、教学组织和评价规则三条主线；若治理设计滞后，学校只能以临时性做法应对，结果是资源强校越走越快、薄弱学校越难跟进。'
    arg2 = '实践层面上，教师会首先感受到备课任务、课堂互动和作业评价的重排压力；如果能力建设与边界规范不能同步推进，AI可能从“辅助教学”滑向“替代判断”，进而削弱教师的专业主体性。'
    counter = '常见反方意见是“先扩大试点，再逐步补规则”，其现实阻力在于不同地区学校在设备、师资和管理能力上的起点差异巨大，先行扩容往往会把不平等放大为结构性后果。'
    return main, arg1, arg2, counter


def _full_draft(n: NewsItem, core_question: str, main_judgement: str, arg1: str, arg2: str, counter: str) -> str:
    p1 = (
        f'围绕“{n.title}”的讨论，如果只停留在技术功能层面，很容易把它当作一条普通的教育科技新闻。'
        f'但这条政策信息真正值得追问的问题是：{core_question} 当政策开始明确AI进课程、进课堂、进评价流程时，'
        '它改变的就不只是教学工具清单，而是学校如何定义“有效教学”、如何分配教师劳动，以及如何维护教育目标不被短期效率绑架。'
    )
    p2 = (
        '从目前可获得的信息看，至少有几条事实对理解这项政策至关重要：第一，政策关注点明确落在课程规范与教师能力建设；'
        '第二，政策动作对应的实施对象不是单一主体，而是管理者、教师和教研组织共同参与；第三，政策影响范围覆盖课程组织、课堂应用边界与评价方式；'
        '第四，政策执行要求学校把技术使用纳入可追踪、可问责的流程；第五，这类政策落地通常需要地方教育部门建立配套培训与督导机制，才能避免“纸面推进、课堂落空”。'
    )
    p3 = (
        '因此，这件事真正改变的是教育系统内部的权责关系。过去，技术往往以“可选工具”进入课堂，使用与否主要取决于个体教师；'
        '而政策化推进意味着AI将成为组织性安排：谁制定边界、谁承担风险、谁解释效果，都会从“个人选择”转向“制度责任”。'
        '这也解释了为什么同样一条政策，在不同地区会呈现不同结果——差别不在口号，而在学校治理能力与执行细节。'
    )
    p4 = (
        f'{arg1} 进一步看，治理设计至少要回答三个问题：一是课程目标如何避免被“工具可用性”替代；'
        '二是评价机制如何防止把机器生成结果直接等同于学习成果；三是资源配置如何兼顾不同学校的条件差异。'
        '如果这些问题没有被提前制度化，政策执行就会出现“上层有方向、基层无抓手”的断层，最终影响的是教育公平与系统稳定。'
    )
    p5 = (
        f'{arg2} 在真实课堂中，教师不仅要决定何时用AI，更要判断何时不用、为何不用，以及如何向学生解释这种边界。'
        f'{counter} 对这类阻力不能用一句“加强培训”草草带过，而应给出回应路径：先界定高风险场景，再建立分层培训，再把课堂反馈反向纳入政策迭代。'
        '只有形成“规则—实践—再校正”的闭环，政策目标才可能从文件语言变成课堂事实。'
    )
    p6 = (
        f'归根到底，{main_judgement} 判断一项AI教育政策是否成功，不应看学校是否“用了AI”，而应看它是否帮助学校在育人目标、教学质量与公平可及之间建立更稳固的平衡。'
        '如果政策推动后，教师专业判断更清晰、课堂目标更明确、弱势学校获得更有力支持，那么这才是值得肯定的长期后果；反之，即便技术应用热闹，也只是把教育问题技术化、而非真正解决问题。'
    )
    return '\n\n'.join([p1, p2, p3, p4, p5, p6])


def _has_substantive_facts(facts: list[str]) -> bool:
    keywords = ['政策', '课程', '教师', '学校', '实施', '评价', '培训', '治理', '对象', '课堂']
    substantive = 0
    for f in facts:
        if any(k in f for k in keywords) and '来源层级' not in f and '内容类型' not in f:
            substantive += 1
    return substantive >= 3


def _quality_status(candidate_ok: bool, verified_facts: list[str], core_q: str, main_j: str, arg1: str, arg2: str, draft: str) -> tuple[str, str, str]:
    paragraphs = [p for p in draft.split('\n\n') if p.strip()]
    p4_len = len(paragraphs[3]) if len(paragraphs) >= 4 else 0
    p5_len = len(paragraphs[4]) if len(paragraphs) >= 5 else 0
    has_long_draft = MIN_LONG_DRAFT_CHARS <= len(draft) <= MAX_LONG_DRAFT_CHARS
    expanded_ok = p4_len >= 120 and p5_len >= 120
    facts_ok = len(verified_facts) >= 3 and _has_substantive_facts(verified_facts)
    base_ok = all([core_q, main_j, arg1, arg2]) and len(paragraphs) >= 6

    if candidate_ok and base_ok and has_long_draft and expanded_ok and facts_ok:
        return 'READY', 'READY', ''

    reasons = []
    if not facts_ok:
        reasons.append('事实层过薄：需补充政策内容、教育动作、实施对象等关键事实')
    if not has_long_draft:
        reasons.append(f'长评字数未达标：当前约{len(draft)}字，目标{MIN_LONG_DRAFT_CHARS}-{MAX_LONG_DRAFT_CHARS}字')
    if not expanded_ok:
        reasons.append('第4/第5段展开不足：每段需至少120字')
    if not base_ok:
        reasons.append('主判断或六段成文结构不完整')
    if not candidate_ok:
        reasons.append('来源等级未通过正式评论门槛')

    return 'HOLD', 'HOLD', '；'.join(reasons)


def build_comment_pack(n: NewsItem, c: Candidate) -> CommentPack:
    profile = load_json_config('author_profile.json')
    tone = profile.get('preferred_tone', '稳健')
    core_question = _core_problem_for(n)
    main_judgement, arg1, arg2, counter = _judgement_units(n)
    facts = _fact_candidates(n)
    draft = _full_draft(n, core_question, main_judgement, arg1, arg2, counter)
    status, quality, hold_reason = _quality_status(c.eligible_for_formal_pack, facts, core_question, main_judgement, arg1, arg2, draft)

    titles = [
        f'{n.title}：真正的考题是教育治理能力',
        'AI进课堂之后，先回答“谁来负责、如何评价”',
        '比技术更难的是：把AI放进可持续的教育秩序',
    ]

    pending = ['需补充政策原文条款与发布时间', '需补充地方执行口径差异']
    if status == 'HOLD' and '事实层过薄' in hold_reason:
        pending.insert(0, '事实不足提示：当前关键事实偏弱，建议补充政策条文、执行范围和实施对象后再出长评READY版')

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
        pending_checks=pending,
        comment_value='具备评论价值' if status == 'READY' else '事实或成文不足，暂不建议直接发布长评',
        angle_options=['制度治理', '教师实践', '教育公平'],
        author_judgement_seed=f'建议采用{tone}语气，先判断后论证。',
        short_comment='本输出已优先生成长评底稿，如需短评可从主判断与第4-5段压缩。',
        long_comment='已生成900-1400字长评正文，可直接进入作者改写。',
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
        '## 六段式评论正文初稿（长评 900-1400 字）',
        pack.full_draft,
        '## 核心论点列表',
        *[f'- {x}' for x in pack.key_claims],
        '## 可能反方意见（含回应）',
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

    ranked = sorted(
        ready_records or records,
        key=lambda r: (r['draft_quality_level'] == 'READY', r['candidate']['priority_score']),
        reverse=True,
    )[:3]
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

    preferred = sorted(records, key=lambda r: (r.get('draft_quality_level') == 'READY', r['candidate']['priority_score']), reverse=True)[0]
    lines += [
        '',
        '## 本周最建议下笔的一篇评论',
        f"- 推荐条目：{preferred['news_item']['title']}",
        '- 推荐理由：已形成主判断与连续长评正文，可直接进入作者改写流程。',
        f"- 建议主判断：{preferred.get('main_judgement', '')}",
        '- 建议结构：六段式成文 -> 补证据 -> 强化结论。',
    ]
    out = OUTPUT_DIR / 'briefs' / f'weekly_{_tag()}.md'
    out.write_text('\n'.join(lines), encoding='utf-8')
    _log('weekly', {'recommended_topic': preferred['topic_card']['topic_name'], 'recommended_news_id': preferred['news_item']['id']})
    return out
