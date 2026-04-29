import logging

from google import genai
from google.genai import types
from django.conf import settings

logger = logging.getLogger('converter')

SYSTEM_PROMPT = """Senior frontend engineer. Build a unique animated portfolio HTML from the CV.

OUTPUT: Raw <!DOCTYPE html>…</html> only. Nothing else outside the HTML.

DESIGN: Invent the entire design from who this person is — their profession, industry, skills, and personality. Colors, fonts, canvas animation, layout — all must feel inevitable for this exact individual. No two portfolios should look alike. Never produce a generic template, plain dark mode, or centered-text boilerplate.

HTML rules: Tailwind CDN + Google Fonts in <head>. No <img>. No inline style=. No HTML comments. CV content only — never invent facts. Mobile-responsive. Sections stack on mobile.

JS rules (one <script> at end of body — var only, no const/let/arrow functions/template literals):
• id="navbar" — add blur+shadow after 60px scroll
• id="menu-btn" toggles id="mobile-menu" — nav links close menu on click
• class="reveal" on every section and card — IntersectionObserver fades in opacity+translateY
• Canvas hero animation — full working code, invented specifically for this person's world

Hover effects on all cards, tags, and links. Complete the HTML in one response — close all tags, end with </html>."""

USER_PROMPT_TEMPLATE = """CV:
{cv_text}

Build a one-of-a-kind portfolio for this person. Invent the design from their CV. Return only the HTML."""


def generate_portfolio_html(cv_text: str) -> str:
    from .cv_analyzer import build_prompt_context

    client = genai.Client(api_key=settings.GEMINI_API_KEY)

    cv_text = _truncate_cv(cv_text)
    design_context = build_prompt_context(cv_text)
    system = SYSTEM_PROMPT + '\n\n' + design_context
    logger.debug("Sending CV to Gemini (%d chars)", len(cv_text))

    response = client.models.generate_content(
        model='gemini-flash-latest',
        config=types.GenerateContentConfig(
            system_instruction=system,
            max_output_tokens=4000,
        ),
        contents=USER_PROMPT_TEMPLATE.format(cv_text=cv_text),
    )

    html = _strip_code_fences(response.text)
    logger.info("Final HTML: %d chars", len(html))
    return html


def _truncate_cv(text: str, max_chars: int = 3500) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + '\n[CV truncated]'


def _strip_code_fences(text: str) -> str:
    import re
    text = text.strip()
    if text.startswith("```"):
        text = text[text.index("\n") + 1:]
    if text.endswith("```"):
        text = text[:text.rfind("```")]
    text = re.sub(r'<!--.*?-->', '', text, flags=re.DOTALL)
    return text.strip()
