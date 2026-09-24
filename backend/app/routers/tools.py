from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from app.models.entities import User, UserRole
from app.routers.auth import get_current_user
from app.schemas.tools import EmailCreate, EmailSent, PdfTextRead, ToolsStatusRead
from app.services.mailer import MailError, MailNotConfigured, mail_is_configured, send_email
from app.services.pdf_text import PdfTextError, extract_pdf_text

router = APIRouter(prefix="/tools", tags=["tools"])
MAX_PDF_BYTES = 10 * 1024 * 1024


def _require_admin(user: User) -> None:
    if user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Solo administración puede enviar mails")


def _valid_email(value: str) -> bool:
    text = value.strip()
    if " " in text or text.count("@") != 1:
        return False
    local, domain = text.split("@")
    return bool(local and "." in domain)


@router.get("/status", response_model=ToolsStatusRead)
async def tools_status(_: User = Depends(get_current_user)) -> ToolsStatusRead:
    return ToolsStatusRead(mail_configured=mail_is_configured())


@router.post("/pdf-to-text", response_model=PdfTextRead)
async def pdf_to_text(
    file: UploadFile = File(...),
    _: User = Depends(get_current_user),
) -> PdfTextRead:
    filename = file.filename or "documento.pdf"
    if not filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Subí un archivo PDF")

    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="El archivo está vacío")
    if len(data) > MAX_PDF_BYTES:
        raise HTTPException(status_code=413, detail="El PDF supera los 10 MB")

    try:
        pages, text = extract_pdf_text(data)
    except PdfTextError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    if not text:
        raise HTTPException(
            status_code=422,
            detail="El PDF no tiene texto para extraer. Puede ser un escaneo.",
        )

    return PdfTextRead(filename=filename, pages=pages, text=text)


@router.post("/email", response_model=EmailSent)
async def send_mail(
    body: EmailCreate,
    current_user: User = Depends(get_current_user),
) -> EmailSent:
    _require_admin(current_user)
    if not _valid_email(body.to):
        raise HTTPException(status_code=400, detail="El destinatario no es un email válido")

    try:
        await send_email(body.to.strip(), body.subject.strip(), body.body.strip())
    except MailNotConfigured as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except MailError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return EmailSent()
