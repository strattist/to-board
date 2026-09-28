import asyncio
import logging
import os
import subprocess
from io import BytesIO
from pathlib import Path
from uuid import uuid4

logger = logging.getLogger(__name__)


def _remove_temporary(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass


def _ocr_page(page) -> str:
    image = page.to_image(resolution=300).original
    with BytesIO() as png:
        image.save(png, format='PNG')
        result = subprocess.run(
            ['tesseract', 'stdin', 'stdout', '-l', 'fra+eng', '--psm', '3'],
            input=png.getvalue(),
            capture_output=True,
            check=True,
            timeout=30,
        )
    return result.stdout.decode('utf-8').strip()


def extract_pdf(pdf_path: str, output_path: str) -> int:
    text = ''
    try:
        import pdfplumber
        with pdfplumber.open(pdf_path) as pdf:
            pages = []
            for page in pdf.pages:
                page_text = page.extract_text() or ''
                if not page_text.strip() and page.images:
                    try:
                        page_text = _ocr_page(page)
                    except Exception as exc:
                        # OCR is a fallback: an unreadable image or unavailable
                        # local Tesseract should not discard text from other pages.
                        logger.warning(
                            'OCR failed for PDF page %s (%s)',
                            page.page_number,
                            type(exc).__name__,
                        )
                pages.append(page_text)
            text = '\n\n'.join(pages)
    except Exception:
        # Keep failures explicit to the worker; no fabricated extraction is marked ready.
        raise
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(f'.{output.name}.{uuid4().hex}.part')
    try:
        with temporary.open('w', encoding='utf-8') as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        temporary.replace(output)
    finally:
        _remove_temporary(temporary)
    return len(text.split())

async def extract_pdf_async(pdf_path: str, output_path: str) -> int:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, extract_pdf, pdf_path, output_path)


def count_extracted_tokens(path: str) -> int:
    """Count words from the durable extraction cache.

    Generation uses this server-side check rather than trusting a value sent
    by the browser.  The caller is responsible for handling read failures.
    """
    return len(Path(path).read_text(encoding='utf-8').split())
