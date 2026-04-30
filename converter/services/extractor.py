import base64
import io
import logging

import fitz  # PyMuPDF
from django.conf import settings
from docx import Document

logger = logging.getLogger('converter')

SUPPORTED_EXTENSIONS = {
    'pdf':  'application/pdf',
    'doc':  'application/msword',
    'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'jpg':  'image/jpeg',
    'jpeg': 'image/jpeg',
    'png':  'image/png',
    'webp': 'image/webp',
}

IMAGE_EXTENSIONS = {'jpg', 'jpeg', 'png', 'webp'}
DOC_EXTENSIONS   = {'doc', 'docx'}

EXTRACT_PROMPT = (
    "This is a CV/resume image. Extract ALL text from it exactly as it appears. "
    "Preserve the structure — sections, headings, bullet points, dates. "
    "Return only the extracted text, nothing else."
)


def extract_text(file_bytes: bytes, filename: str) -> str:
    ext = filename.rsplit('.', 1)[-1].lower()

    if ext not in SUPPORTED_EXTENSIONS:
        raise ValueError(
            f"Unsupported file type '.{ext}'. "
            f"Supported: {', '.join(SUPPORTED_EXTENSIONS.keys())}"
        )

    if ext == 'pdf':
        return _extract_from_pdf(file_bytes)
    elif ext in IMAGE_EXTENSIONS:
        return _extract_from_image(file_bytes, ext)
    elif ext in DOC_EXTENSIONS:
        return _extract_from_doc(file_bytes, ext)


def _extract_from_pdf(file_bytes: bytes) -> str:
    try:
        doc = fitz.open(stream=file_bytes, filetype="pdf")
    except Exception as e:
        raise ValueError(f"Could not open PDF: {e}") from e
    try:
        # Process page by page and discard each after reading — avoids holding all pages in RAM
        parts = []
        for page in doc:
            parts.append(page.get_text())
            page = None  # release page object immediately
        text = "\n".join(parts).strip()
    finally:
        doc.close()
    logger.debug("PDF extracted: %d chars", len(text))
    return text


def _extract_from_image(file_bytes: bytes, ext: str) -> str:
    if settings.AI_PROVIDER == 'claude':
        return _extract_image_claude(file_bytes, ext)
    return _extract_image_gemini(file_bytes, ext)


def _extract_image_gemini(file_bytes: bytes, ext: str) -> str:
    from google import genai
    from google.genai import types

    mime = SUPPORTED_EXTENSIONS[ext]
    client = genai.Client(api_key=settings.GEMINI_API_KEY)

    response = client.models.generate_content(
        model='gemini-flash-latest',
        contents=[
            types.Part.from_bytes(data=file_bytes, mime_type=mime),
            types.Part.from_text(text=EXTRACT_PROMPT),
        ],
    )
    if not response.text:
        raise ValueError("Gemini returned empty response for image extraction.")
    text = response.text.strip()
    logger.debug("Image CV extracted via Gemini Vision: %d chars", len(text))
    return text


def _extract_image_claude(file_bytes: bytes, ext: str) -> str:
    import anthropic

    mime = SUPPORTED_EXTENSIONS[ext]
    b64 = base64.standard_b64encode(file_bytes).decode("utf-8")

    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4000,
        messages=[{
            "role": "user",
            "content": [
                {"type": "image", "source": {"type": "base64", "media_type": mime, "data": b64}},
                {"type": "text", "text": EXTRACT_PROMPT},
            ],
        }],
    )
    block = message.content[0]
    if block.type != 'text':
        raise ValueError(f"Unexpected Claude response block type: {block.type}")
    text = block.text.strip()
    logger.debug("Image CV extracted via Claude Vision: %d chars", len(text))
    return text


def _extract_from_doc(file_bytes: bytes, ext: str) -> str:
    try:
        doc = Document(io.BytesIO(file_bytes))
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        text = "\n".join(paragraphs).strip()
        logger.debug("DOCX extracted: %d chars", len(text))
        return text
    except Exception as e:
        if ext == 'doc':
            raise ValueError(
                "Old .doc format could not be read. "
                "Please save your file as .docx, .pdf, or an image and re-upload."
            ) from e
        raise
