import re
import unicodedata
import uuid

def slugify(value: str, max_length: int = 32) -> str:
    normalized = unicodedata.normalize('NFKD', value).encode('ascii', 'ignore').decode().lower()
    normalized = re.sub(r'[^a-z0-9]+', '-', normalized).strip('-')
    return (normalized or 'game')[:max_length].rstrip('-')

def uuid4_str() -> str:
    return str(uuid.uuid4())
