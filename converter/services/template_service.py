import re
import logging
import html as html_lib

logger = logging.getLogger('converter')

# ── Regex ─────────────────────────────────────────────────────────────────
_EMAIL    = re.compile(r'[\w.+-]+@[\w-]+\.[a-zA-Z]{2,}')
_PHONE    = re.compile(r'\+?[\d][\d\s\-().]{6,14}[\d]')
_LINKEDIN = re.compile(r'(?:https?://)?(?:www\.)?linkedin\.com/in/([\w\-]+)', re.I)
_GITHUB   = re.compile(r'(?:https?://)?(?:www\.)?github\.com/([\w\-]+)', re.I)
_DATE     = re.compile(
    r'\b(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?'
    r'|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)'
    r'\.?\s*\d{4}'
    r'|\b\d{4}\s*[-–—]\s*(?:\d{4}|[Pp]resent|[Cc]urrent|[Nn]ow|[Oo]ngoing)'
    r'|\b\d{1,2}/\d{4}\b',
    re.I,
)
_SEC = {
    'summary': re.compile(
        r'^(summary|profile|about\s*me?|objective|overview|professional\s*summary)\s*:?\s*$', re.I),
    'experience': re.compile(
        r'^(work\s*experience|experience|employment|professional\s*experience'
        r'|career(?:\s*history)?|work\s*history)\s*:?\s*$', re.I),
    'skills': re.compile(
        r'^((?:technical\s*)?skills?|competencies|expertise|technologies'
        r'|tech(?:nical)?\s*stack|core\s*competencies|key\s*skills?)\s*:?\s*$', re.I),
    'education': re.compile(
        r'^(education|academic(?:\s*background)?|qualifications?)\s*:?\s*$', re.I),
    'projects': re.compile(
        r'^(?:(?:personal|key|notable|side)\s*)?projects?\s*:?\s*$', re.I),
    'certifications': re.compile(
        r'^(certifications?|certificates?|licenses?|credentials?)\s*:?\s*$', re.I),
    'languages': re.compile(
        r'^(languages?|spoken\s*languages?)\s*:?\s*$', re.I),
    'awards': re.compile(
        r'^(awards?|achievements?|honors?|recognition|accomplishments?)\s*:?\s*$', re.I),
}

# ── Profession keywords ───────────────────────────────────────────────────
_PROF_KW = {
    'security': [
        'security', 'cybersecurity', 'penetration', 'pentest', 'ethical hack',
        'soc analyst', 'incident response', 'malware', 'forensics', 'ctf',
        'vulnerability', 'exploit', 'firewall', 'siem', 'threat intelligence',
        'red team', 'blue team', 'oscp', 'cissp', 'ceh', 'nmap', 'metasploit',
    ],
    'data': [
        'data scientist', 'data engineer', 'data analyst', 'machine learning',
        'ml engineer', 'ai engineer', 'deep learning', 'neural network',
        'tensorflow', 'pytorch', 'sklearn', 'scikit', 'pandas', 'numpy',
        'tableau', 'power bi', 'analytics', 'statistics', 'data pipeline',
        'etl', 'spark', 'hadoop', 'big data', 'nlp', 'computer vision',
    ],
    'designer': [
        'ux designer', 'ui designer', 'user experience', 'user interface',
        'graphic designer', 'visual designer', 'product designer',
        'figma', 'sketch', 'adobe xd', 'photoshop', 'illustrator', 'indesign',
        'motion designer', 'branding', 'typography', 'interaction design',
        'design system', 'wireframe', 'prototype', 'user research',
    ],
    'devops': [
        'devops', 'site reliability', 'sre', 'platform engineer',
        'kubernetes', 'docker', 'terraform', 'ansible', 'jenkins',
        'ci/cd', 'aws', 'azure', 'gcp', 'google cloud', 'cloud engineer',
        'helm', 'prometheus', 'grafana', 'infrastructure', 'linux admin',
    ],
    'mobile': [
        'ios developer', 'android developer', 'mobile developer',
        'swift', 'kotlin', 'flutter', 'react native', 'xamarin',
        'xcode', 'android studio', 'objective-c', 'mobile app',
    ],
    'finance': [
        'finance', 'financial analyst', 'investment', 'banking',
        'accountant', 'accounting', 'cfa', 'cpa', 'trading', 'equity',
        'hedge fund', 'risk management', 'audit', 'tax', 'treasury',
        'valuation', 'portfolio manager', 'fintech analyst',
    ],
    'manager': [
        'product manager', 'project manager', 'engineering manager',
        'director of', 'vp of', 'head of', 'chief', 'cto', 'ceo', 'coo',
        'scrum master', 'agile coach', 'program manager', 'operations manager',
        'people manager', 'team lead', 'tech lead',
    ],
    'developer': [
        'software engineer', 'software developer', 'frontend', 'backend',
        'fullstack', 'full stack', 'full-stack', 'web developer', 'programmer',
        'javascript', 'typescript', 'react', 'vue', 'angular', 'node',
        'python developer', 'java developer', 'golang', 'rust developer',
        'php', 'ruby', 'django', 'flask', 'spring', 'microservices',
    ],
}

# ── Themes ────────────────────────────────────────────────────────────────
THEMES = {
    'developer': {
        'bg': '#04040e',
        'card_bg': 'rgba(13,13,40,0.85)',
        'a1': '#6366f1', 'a1_rgb': '99,102,241',
        'a2': '#22d3ee', 'a2_rgb': '34,211,238',
        'border': 'rgba(99,102,241,0.18)',
        'border_h': 'rgba(99,102,241,0.5)',
        'chip_from': 'rgba(99,102,241,0.18)', 'chip_to': 'rgba(34,211,238,0.1)',
        'font_h': 'JetBrains Mono', 'font_b': 'Inter',
        'font_url': 'Inter:wght@300;400;500;600;700;800;900&family=JetBrains+Mono:wght@400;500;700',
        'hero_anim': 'network',
        'greeting': "Hello, I'm",
        'scrollbar': '99,102,241',
        'tl_dot_from': '#6366f1', 'tl_dot_to': '#22d3ee',
    },
    'data': {
        'bg': '#020d0e',
        'card_bg': 'rgba(2,20,25,0.9)',
        'a1': '#10b981', 'a1_rgb': '16,185,129',
        'a2': '#3b82f6', 'a2_rgb': '59,130,246',
        'border': 'rgba(16,185,129,0.18)',
        'border_h': 'rgba(16,185,129,0.5)',
        'chip_from': 'rgba(16,185,129,0.15)', 'chip_to': 'rgba(59,130,246,0.1)',
        'font_h': 'Space Mono', 'font_b': 'Inter',
        'font_url': 'Inter:wght@300;400;500;600;700;800;900&family=Space+Mono:wght@400;700',
        'hero_anim': 'waves',
        'greeting': "Hi, I'm",
        'scrollbar': '16,185,129',
        'tl_dot_from': '#10b981', 'tl_dot_to': '#3b82f6',
    },
    'designer': {
        'bg': '#0a0006',
        'card_bg': 'rgba(20,5,15,0.9)',
        'a1': '#f97316', 'a1_rgb': '249,115,22',
        'a2': '#ec4899', 'a2_rgb': '236,72,153',
        'border': 'rgba(249,115,22,0.2)',
        'border_h': 'rgba(249,115,22,0.55)',
        'chip_from': 'rgba(249,115,22,0.15)', 'chip_to': 'rgba(236,72,153,0.1)',
        'font_h': 'Playfair Display', 'font_b': 'DM Sans',
        'font_url': 'DM+Sans:wght@300;400;500;600;700&family=Playfair+Display:wght@400;600;700;900',
        'hero_anim': 'orbs',
        'greeting': "Hey, I'm",
        'scrollbar': '249,115,22',
        'tl_dot_from': '#f97316', 'tl_dot_to': '#ec4899',
    },
    'security': {
        'bg': '#000300',
        'card_bg': 'rgba(0,15,5,0.95)',
        'a1': '#00ff41', 'a1_rgb': '0,255,65',
        'a2': '#00cc33', 'a2_rgb': '0,204,51',
        'border': 'rgba(0,255,65,0.2)',
        'border_h': 'rgba(0,255,65,0.55)',
        'chip_from': 'rgba(0,255,65,0.1)', 'chip_to': 'rgba(0,204,51,0.06)',
        'font_h': 'Share Tech Mono', 'font_b': 'Roboto Mono',
        'font_url': 'Roboto+Mono:wght@300;400;500;700&family=Share+Tech+Mono',
        'hero_anim': 'matrix',
        'greeting': 'ACCESS GRANTED —',
        'scrollbar': '0,255,65',
        'tl_dot_from': '#00ff41', 'tl_dot_to': '#00cc33',
    },
    'devops': {
        'bg': '#020c18',
        'card_bg': 'rgba(2,18,32,0.9)',
        'a1': '#0ea5e9', 'a1_rgb': '14,165,233',
        'a2': '#64748b', 'a2_rgb': '100,116,139',
        'border': 'rgba(14,165,233,0.18)',
        'border_h': 'rgba(14,165,233,0.5)',
        'chip_from': 'rgba(14,165,233,0.15)', 'chip_to': 'rgba(100,116,139,0.1)',
        'font_h': 'Space Mono', 'font_b': 'Inter',
        'font_url': 'Inter:wght@300;400;500;600;700;800;900&family=Space+Mono:wght@400;700',
        'hero_anim': 'hexgrid',
        'greeting': "Hello, I'm",
        'scrollbar': '14,165,233',
        'tl_dot_from': '#0ea5e9', 'tl_dot_to': '#64748b',
    },
    'finance': {
        'bg': '#020818',
        'card_bg': 'rgba(5,12,30,0.92)',
        'a1': '#d4a574', 'a1_rgb': '212,165,116',
        'a2': '#94a3b8', 'a2_rgb': '148,163,184',
        'border': 'rgba(212,165,116,0.2)',
        'border_h': 'rgba(212,165,116,0.5)',
        'chip_from': 'rgba(212,165,116,0.12)', 'chip_to': 'rgba(148,163,184,0.08)',
        'font_h': 'Cormorant Garamond', 'font_b': 'Source Sans 3',
        'font_url': 'Source+Sans+3:wght@300;400;500;600;700&family=Cormorant+Garamond:wght@400;600;700',
        'hero_anim': 'gridlines',
        'greeting': "I'm",
        'scrollbar': '212,165,116',
        'tl_dot_from': '#d4a574', 'tl_dot_to': '#94a3b8',
    },
    'mobile': {
        'bg': '#06040e',
        'card_bg': 'rgba(15,10,30,0.9)',
        'a1': '#8b5cf6', 'a1_rgb': '139,92,246',
        'a2': '#ec4899', 'a2_rgb': '236,72,153',
        'border': 'rgba(139,92,246,0.2)',
        'border_h': 'rgba(139,92,246,0.55)',
        'chip_from': 'rgba(139,92,246,0.18)', 'chip_to': 'rgba(236,72,153,0.1)',
        'font_h': 'Nunito', 'font_b': 'Space Grotesk',
        'font_url': 'Space+Grotesk:wght@300;400;500;600;700&family=Nunito:wght@400;600;700;800;900',
        'hero_anim': 'rings',
        'greeting': "Hey, I'm",
        'scrollbar': '139,92,246',
        'tl_dot_from': '#8b5cf6', 'tl_dot_to': '#ec4899',
    },
    'manager': {
        'bg': '#090909',
        'card_bg': 'rgba(18,18,18,0.92)',
        'a1': '#fbbf24', 'a1_rgb': '251,191,36',
        'a2': '#d1d5db', 'a2_rgb': '209,213,219',
        'border': 'rgba(251,191,36,0.18)',
        'border_h': 'rgba(251,191,36,0.5)',
        'chip_from': 'rgba(251,191,36,0.12)', 'chip_to': 'rgba(209,213,219,0.06)',
        'font_h': 'Raleway', 'font_b': 'Lato',
        'font_url': 'Lato:wght@300;400;700;900&family=Raleway:wght@400;500;600;700;800;900',
        'hero_anim': 'gridlines',
        'greeting': "I'm",
        'scrollbar': '251,191,36',
        'tl_dot_from': '#fbbf24', 'tl_dot_to': '#d1d5db',
    },
}


# ── Public API ────────────────────────────────────────────────────────────

def generate_portfolio_html(cv_text: str) -> str:
    data = parse_cv(cv_text)
    profession = _detect_profession(data, cv_text)
    theme = THEMES[profession]
    result = _build_html(data, theme)
    logger.info('Template portfolio generated: profession=%s chars=%d', profession, len(result))
    return result


# ── Profession detection ──────────────────────────────────────────────────

def _detect_profession(data: dict, cv_text: str) -> str:
    text_lower = cv_text.lower()
    scores = {prof: 0 for prof in _PROF_KW}

    for prof, keywords in _PROF_KW.items():
        for kw in keywords:
            if kw in text_lower:
                scores[prof] += 1

    # boost title match
    title_lower = (data.get('title') or '').lower()
    for prof, keywords in _PROF_KW.items():
        for kw in keywords:
            if kw in title_lower:
                scores[prof] += 3

    best = max(scores, key=lambda k: scores[k])
    if scores[best] == 0:
        best = 'developer'

    logger.debug('Profession scores: %s → %s', scores, best)
    return best


# ── CV Parser ─────────────────────────────────────────────────────────────

def parse_cv(cv_text: str) -> dict:
    lines = [l.strip() for l in cv_text.splitlines() if l.strip()]
    data = {
        'name': '', 'title': '', 'tagline': '',
        'contact': {},
        'summary': '', 'experience': [], 'skills': [],
        'education': [], 'projects': [], 'certifications': [],
        'languages': [], 'awards': [],
    }

    m = _EMAIL.search(cv_text)
    if m:
        data['contact']['email'] = m.group(0)
    m = _PHONE.search(cv_text)
    if m:
        p = m.group(0).strip()
        if 7 <= len(re.sub(r'\D', '', p)) <= 15:
            data['contact']['phone'] = p
    m = _LINKEDIN.search(cv_text)
    if m:
        data['contact']['linkedin'] = 'https://linkedin.com/in/' + m.group(1)
        data['contact']['linkedin_handle'] = m.group(1)
    m = _GITHUB.search(cv_text)
    if m:
        data['contact']['github'] = 'https://github.com/' + m.group(1)
        data['contact']['github_handle'] = m.group(1)

    bounds = []
    for i, line in enumerate(lines):
        for key, pat in _SEC.items():
            if pat.match(line):
                bounds.append((i, key))
                break

    first_sec = bounds[0][0] if bounds else len(lines)

    for line in lines[:min(6, first_sec)]:
        if _EMAIL.search(line) or _PHONE.search(line):
            continue
        if not data['name'] and 2 <= len(line.split()) <= 8 and len(line) < 70:
            data['name'] = line
        elif data['name'] and not data['title'] and len(line) < 90:
            data['title'] = line
            break

    for idx, (start, key) in enumerate(bounds):
        end = bounds[idx + 1][0] if idx + 1 < len(bounds) else len(lines)
        body = lines[start + 1:end]
        if key == 'summary':
            data['summary'] = ' '.join(body)
        elif key == 'experience':
            data['experience'] = _parse_experience(body)
        elif key == 'skills':
            data['skills'] = _parse_skills(body)
        elif key == 'education':
            data['education'] = _parse_education(body)
        elif key == 'projects':
            data['projects'] = _parse_projects(body)
        elif key == 'certifications':
            data['certifications'] = [l.lstrip('•-–*◦▸').strip() for l in body if l.strip()]
        elif key == 'languages':
            data['languages'] = [l.lstrip('•-–*◦').strip() for l in body if l.strip()]
        elif key == 'awards':
            data['awards'] = [l.lstrip('•-–*◦').strip() for l in body if l.strip()]

    if data['summary']:
        first = re.split(r'(?<=[.!?])\s', data['summary'], maxsplit=1)[0].strip()
        data['tagline'] = first if len(first) < 130 else data['title']
    else:
        data['tagline'] = data['title']

    logger.debug('Parsed CV: name=%r title=%r sections=%s',
                 data['name'], data['title'], [k for _, k in bounds])
    return data


def _parse_skills(lines):
    groups = []
    cur_cat, cur_items = '', []
    for line in lines:
        if not line:
            if cur_items:
                groups.append({'category': cur_cat, 'items': cur_items[:]})
                cur_cat, cur_items = '', []
            continue
        if ':' in line:
            pos = line.index(':')
            cat = line[:pos].strip().lstrip('•-–*◦')
            rest = line[pos + 1:].strip()
            if len(cat.split()) <= 5 and rest:
                if cur_items:
                    groups.append({'category': cur_cat, 'items': cur_items[:]})
                cur_cat = cat
                cur_items = [s.strip() for s in re.split(r'[,|;]', rest) if s.strip()]
                continue
        items = [s.strip() for s in re.split(r'[,|;•\-–]', line.lstrip('•-–*◦').strip())
                 if s.strip() and len(s.strip()) > 1]
        cur_items.extend(items)
    if cur_items:
        groups.append({'category': cur_cat, 'items': cur_items})
    return groups


def _parse_experience(lines):
    entries, cur = [], None
    for line in lines:
        if not line:
            continue
        is_bullet = line[:2].strip() in ('•', '-', '–', '*', '◦', '▸', '→')
        has_date = bool(_DATE.search(line))
        if has_date and not is_bullet:
            if cur:
                entries.append(cur)
            cur = {'title': '', 'company': '', 'date': '', 'bullets': []}
            dm = _DATE.search(line)
            cur['date'] = line[dm.start():].strip()
            before = line[:dm.start()].strip().strip('|–—- ')
            for sep in ('|', '–', '—', ' at ', ' @ ', ','):
                if sep in before:
                    parts = before.split(sep, 1)
                    cur['title'] = parts[0].strip()
                    cur['company'] = parts[1].strip() if len(parts) > 1 else ''
                    break
            else:
                cur['title'] = before
        elif cur is not None:
            if is_bullet:
                text = line.lstrip('•-–*◦▸→').strip()
                if text:
                    cur['bullets'].append(text)
            elif not cur['company']:
                cur['company'] = line
        elif not is_bullet:
            cur = {'title': line, 'company': '', 'date': '', 'bullets': []}
    if cur:
        entries.append(cur)
    return entries


def _parse_education(lines):
    entries, cur = [], None
    for line in lines:
        if not line:
            if cur:
                entries.append(cur)
                cur = None
            continue
        is_bullet = line[:2].strip() in ('•', '-', '–', '*')
        has_date = bool(_DATE.search(line))
        if has_date and not is_bullet:
            if cur:
                entries.append(cur)
            cur = {'degree': '', 'institution': '', 'date': '', 'details': []}
            dm = _DATE.search(line)
            cur['date'] = line[dm.start():].strip()
            before = line[:dm.start()].strip().strip('|–—-, ')
            for sep in ('|', '–', '—', ',', ' at '):
                if sep in before:
                    parts = before.split(sep, 1)
                    cur['degree'] = parts[0].strip()
                    cur['institution'] = parts[1].strip() if len(parts) > 1 else ''
                    break
            else:
                cur['degree'] = before
        elif cur is not None:
            if is_bullet:
                cur['details'].append(line.lstrip('•-–*').strip())
            elif not cur['institution']:
                cur['institution'] = line
        elif not is_bullet:
            cur = {'degree': line, 'institution': '', 'date': '', 'details': []}
    if cur:
        entries.append(cur)
    return entries


def _parse_projects(lines):
    entries, cur = [], None
    for line in lines:
        if not line:
            if cur:
                entries.append(cur)
                cur = None
            continue
        is_bullet = line[:2].strip() in ('•', '-', '–', '*', '◦', '▸')
        if not is_bullet and cur is None:
            cur = {'name': line, 'description': '', 'bullets': []}
        elif cur is not None:
            if is_bullet:
                cur['bullets'].append(line.lstrip('•-–*◦▸').strip())
            elif not cur['description']:
                cur['description'] = line
    if cur:
        entries.append(cur)
    return entries


# ── HTML helpers ──────────────────────────────────────────────────────────

def _e(s) -> str:
    return html_lib.escape(str(s), quote=True)


def _initials(name: str) -> str:
    parts = name.strip().split()
    if not parts:
        return 'P'
    return (parts[0][0] + (parts[-1][0] if len(parts) > 1 else '')).upper()


# ── Section builders (theme-aware) ────────────────────────────────────────

def _head(name: str, t: dict) -> str:
    title = _e(name) + ' — Portfolio' if name else 'Portfolio'
    a1, a1r = t['a1'], t['a1_rgb']
    a2 = t['a2']
    bg = t['bg']
    cb = t['card_bg']
    bdr = t['border']
    bdrh = t['border_h']
    cf = t['chip_from']
    ct = t['chip_to']
    fh, fb = t['font_h'], t['font_b']
    tdf, tdt = t['tl_dot_from'], t['tl_dot_to']

    return (
        '<!DOCTYPE html>\n<html lang="en" class="scroll-smooth">\n<head>\n'
        '<meta charset="UTF-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1.0">\n'
        '<title>' + title + '</title>\n'
        '<link rel="preconnect" href="https://fonts.googleapis.com">\n'
        '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n'
        '<link href="https://fonts.googleapis.com/css2?family=' + t['font_url'] + '&display=swap" rel="stylesheet">\n'
        '<script>tailwind={config:{theme:{extend:{fontFamily:{sans:["' + fb + '","sans-serif"],mono:["' + fh + '","monospace"]}}}}}</script>\n'
        '<script src="https://cdn.tailwindcss.com"></script>\n'
        '<style>\n'
        'body{background:' + bg + ';color:#f8fafc;font-family:"' + fb + '",sans-serif}\n'
        'h1,h2,h3,.font-heading{font-family:"' + fh + '",monospace}\n'
        '::-webkit-scrollbar{width:5px}\n'
        '::-webkit-scrollbar-track{background:' + bg + '}\n'
        '::-webkit-scrollbar-thumb{background:' + a1 + ';border-radius:3px}\n'
        '#hero-canvas{position:absolute;inset:0;width:100%;height:100%}\n'
        '.grad{background:linear-gradient(135deg,' + a1 + ',' + a2 + ');-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text}\n'
        '.card{background:' + cb + ';border:1px solid ' + bdr + ';backdrop-filter:blur(12px);transition:all .3s ease}\n'
        '.card:hover{border-color:' + bdrh + ';transform:translateY(-3px);box-shadow:0 12px 40px rgba(' + a1r + ',0.18)}\n'
        '.chip{background:linear-gradient(135deg,' + cf + ',' + ct + ');border:1px solid ' + bdr + ';transition:all .2s ease}\n'
        '.chip:hover{border-color:' + a1 + ';background:rgba(' + a1r + ',0.28)}\n'
        '.a1{color:' + a1 + '}.a2{color:' + a2 + '}\n'
        '.reveal{opacity:0;transform:translateY(28px);transition:opacity .65s ease,transform .65s ease}\n'
        '.reveal.visible{opacity:1;transform:translateY(0)}\n'
        '.tl-line{border-left:2px solid rgba(' + a1r + ',0.25)}\n'
        '.tl-dot{background:linear-gradient(135deg,' + tdf + ',' + tdt + ');flex-shrink:0}\n'
        '#navbar.scrolled{background:rgba(' + _hex_to_rgb(bg) + ',0.96)!important;backdrop-filter:blur(20px);box-shadow:0 1px 0 rgba(' + a1r + ',0.2)}\n'
        '@keyframes float{0%,100%{transform:translateY(0)}50%{transform:translateY(-7px)}}\n'
        '@keyframes glow{0%,100%{opacity:.4}50%{opacity:1}}\n'
        '.float{animation:float 4s ease-in-out infinite}\n'
        '.glow{animation:glow 2.5s ease-in-out infinite}\n'
        '</style>\n</head>\n<body class="antialiased">\n'
    )


def _hex_to_rgb(hex_color: str) -> str:
    h = hex_color.lstrip('#')
    if len(h) == 6:
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        return f'{r},{g},{b}'
    return '0,0,0'


def _navbar(name: str, nav_items: list, t: dict) -> str:
    display = _e(name) if name else 'Portfolio'
    initials = _e(_initials(name)) if name else 'P'
    a1, a2 = t['a1'], t['a2']

    desktop = ''.join(
        '<a href="#' + href + '" class="text-slate-400 hover:text-white text-sm font-medium transition-colors duration-200" style="--tw-text-opacity:1">'
        + _e(label) + '</a>'
        for href, label in nav_items
    )
    mobile = ''.join(
        '<a href="#' + href + '" class="block px-4 py-3 text-slate-300 hover:text-white rounded-lg transition-colors">'
        + _e(label) + '</a>'
        for href, label in nav_items
    )
    return (
        '<nav id="navbar" class="fixed top-0 left-0 right-0 z-50 px-6 py-4 transition-all duration-300">\n'
        '<div class="max-w-6xl mx-auto flex items-center justify-between">\n'
        '<a href="#" class="flex items-center gap-3">'
        '<div class="w-9 h-9 rounded-xl flex items-center justify-center text-white font-mono font-bold text-sm" style="background:linear-gradient(135deg,' + a1 + ',' + a2 + ')">' + initials + '</div>'
        '<span class="font-mono text-white font-semibold text-sm hidden sm:block">' + display + '</span>'
        '</a>\n'
        '<div class="hidden md:flex items-center gap-7">' + desktop + '</div>\n'
        '<button id="menu-btn" class="md:hidden flex flex-col gap-1.5 p-2 rounded-lg hover:bg-white/5 transition-colors">'
        '<span class="block w-5 h-0.5 bg-slate-300"></span>'
        '<span class="block w-5 h-0.5 bg-slate-300"></span>'
        '<span class="block w-4 h-0.5 bg-slate-300"></span>'
        '</button>\n'
        '</div>\n'
        '<div id="mobile-menu" class="hidden md:hidden mt-3 rounded-2xl border p-3" style="background:rgba(10,10,20,0.97);border-color:' + t['border'] + '">'
        + mobile + '</div>\n'
        '</nav>\n'
    )


def _hero(data: dict, t: dict) -> str:
    name    = _e(data['name'])    if data['name']    else 'Professional'
    title   = _e(data['title'])   if data['title']   else ''
    tagline = _e(data['tagline']) if data['tagline'] else ''
    contact = data['contact']
    a1, a2  = t['a1'], t['a2']
    greeting = _e(t['greeting'])

    buttons = ''
    if 'github' in contact:
        buttons += (
            '<a href="' + _e(contact['github']) + '" target="_blank" rel="noopener" '
            'class="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl border text-slate-300 hover:text-white text-sm font-medium transition-all duration-200" '
            'style="border-color:' + t['border'] + '" '
            'onmouseover="this.style.borderColor=\'' + a1 + '\';this.style.background=\'rgba(' + t['a1_rgb'] + ',0.12)\'" '
            'onmouseout="this.style.borderColor=\'' + t['border'] + '\';this.style.background=\'\'">'
            '<svg class="w-4 h-4" fill="currentColor" viewBox="0 0 24 24"><path d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.531 1.032 1.531 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z"/></svg>'
            'GitHub</a>'
        )
    if 'linkedin' in contact:
        buttons += (
            '<a href="' + _e(contact['linkedin']) + '" target="_blank" rel="noopener" '
            'class="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl border text-slate-300 hover:text-white text-sm font-medium transition-all duration-200" '
            'style="border-color:' + t['border'] + '" '
            'onmouseover="this.style.borderColor=\'' + a1 + '\';this.style.background=\'rgba(' + t['a1_rgb'] + ',0.12)\'" '
            'onmouseout="this.style.borderColor=\'' + t['border'] + '\';this.style.background=\'\'">'
            '<svg class="w-4 h-4" fill="currentColor" viewBox="0 0 24 24"><path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433a2.062 2.062 0 01-2.063-2.065 2.064 2.064 0 112.063 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z"/></svg>'
            'LinkedIn</a>'
        )
    if 'email' in contact:
        buttons += (
            '<a href="mailto:' + _e(contact['email']) + '" '
            'class="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl text-white text-sm font-semibold transition-all duration-200 hover:opacity-90 hover:scale-105 shadow-lg" '
            'style="background:linear-gradient(135deg,' + a1 + ',' + a2 + ');box-shadow:0 4px 20px rgba(' + t['a1_rgb'] + ',0.35)">'
            '<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"/></svg>'
            'Get in Touch</a>'
        )

    subtitle = ('<p class="font-mono text-lg md:text-xl font-medium mb-6 a2">' + title + '</p>') if title else ''
    tag_line = ('<p class="text-slate-400 text-base md:text-lg max-w-2xl mx-auto mb-10 leading-relaxed">' + tagline + '</p>') if tagline else ''

    return (
        '<section id="hero" class="relative min-h-screen flex items-center justify-center overflow-hidden">\n'
        '<canvas id="hero-canvas"></canvas>\n'
        '<div class="absolute inset-0 pointer-events-none" style="background:linear-gradient(to bottom,transparent 60%,' + t['bg'] + ')"></div>\n'
        '<div class="relative z-10 text-center px-6 max-w-4xl mx-auto py-32">\n'
        '<p class="font-mono text-sm tracking-[0.25em] uppercase mb-5 glow a1">' + greeting + '</p>\n'
        '<h1 class="font-heading text-5xl sm:text-6xl md:text-7xl font-bold mb-4 grad leading-tight">' + name + '</h1>\n'
        + subtitle + tag_line +
        '<div class="flex items-center justify-center gap-3 flex-wrap">' + buttons + '</div>\n'
        '</div>\n'
        '<div class="absolute bottom-8 left-1/2 -translate-x-1/2 flex flex-col items-center gap-1 float">'
        '<span class="text-xs font-mono a1" style="opacity:.5">scroll</span>'
        '<svg class="w-4 h-4 a1" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"/></svg>'
        '</div>\n'
        '</section>\n'
    )


def _about(summary: str, t: dict) -> str:
    return (
        '<section id="about" class="py-24 px-6">\n'
        '<div class="max-w-4xl mx-auto reveal">\n'
        '<p class="font-mono text-sm tracking-widest uppercase mb-3 a1">About Me</p>\n'
        '<h2 class="font-heading text-3xl md:text-4xl font-bold text-white mb-10">Who I Am</h2>\n'
        '<div class="card rounded-2xl p-8 md:p-10" style="border-left:4px solid ' + t['a1'] + '">\n'
        '<p class="text-slate-300 text-base md:text-lg leading-relaxed">' + _e(summary) + '</p>\n'
        '</div>\n</div>\n</section>\n'
    )


def _skills(skills: list, t: dict) -> str:
    if not skills:
        return ''
    cards = ''
    for g in skills:
        cat = _e(g['category']) if g['category'] else 'Skills'
        chips = ''.join(
            '<span class="chip px-3 py-1.5 rounded-lg text-slate-300 text-xs font-medium">' + _e(item) + '</span>'
            for item in g['items'] if item
        )
        if not chips:
            continue
        cards += (
            '<div class="card rounded-2xl p-6 reveal">\n'
            '<h3 class="font-mono text-xs font-semibold uppercase tracking-wider mb-4 a1">' + cat + '</h3>\n'
            '<div class="flex flex-wrap gap-2">' + chips + '</div>\n'
            '</div>\n'
        )
    if not cards:
        return ''
    return (
        '<section id="skills" class="py-24 px-6" style="background:linear-gradient(to bottom,transparent,' + t['bg'] + '22,' + t['bg'] + ')">\n'
        '<div class="max-w-6xl mx-auto">\n'
        '<p class="font-mono text-sm tracking-widest uppercase mb-3 a1">What I Know</p>\n'
        '<h2 class="font-heading text-3xl md:text-4xl font-bold text-white mb-10">Skills &amp; Technologies</h2>\n'
        '<div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">' + cards + '</div>\n'
        '</div>\n</section>\n'
    )


def _experience(experience: list, t: dict) -> str:
    if not experience:
        return ''
    items = ''
    for job in experience:
        title   = _e(job['title'])   if job['title']   else 'Role'
        company = _e(job['company']) if job['company'] else ''
        date    = _e(job['date'])    if job['date']    else ''
        bullets = ''.join('<li class="text-slate-400 text-sm leading-relaxed">' + _e(b) + '</li>' for b in job['bullets'])
        date_badge   = ('<span class="font-mono text-xs px-3 py-1 rounded-full a2" style="background:rgba(' + t['a2_rgb'] + ',0.1);border:1px solid rgba(' + t['a2_rgb'] + ',0.25)">' + date + '</span>') if date else ''
        company_line = ('<p class="font-medium mt-1 a1">' + company + '</p>') if company else ''
        bullets_block = ('<ul class="mt-4 space-y-2 list-disc list-inside">' + bullets + '</ul>') if bullets else ''
        items += (
            '<div class="relative pl-8 tl-line ml-4 pb-10 last:pb-0 reveal">\n'
            '<div class="tl-dot absolute -left-2 top-1.5 w-4 h-4 rounded-full"></div>\n'
            '<div class="card rounded-2xl p-6">\n'
            '<div class="flex flex-wrap items-start justify-between gap-3 mb-1">\n'
            '<h3 class="text-white font-semibold text-lg">' + title + '</h3>' + date_badge + '\n'
            '</div>' + company_line + bullets_block + '\n'
            '</div>\n</div>\n'
        )
    return (
        '<section id="experience" class="py-24 px-6">\n'
        '<div class="max-w-4xl mx-auto">\n'
        '<p class="font-mono text-sm tracking-widest uppercase mb-3 a1">Where I\'ve Worked</p>\n'
        '<h2 class="font-heading text-3xl md:text-4xl font-bold text-white mb-12">Experience</h2>\n'
        + items + '</div>\n</section>\n'
    )


def _projects(projects: list, t: dict) -> str:
    if not projects:
        return ''
    cards = ''
    for p in projects:
        name = _e(p['name']) if p['name'] else 'Project'
        desc = _e(p['description']) if p['description'] else ''
        bullets = ''.join('<li class="text-slate-400 text-sm">' + _e(b) + '</li>' for b in p['bullets'][:4])
        desc_block    = ('<p class="text-slate-400 text-sm mt-2 leading-relaxed">' + desc + '</p>') if desc else ''
        bullets_block = ('<ul class="mt-3 space-y-1.5 list-disc list-inside">' + bullets + '</ul>') if bullets else ''
        cards += (
            '<div class="card rounded-2xl p-6 reveal">\n'
            '<div class="flex items-center gap-3 mb-3">\n'
            '<div class="w-8 h-8 rounded-lg flex items-center justify-center" style="background:rgba(' + t['a1_rgb'] + ',0.15);border:1px solid rgba(' + t['a1_rgb'] + ',0.3)">'
            '<svg class="w-4 h-4 a1" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4"/></svg>'
            '</div><h3 class="text-white font-semibold">' + name + '</h3>\n'
            '</div>' + desc_block + bullets_block + '\n'
            '</div>\n'
        )
    return (
        '<section id="projects" class="py-24 px-6" style="background:linear-gradient(to bottom,transparent,' + t['bg'] + '22,' + t['bg'] + ')">\n'
        '<div class="max-w-6xl mx-auto">\n'
        '<p class="font-mono text-sm tracking-widest uppercase mb-3 a1">What I\'ve Built</p>\n'
        '<h2 class="font-heading text-3xl md:text-4xl font-bold text-white mb-10">Projects</h2>\n'
        '<div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">' + cards + '</div>\n'
        '</div>\n</section>\n'
    )


def _education(education: list, t: dict) -> str:
    if not education:
        return ''
    cards = ''
    for edu in education:
        degree  = _e(edu['degree'])      if edu['degree']      else 'Degree'
        inst    = _e(edu['institution']) if edu['institution'] else ''
        date    = _e(edu['date'])        if edu['date']        else ''
        details = ''.join('<li class="text-slate-500 text-xs">' + _e(d) + '</li>' for d in edu.get('details', [])[:3])
        inst_b   = ('<p class="text-sm font-medium mt-1 a1">' + inst + '</p>') if inst else ''
        date_b   = ('<p class="font-mono text-xs mt-2 a2">' + date + '</p>') if date else ''
        det_b    = ('<ul class="mt-3 space-y-1 list-disc list-inside">' + details + '</ul>') if details else ''
        cards += (
            '<div class="card rounded-2xl p-6 reveal">\n'
            '<div class="w-10 h-10 rounded-xl flex items-center justify-center mb-4" style="background:rgba(' + t['a1_rgb'] + ',0.12);border:1px solid rgba(' + t['a1_rgb'] + ',0.25)">'
            '<svg class="w-5 h-5 a1" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 14l9-5-9-5-9 5 9 5z"/><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 14l6.16-3.422a12.083 12.083 0 01.665 6.479A11.952 11.952 0 0112 20.055a11.952 11.952 0 00-6.824-2.998 12.078 12.078 0 01.665-6.479L12 14z"/></svg>'
            '</div>\n'
            '<h3 class="text-white font-semibold text-base leading-snug">' + degree + '</h3>' + inst_b + date_b + det_b + '\n'
            '</div>\n'
        )
    return (
        '<section id="education" class="py-24 px-6">\n'
        '<div class="max-w-6xl mx-auto">\n'
        '<p class="font-mono text-sm tracking-widest uppercase mb-3 a1">Academic Background</p>\n'
        '<h2 class="font-heading text-3xl md:text-4xl font-bold text-white mb-10">Education</h2>\n'
        '<div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">' + cards + '</div>\n'
        '</div>\n</section>\n'
    )


def _extras(items: list, t: dict) -> str:  # noqa: ARG001
    if not items:
        return ''
    chips = ''.join(
        '<div class="chip px-4 py-2.5 rounded-xl text-slate-300 text-sm flex items-center gap-2">'
        '<span>' + icon + '</span><span>' + _e(text) + '</span></div>'
        for icon, text in items if text
    )
    return (
        '<section class="py-16 px-6">\n'
        '<div class="max-w-6xl mx-auto reveal">\n'
        '<h2 class="font-heading text-2xl font-bold text-white mb-8">Additional</h2>\n'
        '<div class="flex flex-wrap gap-3">' + chips + '</div>\n'
        '</div>\n</section>\n'
    )


def _contact(contact: dict, t: dict) -> str:
    a1r = t['a1_rgb']
    links = ''
    if 'email' in contact:
        links += (
            '<a href="mailto:' + _e(contact['email']) + '" class="flex flex-col items-center gap-3 card rounded-2xl p-6 group">'
            '<div class="w-12 h-12 rounded-xl flex items-center justify-center transition-colors" style="background:rgba(' + a1r + ',0.12);border:1px solid rgba(' + a1r + ',0.25)">'
            '<svg class="w-5 h-5 a1" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"/></svg>'
            '</div><span class="text-slate-300 text-sm font-medium group-hover:text-white transition-colors">' + _e(contact['email']) + '</span></a>'
        )
    if 'linkedin' in contact:
        handle = _e(contact.get('linkedin_handle', 'LinkedIn'))
        links += (
            '<a href="' + _e(contact['linkedin']) + '" target="_blank" rel="noopener" class="flex flex-col items-center gap-3 card rounded-2xl p-6 group">'
            '<div class="w-12 h-12 rounded-xl flex items-center justify-center transition-colors" style="background:rgba(' + a1r + ',0.12);border:1px solid rgba(' + a1r + ',0.25)">'
            '<svg class="w-5 h-5 a1" fill="currentColor" viewBox="0 0 24 24"><path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433a2.062 2.062 0 01-2.063-2.065 2.064 2.064 0 112.063 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z"/></svg>'
            '</div><span class="text-slate-300 text-sm font-medium group-hover:text-white transition-colors">/in/' + handle + '</span></a>'
        )
    if 'github' in contact:
        handle = _e(contact.get('github_handle', 'GitHub'))
        links += (
            '<a href="' + _e(contact['github']) + '" target="_blank" rel="noopener" class="flex flex-col items-center gap-3 card rounded-2xl p-6 group">'
            '<div class="w-12 h-12 rounded-xl flex items-center justify-center transition-colors" style="background:rgba(' + a1r + ',0.12);border:1px solid rgba(' + a1r + ',0.25)">'
            '<svg class="w-5 h-5 a1" fill="currentColor" viewBox="0 0 24 24"><path d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.531 1.032 1.531 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z"/></svg>'
            '</div><span class="text-slate-300 text-sm font-medium group-hover:text-white transition-colors">/' + handle + '</span></a>'
        )
    if 'phone' in contact:
        links += (
            '<a href="tel:' + _e(contact['phone']) + '" class="flex flex-col items-center gap-3 card rounded-2xl p-6 group">'
            '<div class="w-12 h-12 rounded-xl flex items-center justify-center transition-colors" style="background:rgba(' + a1r + ',0.12);border:1px solid rgba(' + a1r + ',0.25)">'
            '<svg class="w-5 h-5 a1" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 5a2 2 0 012-2h3.28a1 1 0 01.948.684l1.498 4.493a1 1 0 01-.502 1.21l-2.257 1.13a11.042 11.042 0 005.516 5.516l1.13-2.257a1 1 0 011.21-.502l4.493 1.498a1 1 0 01.684.949V19a2 2 0 01-2 2h-1C9.716 21 3 14.284 3 6V5z"/></svg>'
            '</div><span class="text-slate-300 text-sm font-medium group-hover:text-white transition-colors">' + _e(contact['phone']) + '</span></a>'
        )
    if not links:
        links = '<p class="text-slate-500 col-span-full text-center">No contact details found.</p>'
    return (
        '<section id="contact" class="py-24 px-6">\n'
        '<div class="max-w-4xl mx-auto text-center reveal">\n'
        '<p class="font-mono text-sm tracking-widest uppercase mb-3 a1">Get In Touch</p>\n'
        '<h2 class="font-heading text-3xl md:text-4xl font-bold text-white mb-4">Contact</h2>\n'
        '<p class="text-slate-400 mb-12 max-w-lg mx-auto">Feel free to reach out for opportunities or just a friendly hello.</p>\n'
        '<div class="grid grid-cols-2 sm:grid-cols-4 gap-4">' + links + '</div>\n'
        '</div>\n</section>\n'
    )


def _footer(name: str, t: dict) -> str:
    display = _e(name) if name else 'Portfolio'
    return (
        '<footer class="py-8 px-6" style="border-top:1px solid rgba(' + t['a1_rgb'] + ',0.1)">\n'
        '<div class="max-w-6xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-3">\n'
        '<span class="font-mono text-slate-500 text-sm">' + display + '</span>\n'
        '<span class="text-slate-600 text-xs">Built with Portfolix</span>\n'
        '</div>\n</footer>\n'
    )


# ── Hero animations (per profession) ─────────────────────────────────────

def _anim_network(t: dict) -> str:
    r, g, b = t['a1_rgb'].split(',')
    return (
        'var canvas=document.getElementById("hero-canvas");'
        'if(canvas){'
        'var ctx=canvas.getContext("2d");'
        'var pts=[];var N=72;var maxD=145;'
        'function resize(){canvas.width=canvas.offsetWidth;canvas.height=canvas.offsetHeight;}'
        'function Pt(){this.x=Math.random()*canvas.width;this.y=Math.random()*canvas.height;'
        'this.vx=(Math.random()-.5)*.55;this.vy=(Math.random()-.5)*.55;'
        'this.r=Math.random()*2+1;this.a=Math.random()*.55+.15;}'
        'for(var i=0;i<N;i++)pts.push(new Pt());'
        'function draw(){'
        'ctx.clearRect(0,0,canvas.width,canvas.height);'
        'for(var i=0;i<pts.length;i++){'
        'var p=pts[i];p.x+=p.vx;p.y+=p.vy;'
        'if(p.x<0||p.x>canvas.width)p.vx*=-1;'
        'if(p.y<0||p.y>canvas.height)p.vy*=-1;'
        'ctx.beginPath();ctx.arc(p.x,p.y,p.r,0,Math.PI*2);'
        'ctx.fillStyle="rgba(' + r + ',' + g + ',' + b + ',"+p.a+")";ctx.fill();'
        'for(var j=i+1;j<pts.length;j++){'
        'var q=pts[j];var dx=p.x-q.x;var dy=p.y-q.y;var d=Math.sqrt(dx*dx+dy*dy);'
        'if(d<maxD){var op=(1-d/maxD)*.35;'
        'ctx.beginPath();ctx.moveTo(p.x,p.y);ctx.lineTo(q.x,q.y);'
        'ctx.strokeStyle="rgba(' + r + ',' + g + ',' + b + ',"+op+")";ctx.lineWidth=.7;ctx.stroke();}}}'
        'requestAnimationFrame(draw);}'
        'resize();window.addEventListener("resize",resize);draw();}'
    )


def _anim_waves(t: dict) -> str:
    r1, g1, b1 = t['a1_rgb'].split(',')
    r2, g2, b2 = t['a2_rgb'].split(',')
    return (
        'var canvas=document.getElementById("hero-canvas");'
        'if(canvas){'
        'var ctx=canvas.getContext("2d");var T=0;'
        'function resize(){canvas.width=canvas.offsetWidth;canvas.height=canvas.offsetHeight;}'
        'var waves=['
        '{r:' + r1 + ',g:' + g1 + ',b:' + b1 + ',a:.4,f:.018,amp:70,sp:.018,off:0},'
        '{r:' + r2 + ',g:' + g2 + ',b:' + b2 + ',a:.25,f:.013,amp:90,sp:.013,off:2},'
        '{r:' + r1 + ',g:' + g1 + ',b:' + b1 + ',a:.2,f:.025,amp:45,sp:.025,off:4}];'
        'function draw(){'
        'ctx.clearRect(0,0,canvas.width,canvas.height);'
        'for(var w=0;w<waves.length;w++){'
        'var wv=waves[w];ctx.beginPath();'
        'for(var x=0;x<=canvas.width;x++){'
        'var y=canvas.height/2+Math.sin(x*wv.f+T*wv.sp+wv.off)*wv.amp;'
        'if(x===0)ctx.moveTo(x,y);else ctx.lineTo(x,y);}'
        'ctx.strokeStyle="rgba("+wv.r+","+wv.g+","+wv.b+","+wv.a+")";ctx.lineWidth=1.5;ctx.stroke();}'
        'T++;requestAnimationFrame(draw);}'
        'resize();window.addEventListener("resize",resize);draw();}'
    )


def _anim_orbs(t: dict) -> str:
    r1, g1, b1 = t['a1_rgb'].split(',')
    r2, g2, b2 = t['a2_rgb'].split(',')
    return (
        'var canvas=document.getElementById("hero-canvas");'
        'if(canvas){'
        'var ctx=canvas.getContext("2d");'
        'function resize(){canvas.width=canvas.offsetWidth;canvas.height=canvas.offsetHeight;}'
        'var orbs=[];'
        'for(var i=0;i<7;i++){'
        'var isA=(i%2===0);'
        'orbs.push({x:Math.random()*1200,y:Math.random()*800,'
        'r:80+Math.random()*140,vx:(Math.random()-.5)*.35,vy:(Math.random()-.5)*.35,'
        'cr:isA?' + r1 + ':' + r2 + ',cg:isA?' + g1 + ':' + g2 + ',cb:isA?' + b1 + ':' + b2 + '});}'
        'function draw(){'
        'ctx.clearRect(0,0,canvas.width,canvas.height);'
        'for(var i=0;i<orbs.length;i++){'
        'var o=orbs[i];o.x+=o.vx;o.y+=o.vy;'
        'if(o.x<-o.r)o.x=canvas.width+o.r;'
        'if(o.x>canvas.width+o.r)o.x=-o.r;'
        'if(o.y<-o.r)o.y=canvas.height+o.r;'
        'if(o.y>canvas.height+o.r)o.y=-o.r;'
        'var g2=ctx.createRadialGradient(o.x,o.y,0,o.x,o.y,o.r);'
        'g2.addColorStop(0,"rgba("+o.cr+","+o.cg+","+o.cb+",.28)");'
        'g2.addColorStop(1,"transparent");'
        'ctx.beginPath();ctx.arc(o.x,o.y,o.r,0,Math.PI*2);'
        'ctx.fillStyle=g2;ctx.fill();}'
        'requestAnimationFrame(draw);}'
        'resize();window.addEventListener("resize",resize);draw();}'
    )


def _anim_matrix(t: dict) -> str:
    r, g, b = t['a1_rgb'].split(',')
    return (
        'var canvas=document.getElementById("hero-canvas");'
        'if(canvas){'
        'var ctx=canvas.getContext("2d");'
        'function resize(){canvas.width=canvas.offsetWidth;canvas.height=canvas.offsetHeight;'
        'drops=[];var cols=Math.floor(canvas.width/fs);'
        'for(var i=0;i<cols;i++)drops[i]=Math.random()*-100;}'
        'var fs=14;var drops=[];var chars="ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*<>/\\\\|";'
        'function draw(){'
        'ctx.fillStyle="rgba(0,3,0,.06)";ctx.fillRect(0,0,canvas.width,canvas.height);'
        'ctx.font=fs+"px monospace";'
        'for(var i=0;i<drops.length;i++){'
        'var c=chars[Math.floor(Math.random()*chars.length)];'
        'var a=.3+Math.random()*.7;'
        'ctx.fillStyle="rgba(' + r + ',' + g + ',' + b + ',"+a+")";'
        'ctx.fillText(c,i*fs,drops[i]*fs);'
        'if(drops[i]*fs>canvas.height&&Math.random()>.975)drops[i]=0;'
        'drops[i]++;}'
        'requestAnimationFrame(draw);}'
        'resize();window.addEventListener("resize",resize);draw();}'
    )


def _anim_hexgrid(t: dict) -> str:
    r, g, b = t['a1_rgb'].split(',')
    return (
        'var canvas=document.getElementById("hero-canvas");'
        'if(canvas){'
        'var ctx=canvas.getContext("2d");var ph=0;var hs=32;'
        'function resize(){canvas.width=canvas.offsetWidth;canvas.height=canvas.offsetHeight;}'
        'function hex(x,y,a){'
        'ctx.beginPath();'
        'for(var i=0;i<6;i++){'
        'var ang=Math.PI/180*(60*i-30);'
        'var hx=x+hs*Math.cos(ang);var hy=y+hs*Math.sin(ang);'
        'if(i===0)ctx.moveTo(hx,hy);else ctx.lineTo(hx,hy);}'
        'ctx.closePath();ctx.strokeStyle="rgba(' + r + ',' + g + ',' + b + ',"+a+")";ctx.lineWidth=.7;ctx.stroke();}'
        'function draw(){'
        'ctx.clearRect(0,0,canvas.width,canvas.height);ph+=.018;'
        'var hh=hs*Math.sqrt(3);'
        'var cols=Math.ceil(canvas.width/(hs*1.5))+2;'
        'var rows=Math.ceil(canvas.height/hh)+2;'
        'for(var c=-1;c<cols;c++){'
        'for(var r=-1;r<rows;r++){'
        'var x=c*hs*1.5;var y=r*hh+(c%2===0?0:hh/2);'
        'var d=Math.sqrt(Math.pow(x-canvas.width/2,2)+Math.pow(y-canvas.height/2,2));'
        'var a=(Math.sin(d*.007-ph)+1)/2*.25;'
        'hex(x,y,a);}}'
        'requestAnimationFrame(draw);}'
        'resize();window.addEventListener("resize",resize);draw();}'
    )


def _anim_gridlines(t: dict) -> str:
    r, g, b = t['a1_rgb'].split(',')
    return (
        'var canvas=document.getElementById("hero-canvas");'
        'if(canvas){'
        'var ctx=canvas.getContext("2d");var gt=0;'
        'function resize(){canvas.width=canvas.offsetWidth;canvas.height=canvas.offsetHeight;}'
        'function draw(){'
        'ctx.clearRect(0,0,canvas.width,canvas.height);gt+=.004;'
        'var sp=65;'
        'for(var x=0;x<canvas.width;x+=sp){'
        'var a=(Math.sin(x*.018+gt)+1)/2*.1;'
        'ctx.beginPath();ctx.moveTo(x,0);ctx.lineTo(x,canvas.height);'
        'ctx.strokeStyle="rgba(' + r + ',' + g + ',' + b + ',"+a+")";ctx.lineWidth=.6;ctx.stroke();}'
        'for(var y=0;y<canvas.height;y+=sp){'
        'var a2=(Math.sin(y*.018+gt)+1)/2*.1;'
        'ctx.beginPath();ctx.moveTo(0,y);ctx.lineTo(canvas.width,y);'
        'ctx.strokeStyle="rgba(' + r + ',' + g + ',' + b + ',"+a2+")";ctx.lineWidth=.6;ctx.stroke();}'
        'requestAnimationFrame(draw);}'
        'resize();window.addEventListener("resize",resize);draw();}'
    )


def _anim_rings(t: dict) -> str:
    r, g, b = t['a1_rgb'].split(',')
    r2, g2, b2 = t['a2_rgb'].split(',')
    return (
        'var canvas=document.getElementById("hero-canvas");'
        'if(canvas){'
        'var ctx=canvas.getContext("2d");var rings=[];var toggle=0;'
        'function resize(){canvas.width=canvas.offsetWidth;canvas.height=canvas.offsetHeight;}'
        'function addRing(){'
        'toggle=1-toggle;'
        'var cr=toggle===0?' + r + ':' + r2 + ';'
        'var cg=toggle===0?' + g + ':' + g2 + ';'
        'var cb=toggle===0?' + b + ':' + b2 + ';'
        'rings.push({x:canvas.width/2,y:canvas.height/2,r:0,'
        'max:Math.max(canvas.width,canvas.height)*.8,cr:cr,cg:cg,cb:cb});}'
        'setInterval(addRing,1800);addRing();'
        'function draw(){'
        'ctx.clearRect(0,0,canvas.width,canvas.height);'
        'for(var i=rings.length-1;i>=0;i--){'
        'var rg=rings[i];rg.r+=1.2;'
        'var a=.4*(1-rg.r/rg.max);'
        'ctx.beginPath();ctx.arc(rg.x,rg.y,rg.r,0,Math.PI*2);'
        'ctx.strokeStyle="rgba("+rg.cr+","+rg.cg+","+rg.cb+","+a+")";'
        'ctx.lineWidth=1.5;ctx.stroke();'
        'if(rg.r>rg.max)rings.splice(i,1);}'
        'requestAnimationFrame(draw);}'
        'resize();window.addEventListener("resize",resize);draw();}'
    )


_ANIM_FN = {
    'network':  _anim_network,
    'waves':    _anim_waves,
    'orbs':     _anim_orbs,
    'matrix':   _anim_matrix,
    'hexgrid':  _anim_hexgrid,
    'gridlines':_anim_gridlines,
    'rings':    _anim_rings,
}


def _scripts(t: dict) -> str:
    anim_fn = _ANIM_FN.get(t['hero_anim'], _anim_network)
    anim_js = anim_fn(t)

    return (
        '<script>\n'
        + anim_js + '\n'
        'var menuBtn=document.getElementById("menu-btn");'
        'var mobileMenu=document.getElementById("mobile-menu");'
        'if(menuBtn&&mobileMenu){'
        'menuBtn.addEventListener("click",function(){mobileMenu.classList.toggle("hidden");});'
        'var mls=mobileMenu.querySelectorAll("a");'
        'for(var i=0;i<mls.length;i++)mls[i].addEventListener("click",function(){mobileMenu.classList.add("hidden");});}'
        'var obs=new IntersectionObserver(function(entries){'
        'for(var i=0;i<entries.length;i++)if(entries[i].isIntersecting)entries[i].target.classList.add("visible");'
        '},{threshold:.08});'
        'var revs=document.querySelectorAll(".reveal");'
        'for(var i=0;i<revs.length;i++)obs.observe(revs[i]);'
        'window.addEventListener("scroll",function(){'
        'var nb=document.getElementById("navbar");if(!nb)return;'
        'if(window.scrollY>60)nb.classList.add("scrolled");else nb.classList.remove("scrolled");});'
        '\n</script>\n'
    )


# ── HTML assembler ────────────────────────────────────────────────────────

def _build_html(data: dict, t: dict) -> str:
    nav_items = []
    if data['summary']:    nav_items.append(('about',      'About'))
    if data['skills']:     nav_items.append(('skills',     'Skills'))
    if data['experience']: nav_items.append(('experience', 'Experience'))
    if data['projects']:   nav_items.append(('projects',   'Projects'))
    if data['education']:  nav_items.append(('education',  'Education'))
    nav_items.append(('contact', 'Contact'))

    extra_items = (
        [('\U0001f3c6', x) for x in data.get('certifications', [])] +
        [('\U0001f310', x) for x in data.get('languages', [])] +
        [('⭐', x)     for x in data.get('awards', [])]
    )

    parts = [_head(data['name'], t), _navbar(data['name'], nav_items, t), _hero(data, t)]
    if data['summary']:    parts.append(_about(data['summary'], t))
    if data['skills']:     parts.append(_skills(data['skills'], t))
    if data['experience']: parts.append(_experience(data['experience'], t))
    if data['projects']:   parts.append(_projects(data['projects'], t))
    if data['education']:  parts.append(_education(data['education'], t))
    if extra_items:        parts.append(_extras(extra_items, t))
    parts.append(_contact(data['contact'], t))
    parts.append(_footer(data['name'], t))
    parts.append(_scripts(t))
    parts.append('</body>\n</html>')
    return ''.join(parts)
