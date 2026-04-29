import re
import logging
from datetime import datetime

logger = logging.getLogger('converter')

# ── Profession keywords ───────────────────────────────────────────────────
_PROF_KW = {
    'security': [
        'security engineer', 'cybersecurity', 'penetration tester', 'pentest',
        'ethical hacker', 'soc analyst', 'incident response', 'malware analyst',
        'forensics', 'vulnerability researcher', 'red team', 'blue team',
        'oscp', 'cissp', 'ceh', 'metasploit', 'nmap', 'burp suite', 'siem',
        'threat intelligence', 'exploit', 'firewall', 'zero trust',
    ],
    'data': [
        'data scientist', 'data engineer', 'data analyst', 'ml engineer',
        'machine learning', 'ai engineer', 'deep learning', 'nlp engineer',
        'computer vision', 'research scientist', 'tensorflow', 'pytorch',
        'scikit-learn', 'sklearn', 'pandas', 'spark', 'hadoop', 'etl',
        'tableau', 'power bi', 'looker', 'dbt', 'airflow', 'statistics',
    ],
    'designer': [
        'ux designer', 'ui designer', 'product designer', 'visual designer',
        'graphic designer', 'interaction designer', 'design lead', 'design director',
        'figma', 'sketch', 'adobe xd', 'photoshop', 'illustrator', 'indesign',
        'motion designer', 'brand designer', 'design system', 'user research',
        'wireframing', 'prototyping', 'usability testing',
    ],
    'devops': [
        'devops engineer', 'site reliability', 'sre', 'platform engineer',
        'cloud engineer', 'infrastructure engineer', 'systems engineer',
        'kubernetes', 'docker', 'terraform', 'ansible', 'jenkins', 'gitlab ci',
        'github actions', 'aws', 'azure', 'gcp', 'helm', 'prometheus', 'grafana',
        'linux', 'bash scripting', 'ci/cd', 'infrastructure as code',
    ],
    'mobile': [
        'ios developer', 'android developer', 'mobile developer', 'flutter developer',
        'react native developer', 'swift', 'kotlin', 'objective-c', 'xamarin',
        'xcode', 'android studio', 'mobile app', 'swiftui', 'jetpack compose',
    ],
    'finance': [
        'financial analyst', 'investment banker', 'portfolio manager', 'quant',
        'quantitative analyst', 'risk analyst', 'trader', 'accountant', 'auditor',
        'cfa', 'cpa', 'frm', 'bloomberg', 'equity research', 'hedge fund',
        'private equity', 'venture capital', 'treasury', 'tax consultant',
    ],
    'manager': [
        'engineering manager', 'product manager', 'project manager', 'program manager',
        'scrum master', 'agile coach', 'cto', 'ceo', 'vp of engineering',
        'director of engineering', 'head of product', 'head of engineering',
        'chief technology officer', 'tech lead', 'team lead', 'delivery manager',
    ],
    'developer': [
        'software engineer', 'software developer', 'fullstack', 'full-stack',
        'backend engineer', 'frontend engineer', 'web developer', 'api engineer',
        'javascript', 'typescript', 'react', 'vue', 'angular', 'node.js',
        'python', 'django', 'fastapi', 'java', 'spring boot', 'golang',
        'rust', 'php', 'laravel', 'ruby on rails', 'graphql', 'microservices',
    ],
}

# ── Seniority keywords ────────────────────────────────────────────────────
_SENIORITY_KW = [
    ('executive', ['chief ', 'cto', 'ceo', 'coo', 'cpo', 'svp', 'evp']),
    ('director',  ['director', 'vp of', 'vice president', 'head of']),
    ('lead',      ['principal', 'staff engineer', 'architect', 'tech lead', 'team lead', 'lead ']),
    ('senior',    ['senior ', 'sr.', 'sr ', 'senior-']),
    ('junior',    ['junior ', 'jr.', 'jr ', 'associate ', 'entry level', 'entry-level']),
    ('intern',    ['intern', 'trainee', 'apprentice']),
]

# ── Industry keywords ─────────────────────────────────────────────────────
_INDUSTRY_KW = {
    'fintech':      ['bank', 'fintech', 'payment', 'stripe', 'paypal', 'trading', 'crypto', 'blockchain', 'lending', 'insurance'],
    'healthcare':   ['health', 'medical', 'hospital', 'pharma', 'biotech', 'clinical', 'epic', 'ehr'],
    'gaming':       ['game', 'gaming', 'unity', 'unreal', 'game engine', 'steam', 'roblox'],
    'e-commerce':   ['e-commerce', 'ecommerce', 'shopify', 'amazon', 'marketplace', 'retail tech'],
    'enterprise':   ['ibm', 'oracle', 'sap', 'salesforce', 'enterprise software', 'b2b saas'],
    'startup':      ['startup', 'seed stage', 'series a', 'series b', 'early-stage', 'vc-backed'],
    'consulting':   ['consulting', 'consultancy', 'accenture', 'deloitte', 'mckinsey', 'pwc', 'kpmg'],
    'adtech':       ['advertising', 'ad tech', 'marketing tech', 'martech', 'programmatic'],
    'edtech':       ['education', 'edtech', 'e-learning', 'lms', 'coursera', 'udemy'],
}

# ── Skill lists per profession (for top-skill extraction) ─────────────────
_SKILL_POOLS = {
    'security':  ['python', 'bash', 'metasploit', 'nmap', 'burp suite', 'wireshark', 'splunk', 'qradar', 'kali linux', 'ida pro', 'ghidra', 'oscp', 'cissp'],
    'data':      ['python', 'sql', 'tensorflow', 'pytorch', 'spark', 'pandas', 'numpy', 'scikit-learn', 'airflow', 'dbt', 'tableau', 'power bi', 'r', 'hadoop'],
    'designer':  ['figma', 'sketch', 'adobe xd', 'photoshop', 'illustrator', 'indesign', 'principle', 'framer', 'invision', 'zeplin', 'webflow'],
    'devops':    ['kubernetes', 'docker', 'terraform', 'ansible', 'aws', 'azure', 'gcp', 'jenkins', 'gitlab ci', 'helm', 'prometheus', 'grafana', 'linux', 'bash'],
    'mobile':    ['swift', 'kotlin', 'flutter', 'react native', 'swiftui', 'jetpack compose', 'objective-c', 'xcode', 'android studio', 'firebase'],
    'finance':   ['python', 'excel', 'vba', 'bloomberg', 'sql', 'r', 'matlab', 'tableau', 'power bi', 'dcf', 'financial modeling'],
    'manager':   ['agile', 'scrum', 'jira', 'confluence', 'okrs', 'roadmapping', 'stakeholder management', 'data-driven'],
    'developer': ['javascript', 'typescript', 'python', 'react', 'node.js', 'postgresql', 'redis', 'docker', 'aws', 'graphql', 'java', 'go', 'rust'],
}

# ── Design briefs per profession ──────────────────────────────────────────
_DESIGN_BRIEFS = {
    'security': {
        'aesthetic':   'terminal hacker — encrypted text, hex patterns, matrix-like data streams, dark as void',
        'colors':      'pure black or #000300 background, electric green (#00ff41) or crimson red accent — nothing soft, nothing warm',
        'typography':  'monospace throughout — Share Tech Mono, Fira Code, or Courier Prime — terminal authenticity',
        'hero_animation': 'matrix character rain falling across the canvas, or binary hex streams — raw, menacing, precise',
        'mood':        'intense, zero-trust, paranoid-precise — the aesthetic of someone who lives in the shadows and owns them',
    },
    'data': {
        'aesthetic':   'data visualization — flowing sine waves, scatter plot particles, live neural network connections',
        'colors':      'deep dark navy (#020d0e) or teal-black background, emerald (#10b981) + electric blue (#3b82f6) accents — cold intelligence',
        'typography':  'Space Mono or IBM Plex Mono for headings + Inter for body — analytical with clean readability',
        'hero_animation': 'animated sine waves flowing at different frequencies across the canvas, or floating data points connecting like a live scatter plot',
        'mood':        'curious, pattern-obsessed, insight-driven — data is poetry and this person speaks it fluently',
    },
    'designer': {
        'aesthetic':   'bold sensory — morphing gradient blobs, organic forms, Dribbble-quality visual weight, color as emotion',
        'colors':      'warm dark background (#0a0006), orange (#f97316) + hot pink/magenta (#ec4899) — creative fire, nothing technical or cold',
        'typography':  'expressive serif for headings (Playfair Display, Cormorant Garamond) + geometric humanist for body (DM Sans, Nunito)',
        'hero_animation': 'floating radial gradient orbs drifting slowly across the canvas — pure color and form as living aesthetic',
        'mood':        'sensory, intentional, obsessively beautiful — every pixel is a conscious decision, form and function inseparable',
    },
    'devops': {
        'aesthetic':   'infrastructure topology — hexagonal node grids, CLI-inspired layouts, Kubernetes cluster diagrams as art',
        'colors':      'deep dark navy (#020c18), sky blue (#0ea5e9) + slate grey accents — cloud precision, industrial cool',
        'typography':  'Space Mono or JetBrains Mono for headings + Inter for body — efficient, no-nonsense, CLI-native',
        'hero_animation': 'hexagonal grid pulsing with wave propagation from center, or interconnected nodes like a live service mesh topology',
        'mood':        'reliable, always-on, zero-downtime mindset — the page should feel like uptime is 99.99%',
    },
    'mobile': {
        'aesthetic':   'app-native — layered translucent cards, device-frame inspired sections, smooth gesture-like transitions',
        'colors':      'deep purple-black (#06040e), vivid purple (#8b5cf6) + hot pink (#ec4899) — modern app store energy',
        'typography':  'Nunito or Space Grotesk — rounded, friendly, tactile — reads like a premium app UI',
        'hero_animation': 'concentric expanding rings pulsing from center like a tap/ripple gesture — distinctly mobile',
        'mood':        'polished, tactile, gesture-driven — designed for thumbs and eyes, every interaction intentional',
    },
    'finance': {
        'aesthetic':   'precision finance — Bloomberg terminal gravitas, subtle ruled grid lines, structured typographic hierarchy',
        'colors':      'deep navy (#020818) or near-black background, gold (#d4a574) + silver/slate (#94a3b8) — authority, wealth, trust',
        'typography':  'Cormorant Garamond or EB Garamond for headings — old money gravitas + Source Sans 3 for body — clarity at scale',
        'hero_animation': 'slow animated precision grid lines shifting subtly, or a minimal chart-line drawing itself — controlled, not chaotic',
        'mood':        'authoritative, measured, high-trust — the page should feel like a pitch deck from Goldman Sachs',
    },
    'manager': {
        'aesthetic':   'executive presence — bold hierarchy, strategic whitespace, leadership visible in structure and scale',
        'colors':      'dark charcoal (#090909) or deep navy, gold (#fbbf24) + warm white accents — commanding, decisive, trustworthy',
        'typography':  'Raleway or Montserrat heavy weights for headings + Lato for body — board-room authority',
        'hero_animation': 'slow precision grid lines or a minimal subtle particle drift — controlled, deliberate, nothing chaotic',
        'mood':        'strategic, decisive, high-trust — the page should feel like a C-suite brief or an annual report cover',
    },
    'developer': {
        'aesthetic':   'code-native dark mode — syntax-texture backgrounds, browser DevTools aesthetic, dependency graph as art',
        'colors':      'very deep dark (#04040e), indigo (#6366f1) + electric cyan (#22d3ee) accents — canonical dev dark mode',
        'typography':  'JetBrains Mono or Fira Code for headings + Inter for body — readable at depth, technically beautiful',
        'hero_animation': 'particle network — nodes drifting and connecting with weighted lines, like a live call graph or dependency tree',
        'mood':        'thoughtful, craft-obsessed, systematic — code is the medium, quality is the religion',
    },
}


# ── Public API ────────────────────────────────────────────────────────────

def build_prompt_context(cv_text: str) -> str:
    analysis = _analyze(cv_text)
    context  = _format_brief(analysis)
    logger.debug(
        'CV brief: profession=%s seniority=%s industry=%s skills=%s',
        analysis['profession'], analysis['seniority'],
        analysis['industry'], analysis['top_skills'],
    )
    return context


# ── Internal analysis ─────────────────────────────────────────────────────

def _analyze(cv_text: str) -> dict:
    text = cv_text.lower()

    profession = _detect_profession(text)
    seniority  = _detect_seniority(text)
    industry   = _detect_industry(text)
    top_skills = _extract_skills(cv_text, profession)
    years_exp  = _estimate_years(cv_text)
    name, title = _extract_header(cv_text)

    return {
        'name':       name,
        'title':      title,
        'profession': profession,
        'seniority':  seniority,
        'industry':   industry,
        'top_skills': top_skills,
        'years_exp':  years_exp,
        'brief':      _DESIGN_BRIEFS[profession],
    }


def _detect_profession(text: str) -> str:
    scores = {prof: 0 for prof in _PROF_KW}
    for prof, keywords in _PROF_KW.items():
        for kw in keywords:
            if kw in text:
                scores[prof] += 1
    best = max(scores, key=lambda k: scores[k])
    return best if scores[best] > 0 else 'developer'


def _detect_seniority(text: str) -> str:
    for level, keywords in _SENIORITY_KW:
        if any(kw in text for kw in keywords):
            return level
    return 'mid'


def _detect_industry(text: str) -> str:
    for industry, keywords in _INDUSTRY_KW.items():
        if any(kw in text for kw in keywords):
            return industry
    return 'technology'


def _extract_skills(cv_text: str, profession: str) -> list:
    text  = cv_text.lower()
    pool  = _SKILL_POOLS.get(profession, _SKILL_POOLS['developer'])
    found = [skill for skill in pool if skill in text]

    # also pick up capitalised skills not in pool (words ≤ 20 chars near skill section)
    skill_section = re.search(
        r'(?:skills?|technologies|expertise|stack)[^\n]*\n(.*?)(?:\n[A-Z][^\n]{3,}\n|\Z)',
        cv_text, re.I | re.DOTALL,
    )
    if skill_section:
        extras = re.findall(r'[A-Za-z][A-Za-z0-9.+#\-]{1,19}', skill_section.group(1))
        for e in extras:
            if e.lower() not in found and len(e) > 2:
                found.append(e)

    return found[:8]


def _estimate_years(cv_text: str) -> int:
    current_year = datetime.now().year
    years = re.findall(r'\b(19[89]\d|20[0-2]\d)\b', cv_text)
    if not years:
        return 0
    years_int = [int(y) for y in years]
    earliest  = min(y for y in years_int if y <= current_year)
    span      = current_year - earliest
    return min(span, 40)


def _extract_header(cv_text: str) -> tuple:
    lines = [l.strip() for l in cv_text.splitlines() if l.strip()]
    email_re = re.compile(r'[\w.+-]+@[\w-]+\.[a-zA-Z]{2,}')
    phone_re = re.compile(r'\+?[\d][\d\s\-().]{6,14}[\d]')

    name, title = '', ''
    for line in lines[:6]:
        if email_re.search(line) or phone_re.search(line):
            continue
        if not name and 2 <= len(line.split()) <= 8 and len(line) < 70:
            name = line
        elif name and not title and len(line) < 90:
            title = line
            break
    return name, title


# ── Brief formatter ───────────────────────────────────────────────────────

def _format_brief(a: dict) -> str:
    b          = a['brief']
    seniority  = '' if a['seniority'] == 'mid' else a['seniority'].capitalize() + ' '
    role_label = a['title'] or (seniority + a['profession'].replace('_', ' ').title())
    exp_label  = f' with {a["years_exp"]}+ years of experience' if a['years_exp'] >= 1 else ''
    skills_str = ', '.join(a['top_skills']) if a['top_skills'] else 'not listed'
    industry   = a['industry']

    return (
        '── PRE-ANALYZED DESIGN BRIEF ──\n'
        f'Person:    {role_label}{exp_label}\n'
        f'Industry:  {industry}\n'
        f'Key stack: {skills_str}\n\n'
        'Use this brief to drive EVERY design decision:\n'
        f'• Aesthetic:        {b["aesthetic"]}\n'
        f'• Color palette:    {b["colors"]}\n'
        f'• Typography:       {b["typography"]}\n'
        f'• Hero animation:   {b["hero_animation"]}\n'
        f'• Emotional tone:   {b["mood"]}\n\n'
        'This brief is non-negotiable. Do not default to a generic dark theme.\n'
        'Every color, font, animation, and layout must feel inevitable for this exact person.'
    )
