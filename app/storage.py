import shutil
from pathlib import Path
from uuid import UUID


def _clean_id(value: str) -> str:
    """Accept only canonical lowercase UUIDs, so an ID can never change the path."""
    if str(UUID(value)) != value:
        raise ValueError("ID must be a canonical lowercase UUID")
    return value


def patient_dir(root: Path, patient_id: str) -> Path:
    return root / "patients" / _clean_id(patient_id)


def _pdf_path(root: Path, patient_id: str, document_id: str) -> Path:
    return patient_dir(root, patient_id) / "documents" / f"{_clean_id(document_id)}.pdf"


def save_pdf(root: Path, patient_id: str, document_id: str, data: bytes) -> Path:
    """Store an uploaded PDF. Uploads are never modified, so overwriting is refused."""
    path = _pdf_path(root, patient_id, document_id)
    if path.exists():
        raise FileExistsError(path.name)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp")
    temp.write_bytes(data)
    temp.replace(path)
    return path


def get_pdf(root: Path, patient_id: str, document_id: str) -> bytes:
    return _pdf_path(root, patient_id, document_id).read_bytes()


def delete_patient_files(root: Path, patient_id: str) -> None:
    shutil.rmtree(patient_dir(root, patient_id), ignore_errors=True)
