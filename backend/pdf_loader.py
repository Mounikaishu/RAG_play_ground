import io
from pypdf import PdfReader
from typing import Union

def load_pdf(path_or_bytes: Union[str, bytes]) -> str:
    if isinstance(path_or_bytes, bytes):
        reader = PdfReader(io.BytesIO(path_or_bytes))
    else:
        reader = PdfReader(path_or_bytes)
    text = ""

    for page in reader.pages:
        page_text = page.extract_text()
        if page_text:
            text += page_text + "\n"

    return text
