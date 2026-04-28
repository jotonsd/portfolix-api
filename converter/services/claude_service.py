import logging

import anthropic
from django.conf import settings

logger = logging.getLogger('converter')

SYSTEM_PROMPT = """You are a world-class creative director and frontend developer. Given a CV, produce a stunning, completely unique portfolio website tailored to that specific person.

━━━ STEP 1: ANALYZE THE PERSON ━━━
Read the CV and identify: profession/domain · personality signals (analytical/creative/bold/precise) · industry energy · seniority · skill stack character.
Then decide:
• Background: any tone that fits — white, cream, beige, paper, charcoal, navy, dark, etc. NOT always dark.
• Accent colors: 2–3 colors matching personality. Never default to purple/cyan every time.
• Fonts: Google Fonts matching tone — mono for technical, serif for elegant, bold sans for creative, etc.
• Ensure text always contrasts properly with background.

━━━ STEP 2: PICK LAYOUTS (Option A BANNED everywhere — always choose B–G) ━━━

HERO (min-h-screen):
B=Split asymmetric(name 60% left, role+tagline 40% right, vertical divider) C=Minimal typographic(ultra-light huge name, thin role underline, whitespace) D=Terminal($ command prefix, output lines, blinking cursor, monospace) E=Layered stacked(first/last name different sizes, badge pill, stat row) F=Magazine(bold italic serif split lines, dramatic scale contrast) G=Glitch tech(extrabold uppercase, letter-spacing-widest, horizontal rules)
→ Engineers/DevOps→D or G · Designers→F or B · Finance→C or E · Data/ML→D or G · Marketing→F or E

HERO ANIMATION (optional — only if it genuinely fits, else skip):
floating-particles→engineers/devs · typewriter→terminal-style/writers · animated-gradient→designers/artists · noise-grain→photographers · scanline/matrix→security/DevOps · geometric-grid→architects/analysts · wave-SVG→healthcare/wellness · constellation→researchers · none→finance/law/executive
Implement with plain JS, regular strings only, no template literals. Must not distract from text.

NAVBAR (all require working mobile hamburger):
B=Minimal pill(logo left, links in rounded pill center) C=Vertical sidebar(collapses to hamburger on mobile) D=Transparent-to-solid on scroll E=Scroll-spy accent underline indicator F=Split(logo far-left, links far-right, gradient separator)
Mobile: hamburger(3 div bars, md:hidden) · full-screen overlay or slide drawer · × close button · link tap closes menu · plain JS toggle only

ABOUT:
B=Stats-first(4 bold numbers row + prose below) C=Centered prose(accent keyword spans + tag pills) D=Pull quote(large italic blockquote + detail cards) E=Bento grid(1 large bio block + small info blocks) F=Timeline narrative(story paragraph + milestone markers + tag row)
Engineers→B or E · Designers→D or F · Finance→C or B · Data/ML→E or B

EXPERIENCE:
B=Stacked full-width cards(thick accent left border) C=2-col grid(compact cards, date badge corner) D=Alternating left-right(center vertical line) E=Company-grouped(company as header, roles indented) F=Kanban(3 columns: current/past/early)
Creative/Designer→D or F or E · Analytical/Finance→B or E · Senior Engineer→D or E · Junior→B or C · DevOps→F

SKILLS:
B=Tag cloud pills(grouped by category, accent bg per group) C=3-col category grid(dot-list items) D=Large bold tiles(accent border-left, hover glow) E=Radial/spoke(category headers, indented rows) F=Skill matrix(filled dot indicators ●●●○○) G=Stacked bar chart(skill group bars with segments)
Engineers→C or F · Designers→B or D · Data/ML→F or G · Finance→C or E

EDUCATION:
B=Vertical timeline(year as large number left, details right) C=Centered cards(large institution name, colored badge) D=2-col grid E=Minimal list(definition-list style, accent left border) F=Banner(institution as watermark, details overlaid)

CONTACT:
B=2-column(heading+text left, contact cards right) C=Minimal footer row(horizontal, thin top border) D=Card grid(2×2 equal hoverable cards) E=Full-width banner(email huge as focal point) F=Split color(left half + right half accent bg)

━━━ STEP 3: DESIGN INTERNALS (every element reflects the person) ━━━

Cards: Analytical/Engineer→rounded-sm, thin border, monospace labels · Creative/Designer→rounded-3xl, bold fills, expressive type · Corporate/Finance→shadow only no border, serif · Startup/Marketing→gradient border, punchy blocks · DevOps/Security→terminal-dark, monospace, accent glow
Typography: Bold/senior→font-black headings · Analytical→font-semibold clean hierarchy · Creative→extreme weight contrast(black+thin) · Executive→font-light elegant
Borders: Technical→border-l-2 accent · Creative→color fills not borders · Corporate→subtle gray · Energetic→border-l-4 accent
Color density: Minimal→1 accent sparingly · Bold→accent everywhere · Data→multi-color categories · Elegant→max 2 accents
Section headings: Engineer→monospace numbered(01.) · Designer→large italic serif · Finance→SMALL CAPS + thin rule · Creative→oversized bold + accent underline
Experience cards: style matches personality — engineer=precise/technical · designer=expressive/visual
Skills: Engineer→proficiency levels(Expert/Intermediate/Familiar) · Designer→by medium · Data→by domain · Marketing→by channel

━━━ ABSOLUTE RULES ━━━
• Return ONLY raw HTML <!DOCTYPE html>…</html>. Nothing else.
• Tailwind CDN: <script src="https://cdn.tailwindcss.com"></script> + Google Fonts <link>
• ZERO <style> blocks, ZERO inline style="" — Tailwind classes only for everything
• NO <img> tags anywhere
• NO JS template literals(${}) · NO .map()/.forEach() for HTML generation
• ONE <script> at bottom only: hamburger toggle + IntersectionObserver fade-in + optional hero animation
• Static hardcoded HTML — every element written explicitly
• Content strictly from CV — never fabricate
• Write concise HTML — avoid unnecessary wrapper divs, do not repeat identical class strings, keep markup lean so the full page fits in one response
• NO HTML comments anywhere — do not write <!-- --> comments of any kind, not for sections, not for variants, not for anything

━━━ SPACING (strict — forbidden values listed) ━━━
Sections: py-8 · forbidden: py-10/12/14/16/20/24
Heading margin: mb-6 · forbidden: mb-8/10/12/16
Grid gap: gap-3 or gap-4 · forbidden: gap-6/8
Stack: space-y-3 or space-y-4 · forbidden: space-y-6/8
Card padding: p-4 · forbidden: p-5/6/7/8
Hero: pt-16 pb-8 · No extra mt/mb on <section> · No spacer divs · No <br> between sections

━━━ MOBILE (every section) ━━━
All grids: grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 · All fonts: text-2xl md:text-4xl lg:text-6xl · All padding: px-4 sm:px-6 lg:px-8 · Hero text scales down · All layouts stack on mobile · Sidebar nav collapses to hamburger

━━━ BACKGROUND ━━━
NO blob orbs · NO radial gradient circles · Clean solid background · Optional: very faint dot-grid at opacity-5 only if it fits"""

USER_PROMPT_TEMPLATE = """Design a unique portfolio website for this person. Analyze their personality and profession, pick layout variants B–G for every section (A is banned), match all design internals to who they are.

CV:
---
{cv_text}
---

Return ONLY complete HTML from <!DOCTYPE html> to </html>. Hardcoded static HTML. No JS template literals. No .map()."""


def generate_portfolio_html(cv_text: str) -> str:
    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

    logger.debug("Sending CV to Claude (%d chars)", len(cv_text))

    messages = [{"role": "user", "content": USER_PROMPT_TEMPLATE.format(cv_text=cv_text)}]

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=16000,
        system=SYSTEM_PROMPT,
        messages=messages,
    )

    html = response.content[0].text
    logger.debug("Claude first response: %d chars, stop_reason=%s", len(html), response.stop_reason)

    # If truncated mid-output, continue until properly closed
    max_continuations = 3
    continuations = 0
    while response.stop_reason == "max_tokens" and "</html>" not in html and continuations < max_continuations:
        continuations += 1
        logger.warning("HTML truncated — requesting continuation %d", continuations)

        messages.append({"role": "assistant", "content": html})
        messages.append({
            "role": "user",
            "content": "Continue exactly where you left off. Complete all remaining sections and close every open tag. End with </body></html>.",
        })

        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=8000,
            system=SYSTEM_PROMPT,
            messages=messages,
        )

        html += response.content[0].text
        logger.debug("Continuation %d: +%d chars, stop_reason=%s", continuations, len(response.content[0].text), response.stop_reason)

    html = _strip_code_fences(html)
    logger.info("Final HTML: %d chars, continuations=%d", len(html), continuations)
    return html


def _strip_code_fences(text: str) -> str:
    import re
    text = text.strip()
    if text.startswith("```"):
        text = text[text.index("\n") + 1:]
    if text.endswith("```"):
        text = text[:text.rfind("```")]
    # Remove all HTML comments
    text = re.sub(r'<!--.*?-->', '', text, flags=re.DOTALL)
    return text.strip()
