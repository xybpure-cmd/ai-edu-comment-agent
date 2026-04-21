from __future__ import annotations
import hashlib,json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from app.config import BASE_DIR,OUTPUT_DIR,DATA_DIR,ensure_directories,load_json_config
from app.models import NewsItem,Candidate,TopicCard,CommentPack

def _tag()->str:return datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')
def _log(event:str,payload:dict)->None:
    p=DATA_DIR/'usage_log.json'
    data={'events':[]}
    if p.exists(): data=json.loads(p.read_text(encoding='utf-8'))
    data['events'].append({'ts':_tag(),'event':event,'payload':payload})
    p.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')

def _source_level(url_or_text:str)->str:
    wl=load_json_config('source_whitelist.json')
    for s in wl['sources']:
        if any(k in url_or_text for k in s['domain_keywords']): return s['source_level']
    return 'D_CLUE'

def _ctype(text:str)->str:
    t=text.lower()
    if any(k in t for k in ['policy','政策','通知']): return 'policy'
    if any(k in t for k in ['研究','paper']): return 'research'
    if any(k in t for k in ['课堂','教师','school']): return 'case'
    if any(k in t for k in ['产品','platform','tool']): return 'product'
    return 'news'

def build_news_item(raw:str|dict)->NewsItem:
    if isinstance(raw,dict):
        url=raw.get('url','manual://item'); title=raw.get('title',url); summary=raw.get('summary','')
    else:
        url=raw; title=raw[:80]; summary='待补充摘要'
    return NewsItem(id=hashlib.md5(url.encode()).hexdigest()[:12],title=title,url=url,source_level=_source_level(url),content_type=_ctype(url+' '+summary),summary=summary)

def evaluate_candidate(n:NewsItem)->Candidate:
    base={'A_OFFICIAL':95,'B_AUTH_MEDIA':75,'C_WECHAT':55,'D_CLUE':30}.get(n.source_level,20)
    score=min(base+(5 if n.content_type in {'policy','research','case'} else 0),100)
    if n.source_level=='C_WECHAT':return Candidate(f'cand_{n.id}',n.id,score,False,False,'C_WECHAT 默认不得直接推荐为正式评论')
    if n.source_level=='D_CLUE':return Candidate(f'cand_{n.id}',n.id,score,False,False,'D_CLUE 默认不得进入正式评论包')
    return Candidate(f'cand_{n.id}',n.id,score,True,True,'')

def _topic(n:NewsItem,c:Candidate)->TopicCard:
    if n.content_type=='policy': name,tp,desc='AI课程政策','policy','围绕政策条文与执行路径的教育治理议题'
    elif n.content_type=='case': name,tp,desc='教师使用AI','practice','聚焦教师工作流与课堂实践变化'
    elif n.content_type=='product': name,tp,desc='教育产品进校园','product','聚焦平台产品进入校园后的真实适配'
    else: name,tp,desc='AI教育动态','general','跨来源动态追踪与议题归档'
    pri='high' if c.eligible_for_formal_pack and n.content_type in {'policy','research'} else 'medium'
    return TopicCard(id=f'topic_{n.id}',topic_name=name,topic_type=tp,description=desc,related_items=[n.id],trend_note='本轮新增',status='READY' if c.eligible_for_formal_pack else 'HOLD',priority_level=pri,watch_reason='长期影响教育系统配置',history=[{'ts':_tag(),'related_count':1}])

def _merge(cards:list[TopicCard])->list[TopicCard]:
    latest=OUTPUT_DIR/'json'/'topic_cards_latest.json'
    old={}
    if latest.exists():
        for x in json.loads(latest.read_text(encoding='utf-8')): old[x['topic_name']]=x
    m={}
    for c in cards:
        if c.topic_name not in m: m[c.topic_name]=c
        else: m[c.topic_name].related_items+=c.related_items
    for k,v in m.items():
        if k in old:
            v.related_items=sorted(set(old[k].get('related_items',[])+v.related_items))
            v.history=old[k].get('history',[])+[{'ts':_tag(),'related_count':len(v.related_items)}]
    return list(m.values())

def _planning(n:NewsItem)->dict:
    angles={'policy':'从政策执行成本与学校治理能力切入','research':'从证据质量与教育效果可迁移性切入','case':'从教师真实工作流变化切入','product':'从产品承诺与课堂真实需求错位切入','news':'从舆论热度与长期议题错位切入'}
    return {'core_question':'这条信息真正改变了教育系统哪个关键环节？','possible_angle':angles[n.content_type],'likely_audience':['教师','学校管理者'],'debate_tension':'效率提升 vs 教育目标异化'}

def build_comment_pack(n:NewsItem,c:Candidate)->CommentPack:
    profile=load_json_config('author_profile.json')
    status='READY' if c.eligible_for_formal_pack else 'HOLD'
    tone=profile.get('preferred_tone','稳健')
    titles=[f"{n.title}：教育后果比技术细节更重要",f"从{n.content_type}看AI教育的真实分水岭"]
    return CommentPack(
        id=f'comment_pack_{n.id}',candidate_id=c.id,status=status,hold_reason=c.hold_reason,basic_info={'title':n.title,'url':n.url,'source_level':n.source_level,'content_type':n.content_type,'target_audience':profile.get('preferred_target_audience',[])},
        one_sentence_summary='这是一条与AI+教育相关、值得进一步分析的资讯。',
        verified_facts=[f'来源层级为 {n.source_level}'],pending_checks=['需补充原始出处细节'],comment_value='具备评论价值' if c.recommended else '线索价值优先',
        angle_options=['从教育治理角度分析其制度意义','从教师角色变化角度讨论其影响','从技术应用边界角度讨论其风险'],
        author_judgement_seed=f"建议采用{tone}语气，{profile.get('commentary_style_notes','')}",
        short_comment='建议先写短评' if profile.get('preferred_article_length')=='short' else '建议先形成结构化短评再扩写。',
        long_comment='长评建议：先事实后判断，突出教育后果。',
        sources=[{'url':n.url,'source_level':n.source_level}],author_decision_points=['是否作为正式评论选题'],planning=_planning(n),
        recommended_title_options=titles,opening_hook_options=['这条信息表面谈技术，实则改写学校治理逻辑。'],key_claims=['高可信来源是评论成立前提','应优先讨论制度后果'],possible_counterarguments=['也可先试点后治理'],
        primary_title=titles[0],alternative_titles=titles[1:],suggested_opening_paragraph='如果只看功能演示，我们会错过教育系统真正的压力点。',ending_suggestion='结尾回到“教育目标是否更公平、更可持续”这一判断框架。'
    )

def export_outputs(pack:CommentPack)->None:
    ensure_directories(); pref='hold_' if pack.status=='HOLD' else ''
    jp=OUTPUT_DIR/'json'/f'{pref}{pack.id}.json'; mp=OUTPUT_DIR/'markdown'/f'{pref}{pack.id}.md'; tp=OUTPUT_DIR/'txt'/f'{pref}{pack.id}.txt'
    jp.write_text(json.dumps(pack.to_dict(),ensure_ascii=False,indent=2),encoding='utf-8')
    md='\n'.join([f"# {pack.primary_title}",f"- status: {pack.status}",f"- hold reason: {pack.hold_reason}" if pack.hold_reason else '',"## 新闻基本信息",f"- URL: {pack.basic_info['url']}","## 一句话摘要",pack.one_sentence_summary,"## 已核实事实",*['- '+x for x in pack.verified_facts],"## 待核实信息",*['- '+x for x in pack.pending_checks],"## 评论价值判断",pack.comment_value,"## 三个可选评论角度",*['- '+x for x in pack.angle_options],"## 作者主判断建议",pack.author_judgement_seed,"## 300字短评",pack.short_comment,"## 800-1200字长评",pack.long_comment,"## 引用来源清单",*['- '+x['url'] for x in pack.sources],"## 评论策划",f"- core question: {pack.planning['core_question']}",f"- possible angle: {pack.planning['possible_angle']}",f"- likely audience: {', '.join(pack.planning['likely_audience'])}",f"- debate/tension: {pack.planning['debate_tension']}","## 可直接改写素材","### 建议标题（主标题 + 备选标题)",f"- 主标题: {pack.primary_title}",*['- 备选: '+x for x in pack.alternative_titles],"### 建议开头段",pack.suggested_opening_paragraph,"### 核心论点列表",*['- '+x for x in pack.key_claims],"### 可能反方意见",*['- '+x for x in pack.possible_counterarguments],"### 结尾收束建议",pack.ending_suggestion,"## 需作者拍板处",*['- '+x for x in pack.author_decision_points]])
    mp.write_text(md,encoding='utf-8'); tp.write_text(md,encoding='utf-8')
    _log('build',{'candidate_id':pack.candidate_id,'topic':pack.basic_info['content_type'],'status':pack.status})

def _load_inputs()->list[str|dict]:
    fixture=json.loads((BASE_DIR/'tests/fixtures/scan_inputs.json').read_text(encoding='utf-8')).get('items',[])
    manual_path=DATA_DIR/'raw'/'manual_inputs.json'
    manual=json.loads(manual_path.read_text(encoding='utf-8')).get('items',[]) if manual_path.exists() else []
    return fixture+manual

def run_scan()->dict[str,str]:
    ensure_directories(); ts=_tag(); items=_load_inputs(); records=[]; cards=[]
    for raw in items:
        n=build_news_item(raw); c=evaluate_candidate(n); t=_topic(n,c)
        records.append({'news_item':asdict(n),'candidate':asdict(c),'topic_card':t.to_dict()}); cards.append(t)
    grouped=_merge(cards)
    cp=OUTPUT_DIR/'json'/f'candidates_{ts}.json'; cp.write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')
    tp=OUTPUT_DIR/'json'/f'topic_cards_{ts}.json'; payload=[x.to_dict() for x in grouped]; tp.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8'); (OUTPUT_DIR/'json'/'topic_cards_latest.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8')
    top=sorted(records,key=lambda r:r['candidate']['priority_score'],reverse=True)[:3]
    brief=['# 本轮更新简报','', '## 本轮最值得关注的3条']
    dash=['# 作者工作台','', '## 本轮最值得写的3条']
    for r in top:
        n,c,t=r['news_item'],r['candidate'],r['topic_card']; pref='长评' if c['priority_score']>=85 else '短评'
        brief += [f"- {n['title']}：为什么值得关注=来源与议题延展性；建议评论方向=制度后果"]
        dash += [f"- {n['title']}",f"  - 建议切入点：{_planning(NewsItem(**n))['possible_angle']}",f"  - 对应 topic card：{t['topic_name']}",f"  - 推荐优先级：{c['priority_score']}",f"  - 建议写作长度：{pref}"]
    bp=OUTPUT_DIR/'briefs'/f'briefs_{ts}.md'; bp.write_text('\n'.join(brief),encoding='utf-8')
    dp=OUTPUT_DIR/'briefs'/f'writer_dashboard_{ts}.md'; dp.write_text('\n'.join(dash),encoding='utf-8')
    return {'brief':str(bp),'candidates':str(cp),'topics':str(tp),'dashboard':str(dp),'count':str(len(records))}

def run_weekly_review()->Path:
    ensure_directories();
    cand=sorted((OUTPUT_DIR/'json').glob('candidates_*.json'), key=lambda p:p.stat().st_mtime, reverse=True)
    topics=sorted((OUTPUT_DIR/'json').glob('topic_cards_*.json'), key=lambda p:p.stat().st_mtime, reverse=True)
    if not cand or not topics: run_scan(); cand=sorted((OUTPUT_DIR/'json').glob('candidates_*.json'), key=lambda p:p.stat().st_mtime, reverse=True); topics=sorted((OUTPUT_DIR/'json').glob('topic_cards_*.json'), key=lambda p:p.stat().st_mtime, reverse=True)
    records=json.loads(cand[0].read_text(encoding='utf-8')); tps=json.loads(topics[0].read_text(encoding='utf-8'))
    top3=tps[:3]
    lines=['# 周度专题简报','', '## 本周最值得关注的3个AI+教育议题']
    for t in top3:
        lines += [f"### {t['topic_name']}",f"- 为什么值得持续观察：{t.get('watch_reason','长期影响教育系统配置')}","- 可延展的评论方向：从制度后果、实践摩擦与教育公平展开。","- 关联条目："]
        rel=set(t.get('related_items',[]))
        for r in records:
            n=r['news_item']
            if n['id'] in rel: lines.append(f"  - {n['title']} ({n['content_type']})")
    rec=sorted(records,key=lambda r:r['candidate']['priority_score'],reverse=True)[0]
    lines += ['', '## 本周最建议下笔的一篇评论', f"- 推荐条目：{rec['news_item']['title']}", '- 推荐理由：来源可信、议题延展性强、可形成稳定主判断。', '- 建议标题：AI进入课堂：真正要回答的不是效率，而是教育目的', '- 建议结构：事实锚点 -> 机制分析 -> 风险与反方 -> 主判断收束']
    out=OUTPUT_DIR/'briefs'/f'weekly_{_tag()}.md'; out.write_text('\n'.join(lines),encoding='utf-8')
    _log('weekly',{'recommended_topic':rec['topic_card']['topic_name'],'recommended_news_id':rec['news_item']['id']})
    return out
