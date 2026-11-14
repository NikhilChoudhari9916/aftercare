import re
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


def _index_path(root: Path, patient_id: str, name: str) -> Path:
    # An allow-list, not a Path check: "..\\x" is a plain name on Linux but a path on Windows.
    if not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.-]*", name):
        raise ValueError("Index file names are plain names")
    return patient_dir(root, patient_id) / "index" / name


def save_index_file(root: Path, patient_id: str, name: str, data: bytes) -> None:
    """Store a piece of the patient's search index. It is rebuilt freely, so overwriting is fine."""
    path = _index_path(root, patient_id, name)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp")
    temp.write_bytes(data)
    temp.replace(path)


def get_index_file(root: Path, patient_id: str, name: str) -> bytes | None:
    path = _index_path(root, patient_id, name)
    return path.read_bytes() if path.exists() else None
