"""Shared concise bullet style for Daily summaries."""
import re


def nominal_summary(text: str) -> str:
    # Process sentence and triangle boundaries separately; preserve decimals.
    parts = re.split(r'(△|(?<=[다음함됨임])[.!?]\s+)', str(text))
    output = []
    for part in parts:
        if not part or part == '△':
            output.append(part)
            continue
        if re.fullmatch(r'[.!?]\s+', part):
            output.append(' · ')
            continue
        clause = part.strip().rstrip('.。!?')
        clause = re.sub(r'는 내용$', '', clause)
        replacements = (
            ('결정되지 않았다', '미결정'), ('결정되지 않았음', '미결정'),
            ('밝혔다', '발표'), ('밝힘', '발표'), ('말했다', '언급'),
            ('늘었다', '증가'), ('늘어났다', '증가'), ('줄었다', '감소'),
            ('올랐다', '상승'), ('내렸다', '하락'), ('어려워짐', '어려움'),
            ('했다고', ''), ('한다고', ''), ('했습니다', ''), ('하였다', ''),
            ('했다', ''), ('합니다', ''), ('한다', ''), ('됐음', ''),
            ('됐다', ''), ('되었다', ''), ('된다', ''), ('됨', ''), ('함', ''),
        )
        for suffix, replacement in replacements:
            if clause.endswith(suffix):
                clause = clause[:-len(suffix)] + replacement
                break
        output.append(clause)
    result = re.sub(r'\s*·\s*(?=△)', ' ', ''.join(output))
    return re.sub(r'\s*△', ' △', result).strip()
