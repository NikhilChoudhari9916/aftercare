import re
import shutil
import threading
from pathlib import Path
from uuid import UUID, uuid4


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


_locks_guard = threading.Lock()
_file_locks: dict[Path, threading.Lock] = {}


def _file_lock(path: Path) -> threading.Lock:
    with _locks_guard:
        return _file_locks.setdefault(path, threading.Lock())


def _index_path(root: Path, patient_id: str, name: str) -> Path:
    # An allow-list, not a Path check: "..\\x" is a plain name on Linux but a path on Windows.
    if not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.-]*", name):
        raise ValueError("Index file names are plain names")
    return patient_dir(root, patient_id) / "index" / name


def save_index_file(root: Path, patient_id: str, name: str, data: bytes) -> None:
    """Store a piece of the patient's search index. It is rebuilt freely, so overwriting is fine."""
    path = _index_path(root, patient_id, name)
    path.parent.mkdir(parents=True, exist_ok=True)
    # A name of its own for every write, and one writer at a time per file: on Windows two
    # writers replacing the same file (or a reader opening it) fail with "Access is denied".
    temp = path.with_name(f"{path.name}.{uuid4().hex}.tmp")
    with _file_lock(path):
        try:
            temp.write_bytes(data)
            temp.replace(path)
        except BaseException:
            temp.unlink(missing_ok=True)
            raise


def get_index_file(root: Path, patient_id: str, name: str) -> bytes | None:
    path = _index_path(root, patient_id, name)
    with _file_lock(path):
        return path.read_bytes() if path.exists() else None
