from pydantic import BaseModel, Field


class PdfTextRead(BaseModel):
    filename: str
    pages: int
    text: str


class EmailCreate(BaseModel):
    to: str = Field(min_length=3, max_length=255)
    subject: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=8000)


class EmailSent(BaseModel):
    sent: bool = True


class ToolsStatusRead(BaseModel):
    mail_configured: bool
