from io import BytesIO


class PdfTextError(Exception):
    """El archivo no se pudo leer como PDF."""


def extract_pdf_text(data: bytes) -> tuple[int, str]:
    try:
        from pypdf import PdfReader
        from pypdf.errors import PdfReadError
    except ImportError as exc:
        raise PdfTextError("Falta instalar pypdf en el backend") from exc

    try:
        reader = PdfReader(BytesIO(data))
    except PdfReadError as exc:
        raise PdfTextError("No se pudo leer el PDF") from exc

    if reader.is_encrypted:
        raise PdfTextError("El PDF está protegido con contraseña")

    pages: list[str] = []
    for page in reader.pages:
        text = " ".join((page.extract_text() or "").split())
        if text:
            pages.append(text)

    return len(reader.pages), "\n\n".join(pages)
