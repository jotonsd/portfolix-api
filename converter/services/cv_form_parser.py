import json
import logging
import re
import uuid

import anthropic
from django.conf import settings

logger = logging.getLogger('converter')

PARSE_PROMPT = """\
You are a CV parser. Extract all information from the CV text below and return it as a single JSON object.

Return ONLY valid JSON — no markdown, no explanation. Use this exact structure:

{
  "name": "Full Name",
  "title": "Job Title / Profession",
  "email": "email@example.com",
  "phone": "+1 234 567 890",
  "location": "City, Country",
  "website": "https://example.com or empty string",
  "linkedin": "username-only (strip https://linkedin.com/in/)",
  "github": "username-only (strip https://github.com/)",
  "sections": [
    {
      "id": "summary",
      "type": "summary",
      "icon": "👤",
      "label": "Professional Summary",
      "visible": true,
      "entries": [
        {"id": "sum_0", "visible": true, "title": "", "subtitle": "", "location": "", "startDate": "", "endDate": "", "current": false, "description": "Summary text here", "level": 0}
      ]
    },
    {
      "id": "experience",
      "type": "experience",
      "icon": "💼",
      "label": "Work Experience",
      "visible": true,
      "entries": [
        {"id": "exp_0", "visible": true, "title": "Job Title", "subtitle": "Company Name", "location": "City", "startDate": "Jan 2022", "endDate": "Present", "current": true, "description": "- Achievement one\\n- Achievement two", "level": 0}
      ]
    },
    {
      "id": "education",
      "type": "education",
      "icon": "🎓",
      "label": "Education",
      "visible": true,
      "entries": [
        {"id": "edu_0", "visible": true, "title": "Degree Name", "subtitle": "University Name", "location": "City", "startDate": "2018", "endDate": "2022", "current": false, "description": "", "level": 0}
      ]
    },
    {
      "id": "skills",
      "type": "skills",
      "icon": "⚡",
      "label": "Skills",
      "visible": true,
      "entries": [
        {"id": "sk_0", "visible": true, "title": "Skill Name", "subtitle": "", "location": "", "startDate": "", "endDate": "", "current": false, "description": "", "level": 0}
      ]
    }
  ]
}

Rules:
- Include only sections that actually appear in the CV (skip empty ones)
- For experience/education: one entry per job/degree
- For skills: one entry per skill, title = skill name
- For languages: type="languages", icon="🌐", one entry per language; level = 0-5 (0=unspecified, 1=beginner, 2=elementary, 3=intermediate, 4=advanced, 5=native/mother tongue)
- For certifications: type="certifications", icon="🏅"
- For projects: type="projects", icon="🚀"
- description fields: use plain text, separate bullet points with \\n
- linkedin/github: extract username only, not the full URL
- If a field is not present, use empty string ""
- current: true only if the person is still in that role (no end date or says "Present")
- Keep section order matching the CV

CV TEXT:
{cv_text}
"""


def parse_cv_to_form_data(cv_text: str) -> dict:
    prompt = PARSE_PROMPT.replace('{cv_text}', cv_text[:8000], 1)

    raw = ''
    if getattr(settings, 'AI_PROVIDER', 'gemini') == 'claude':
        raw = _parse_with_claude(prompt)
    else:
        raw = _parse_with_gemini(prompt)

    raw = _extract_json(raw)
    data = json.loads(raw)
    logger.debug("CV parsed successfully: name=%s sections=%d", data.get('name'), len(data.get('sections', [])))

    # Ensure every entry has all required fields and unique ids
    for s in data.get('sections', []):
        for i, e in enumerate(s.get('entries', [])):
            e.setdefault('id', f"{s['id']}_{i}")
            e.setdefault('visible', True)
            e.setdefault('title', '')
            e.setdefault('subtitle', '')
            e.setdefault('location', '')
            e.setdefault('startDate', '')
            e.setdefault('endDate', '')
            e.setdefault('current', False)
            e.setdefault('description', '')
            e.setdefault('level', 0)
        s.setdefault('visible', True)

    return data


def _parse_with_claude(prompt: str) -> str:
    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    msg = client.messages.create(
        model='claude-sonnet-4-6',
        max_tokens=4096,
        messages=[{'role': 'user', 'content': prompt}],
    )
    return msg.content[0].text.strip()


def _parse_with_gemini(prompt: str) -> str:
    from google import genai
    client = genai.Client(api_key=settings.GEMINI_API_KEY)
    response = client.models.generate_content(
        model='gemini-flash-latest',
        contents=prompt,
    )
    return response.text.strip()


def _extract_json(text: str) -> str:
    # Strip markdown code fences first
    text = re.sub(r'^```[a-zA-Z]*\n?', '', text.strip())
    text = re.sub(r'\n?```$', '', text.strip()).strip()
    # Find the outermost { ... } block to tolerate any surrounding text
    start = text.find('{')
    end = text.rfind('}')
    if start != -1 and end != -1 and end > start:
        return text[start:end + 1]
    return text
