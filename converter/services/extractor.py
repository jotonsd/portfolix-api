import base64
import io
import logging

import anthropic
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
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    text = "\n".join(page.get_text() for page in doc).strip()
    doc.close()
    logger.debug("PDF extracted: %d chars", len(text))
    return text


def _extract_from_image(file_bytes: bytes, ext: str) -> str:
    """Send image to Claude Vision and extract CV text from it."""
    mime = SUPPORTED_EXTENSIONS[ext]
    b64 = base64.standard_b64encode(file_bytes).decode("utf-8")

    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4000,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": mime,
                            "data": b64,
                        },
                    },
                    {
                        "type": "text",
                        "text": (
                            "This is a CV/resume image. Extract ALL text from it exactly as it appears. "
                            "Preserve the structure — sections, headings, bullet points, dates. "
                            "Return only the extracted text, nothing else."
                        ),
                    },
                ],
            }
        ],
    )
    text = message.content[0].text.strip()
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
