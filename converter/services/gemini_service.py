import logging

from google import genai
from google.genai import types
from django.conf import settings

logger = logging.getLogger('converter')

SYSTEM_PROMPT = """You are an elite creative developer. Read the CV carefully and build a stunning, fully interactive portfolio website in a single HTML file.

Every design decision — color palette, typography, layout, animations, interactions — must be inspired by who this person is: their profession, industry, personality, and story. A chef, a data scientist, and a lawyer must look completely different.

Do NOT default to dark backgrounds. Choose colors that feel alive for this person — vibrant, warm, or bold. Light, gradient, or colorful backgrounds are encouraged.

STYLING: Use ONLY Tailwind CSS classes for all styling. Include the Tailwind CDN and a Google Font in <head>. Do NOT write any <style> tags or inline style= attributes anywhere in the HTML. Every visual style must come from Tailwind utility classes only.

HERO ANIMATION (required): The hero section must have a full-screen canvas animation deeply connected to who this person is. Rich, atmospheric, particle-based — dozens of shapes twinkling, raining, drifting, or floating. Think of a night sky full of sparkling stars — that same density and liveliness, but the shapes and behavior invented from the person's world:
- A developer → raining code characters
- A chef → rising steam or floating spice dots
- A designer → drifting glowing color orbs
- A marketer → rising signal ripple rings
Invent something original. Particle count 80–150. Each particle has its own speed, size, opacity, lifecycle. Written in plain JS (var only, no const/let/arrow functions/template literals) in one <script> at end of body.

Rules:
- Return raw HTML only. The very last characters you output MUST be </body></html>. You have 15000 tokens — use them, never stop early, never truncate.
- No invented facts. CV content only.
- Mobile responsive.
- Fully mobile responsive. Use Tailwind responsive prefixes (sm:, md:, lg:) throughout. On mobile: single column layout, stacked nav, readable font sizes, touch-friendly tap targets. Test every section mentally on a 375px screen.
- Navbar must match the overall design — same color palette, fonts, and personality as the rest of the site. It should feel like it belongs. Include a hamburger menu for mobile that toggles a full mobile nav. Navbar becomes solid/blurred on scroll.
- No <img> tags. No <style> tags. No inline style= attributes."""

USER_PROMPT_TEMPLATE = """CV:
{cv_text}

Study this person. Build a world-class portfolio — Tailwind only, rich hero canvas animation, colors and energy matching their field. End your response with </body></html>."""


def generate_portfolio_html(cv_text: str) -> str:
    client = genai.Client(api_key=settings.GEMINI_API_KEY)

    cv_text = _truncate_cv(cv_text)
    logger.debug("Sending CV to Gemini (%d chars)", len(cv_text))

    response = client.models.generate_content(
        model='gemini-flash-latest',
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            max_output_tokens=15000,
        ),
        contents=USER_PROMPT_TEMPLATE.format(cv_text=cv_text),
    )

    if not response.text:
        raise ValueError("Gemini returned empty response.")
    html = _strip_code_fences(response.text)
    html = _dedup_html(html)
    logger.info("Final HTML: %d chars", len(html))
    return html


def _dedup_html(html: str) -> str:
    second = html.lower().find('<!doctype', 10)
    if second != -1:
        html = html[:second].rstrip()
    return html


def _truncate_cv(text: str, max_chars: int = 6000) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + '\n[CV truncated]'


def _strip_code_fences(text: str) -> str:
    import re
    text = text.strip()
    text = re.sub(r'^```[^\n]*\n', '', text)
    text = re.sub(r'\n?```\s*$', '', text)
    text = re.sub(r'<!--.*?-->', '', text, flags=re.DOTALL)
    return text.strip()
