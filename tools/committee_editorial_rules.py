"""Conservative, source-only editorial fallback when the optional API is unavailable."""
import hashlib
import re
from difflib import SequenceMatcher

ALIASES = {
    'industry': r'산업통상자원중소벤처기업위원회|산업통상자원위원회|산중위|산자위',
    'climate_labor': r'기후에너지환경노동위원회|기후노동위|환경노동위원회|기노위|환노위',
    'finance': r'재정경제기획위원회|기획재정위원회|재경위|기재위',
}
MINISTRIES = {
    'industry': r'산업통상(?:자원)?부|산업부|산업장관|중소벤처기업부|중기부|중기장관',
    'climate_labor': r'기후에너지환경부|기후부|환경부|고용노동부|노동부|노동장관',
    'finance': r'기획재정부|재정경제부|기재부|재경부|경제부총리',
}
CATEGORY_PATTERNS = {
    '정유·유가/담합': r'정유|유가|휘발유|경유|석유제품|주유소',
    '석유화학': r'석유화학|나프타|에틸렌', '배터리': r'배터리|이차전지',
    'LNG·전력': r'LNG|액화천연가스|전력|전기요금', '도시가스': r'도시가스',
    '재생에너지·수소': r'재생에너지|수소|태양광|풍력',
    'E&P·해외자원개발': r'해외자원|대왕고래|석유개발|가스전',
    'SMR·신재생 원전(신사업)': r'SMR|소형모듈원전|소형 모듈 원전',
}


def noun_summary(title):
    """Keep the confirmed original headline; normalize only explicit endings."""
    value = re.sub(r'\s+', ' ', title).strip().rstrip('.… ')
    for marker in ['[종합]', '(종합)', '[속보]']:
        value = value.replace(marker, '').strip()
    endings = [('추진한다', '추진'), ('발표했다', '발표'), ('점검했다', '점검'),
               ('지원한다', '지원'), ('논의했다', '논의'), ('요구했다', '요구'),
               ('촉구했다', '촉구'), ('통과했다', '통과'), ('확대한다', '확대'),
               ('검토한다', '검토'), ('개최한다', '개최'), ('나선다', '추진')]
    for ending, replacement in endings:
        if value.endswith(ending):
            value = value[:-len(ending)] + replacement
            break
    # Attributed quotations are themselves confirmed statements; preserve the
    # quoted wording rather than inventing its policy consequences.
    if re.search(r'["”\']$', value):
        value += ' 발언'
    if value.endswith(('다', '했다', '내용')):
        return None
    return value


def classify(sources, roster):
    decisions, events = [], []
    for index, source in enumerate(sources):
        title, body = source['title'], source['body']
        context = title + '\n' + body[:2200]
        member_hits = []
        for member in roster:
            name = member['name']
            # A roster name alone is insufficient: require the member role in
            # the same clause, and prefer title/main-article attribution.
            if re.search(re.escape(name) + r'[^.。\n]{0,35}(?:의원|위원장|간사)', context):
                member_hits.append(member)
        title_ministries = [key for key, pattern in MINISTRIES.items() if re.search(pattern, title)]
        explicit = [key for key, pattern in ALIASES.items() if re.search(pattern, context)]
        member_owners = {m['committee'] for m in member_hits}
        role, members, owner, basis = 'policy', [], None, ''
        if len(title_ministries) == 1 and re.search(r'장관|차관|후보자', title):
            owner, role = explicit[0] if len(explicit) == 1 else title_ministries[0], 'minister'
            basis = '제목에 명시된 장관·차관 자격 및 소관 부처'
        elif len(member_owners) == 1:
            owner = next(iter(member_owners))
            members, role = [m['name'] for m in member_hits], 'member'
            basis = '본문 의원·위원장·간사 발언 표시 및 roster 소속 대조: ' + ', '.join(members)
        elif len(explicit) == 1:
            owner, basis = explicit[0], '본문에 명시된 심사·소관 상임위'
        elif not member_hits:
            ministries = [key for key, pattern in MINISTRIES.items() if re.search(pattern, title + body[:600])]
            if len(ministries) == 1 and re.search(r'정책|법안|지원|대책|규제|예산|장관|차관|청문|국감|국정감사|계획|세제', context):
                owner, basis = ministries[0], '제목·본문 주된 부처 및 명시된 정책·법안·현안'
        if owner not in ALIASES:
            decisions.append(dict(index=index, include=False, reason='상임위·발언자·소관 직접성 또는 단일 배정 근거 불충분'))
            continue
        if '최고가격제' in title and not members:
            owner = 'finance' if re.search(r'피해액|재정\s*부담', title) else 'industry'
            basis += '; 최고가격제 정산·보상/피해액·재정부담 주된 제목 맥락 구분'
        summary = noun_summary(title)
        if not summary:
            decisions.append(dict(index=index, include=False, reason='원문 제목의 명사형 요약을 안전하게 구성하지 못해 편집 검토 필요'))
            continue
        categories = [name for name, pattern in CATEGORY_PATTERNS.items() if re.search(pattern, title)]
        normalized = re.sub(r'[^가-힣A-Za-z0-9]', '', title)
        event_id = None
        for previous, previous_owner, previous_members, previous_event in events:
            if owner == previous_owner and members == previous_members and SequenceMatcher(None, normalized, previous).ratio() >= .78:
                event_id = previous_event
                break
        event_id = event_id or hashlib.sha256(normalized.encode()).hexdigest()[:20]
        events.append((normalized, owner, members, event_id))
        legislation = 3 if re.search(r'본회의.{0,20}통과|의결|법안.{0,20}통과', context) else 2 if re.search(r'법안|발의|법률', context) else 0
        decisions.append(dict(index=index, include=True, summary=summary, event_id=event_id,
                              committees=[owner], members=members, speaker_role=role, committee_reason=basis,
                              categories=categories, category_reason='원문 제목에 직접 명시된 우선산업' if categories else '',
                              importance=dict(legislation=legislation, impact=2, speaker=3 if role == 'minister' else 2 if role == 'member' else 1)))
    return {'decisions': decisions}
