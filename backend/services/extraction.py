import asyncio
from pathlib import Path
from backend.core.config import get_settings

def extract_pdf(pdf_path: str, output_path: str) -> int:
    text = ''
    try:
        import pdfplumber
        with pdfplumber.open(pdf_path) as pdf:
            text = '\n\n'.join((page.extract_text() or '') for page in pdf.pages)
    except Exception:
        # Keep failures explicit to the worker; no fabricated extraction is marked ready.
        raise
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    Path(output_path).write_text(text, encoding='utf-8')
    return len(text.split())

async def extract_pdf_async(pdf_path: str, output_path: str) -> int:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, extract_pdf, pdf_path, output_path)
