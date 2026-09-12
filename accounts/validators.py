import os

from django.core.exceptions import ValidationError

MAX_CV_SIZE_MB = 5
MAX_CV_SIZE_BYTES = MAX_CV_SIZE_MB * 1024 * 1024


def validate_pdf_file(file) -> None:
    """Ensure uploaded file is a PDF (extension and content-type)."""
    if not file.name.lower().endswith(".pdf"):
        raise ValidationError("Le CV doit être au format PDF (.pdf).")

    content_type = getattr(file, "content_type", None)
    if content_type and content_type not in ("application/pdf", "application/x-pdf"):
        raise ValidationError("Le fichier envoyé n'est pas un PDF valide.")

    ext = os.path.splitext(file.name)[1].lower()
    if ext != ".pdf":
        raise ValidationError("Le CV doit être au format PDF (.pdf).")


def validate_file_max_size(file, max_bytes: int = MAX_CV_SIZE_BYTES) -> None:
    """Reject files larger than the allowed size."""
    if file.size > max_bytes:
        max_mb = max_bytes // (1024 * 1024)
        raise ValidationError(f"Le fichier ne doit pas dépasser {max_mb} Mo.")
