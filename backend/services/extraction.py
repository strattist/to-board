import asyncio
import os
from pathlib import Path
from uuid import uuid4
from backend.core.config import get_settings

def _remove_temporary(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass

def extract_pdf(pdf_path: str, output_path: str) -> int:
    text = ''
    try:
        import pdfplumber
        with pdfplumber.open(pdf_path) as pdf:
            text = '\n\n'.join((page.extract_text() or '') for page in pdf.pages)
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
