from __future__ import annotations

import hashlib
import mimetypes
import re
import tempfile
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

from DataStore.context_file_store import ContextFileError, ContextFileStore, chunk_text, redact_preview

MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024
SUPPORTED_EXTENSIONS = {".txt", ".md", ".docx", ".pdf", ".json", ".csv", ".html"}
BLOCKED_EXTENSIONS = {".docm", ".xlsm", ".pptm", ".exe", ".bat", ".cmd", ".ps1", ".sh", ".zip", ".rar", ".doc"}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def detect_mime(filename: str) -> str:
    return mimetypes.guess_type(filename)[0] or "application/octet-stream"


def _decode_text(data: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "utf-16", "latin-1"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def extract_txt_like(data: bytes) -> str:
    return _decode_text(data)


def extract_docx(data: bytes) -> str:
    try:
        with zipfile.ZipFile(tempfile.SpooledTemporaryFile()) as _:
            pass
    except Exception:
        pass
    try:
        import io
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            xml = zf.read("word/document.xml")
        root = ElementTree.fromstring(xml)
        texts = []
        for node in root.iter():
            if node.tag.endswith("}t") or node.tag == "t":
                if node.text:
                    texts.append(node.text)
        return "\n".join(texts)
    except Exception as exc:
        raise ContextFileError("FILE_TEXT_EXTRACTION_FAILED", "DOCX text extraction failed.", {"error": str(exc)}) from exc


def extract_pdf(data: bytes) -> str:
    try:
        from pypdf import PdfReader  # type: ignore
        import io
        reader = PdfReader(io.BytesIO(data))
        pages = [page.extract_text() or "" for page in reader.pages]
        text = "\n".join(pages).strip()
        if text:
            return text
    except Exception:
        # Fall back to conservative regex extraction for simple text-based PDF fixtures.
        pass
    decoded = data.decode("latin-1", errors="ignore")
    tokens = re.findall(r"\(([^()]{1,2000})\)\s*T[jJ]", decoded)
    if not tokens:
        tokens = re.findall(r"\(([^()]{1,2000})\)", decoded)
    cleaned = []
    for token in tokens:
        token = token.replace(r"\(", "(").replace(r"\)", ")").replace(r"\n", "\n")
        if any(ch.isalpha() for ch in token):
            cleaned.append(token)
    return "\n".join(cleaned).strip()


def extract_text(filename: str, data: bytes) -> tuple[str, str | None]:
    ext = Path(filename).suffix.lower()
    if ext in {".txt", ".md", ".json", ".csv", ".html"}:
        text = extract_txt_like(data)
    elif ext == ".docx":
        text = extract_docx(data)
    elif ext == ".pdf":
        text = extract_pdf(data)
    else:
        raise ContextFileError("FILE_TYPE_UNSUPPORTED", "File type is not supported.")
    if not text.strip():
        return "", "FILE_TEXT_EXTRACTION_EMPTY"
    return text, None


def ingest_context_file(
    store: ContextFileStore,
    filename: str,
    data: bytes,
    *,
    uploaded_by: str | None = None,
    chat_id: str | None = None,
    database_profile_id: str | None = None,
    sandbox_id: str | None = None,
    project_id: str | None = None,
    scope: str = "session",
    source_type: str = "prompt_context",
) -> dict[str, Any]:
    size = len(data or b"")
    if size > MAX_FILE_SIZE_BYTES:
        raise ContextFileError("FILE_TOO_LARGE", "File exceeds 50 MB limit.")
    safe_filename = store.sanitize_filename(filename)
    ext = Path(safe_filename).suffix.lower()
    if ext in BLOCKED_EXTENSIONS or ext not in SUPPORTED_EXTENSIONS:
        raise ContextFileError("FILE_TYPE_UNSUPPORTED", "File type is not supported in File Prompt Reader V1.")
    digest = sha256_bytes(data)
    text, extraction_error = extract_text(safe_filename, data)
    status = "success"
    if extraction_error == "FILE_TEXT_EXTRACTION_EMPTY":
        status = "empty"
    chunks = chunk_text(text)
    file_id = "ctx_" + uuid.uuid4().hex[:24]
    with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
        tmp.write(data)
        tmp_path = Path(tmp.name)
    try:
        metadata = {
            "file_id": file_id,
            "filename": filename,
            "safe_filename": safe_filename,
            "extension": ext,
            "mime_type": detect_mime(safe_filename),
            "size_bytes": size,
            "sha256": digest,
            "source_type": source_type,
            "uploaded_by": uploaded_by,
            "chat_id": chat_id,
            "database_profile_id": database_profile_id,
            "sandbox_id": sandbox_id,
            "project_id": project_id,
            "scope": scope,
            "is_active": True,
            "is_pinned": False,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "extraction_status": status,
            "error_code": extraction_error,
            "text_char_count": len(text),
            "chunk_count": len(chunks),
            "preview": redact_preview(text),
        }
        return store.save(metadata, tmp_path, text)
    finally:
        try:
            tmp_path.unlink(missing_ok=True)
        except Exception:
            pass
