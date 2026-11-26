import threading
from uuid import uuid4

import pytest

from app.storage import (
    delete_patient_files,
    get_index_file,
    get_pdf,
    patient_dir,
    save_index_file,
    save_pdf,
)


@pytest.fixture
def ids():
    return str(uuid4()), str(uuid4())


def test_save_then_get_round_trips_and_lands_under_the_patient(tmp_path, ids):
    patient_id, document_id = ids
    path = save_pdf(tmp_path, patient_id, document_id, b"%PDF-1.7 hello")
    assert path == tmp_path / "patients" / patient_id / "documents" / f"{document_id}.pdf"
    assert get_pdf(tmp_path, patient_id, document_id) == b"%PDF-1.7 hello"


def test_uploads_are_never_overwritten(tmp_path, ids):
    patient_id, document_id = ids
    save_pdf(tmp_path, patient_id, document_id, b"first")
    with pytest.raises(FileExistsError):
        save_pdf(tmp_path, patient_id, document_id, b"second")
    assert get_pdf(tmp_path, patient_id, document_id) == b"first"


def test_no_temp_file_is_left_behind(tmp_path, ids):
    patient_id, document_id = ids
    save_pdf(tmp_path, patient_id, document_id, b"data")
    leftovers = [p.name for p in patient_dir(tmp_path, patient_id).rglob("*.tmp")]
    assert leftovers == []


@pytest.mark.parametrize(
    "bad_id",
    [
        "../escape",
        "..",
        "",
        "not-a-uuid",
        str(uuid4()).upper(),
        f"urn:uuid:{uuid4()}",
        "{" + str(uuid4()) + "}",
    ],
)
def test_ids_that_could_change_the_path_are_rejected(tmp_path, bad_id):
    with pytest.raises(ValueError):
        patient_dir(tmp_path, bad_id)
    with pytest.raises(ValueError):
        save_pdf(tmp_path, str(uuid4()), bad_id, b"x")


def test_delete_patient_files_removes_only_that_patient(tmp_path, ids):
    patient_id, document_id = ids
    other_patient = str(uuid4())
    save_pdf(tmp_path, patient_id, document_id, b"mine")
    save_pdf(tmp_path, other_patient, document_id, b"theirs")
    delete_patient_files(tmp_path, patient_id)
    assert not patient_dir(tmp_path, patient_id).exists()
    assert get_pdf(tmp_path, other_patient, document_id) == b"theirs"


def test_deleting_a_patient_with_no_files_is_not_an_error(tmp_path):
    delete_patient_files(tmp_path, str(uuid4()))


def test_index_files_written_at_once_never_break_each_other(tmp_path, ids):
    patient_id, _ = ids
    errors: list[BaseException] = []

    def write(number: int) -> None:
        try:
            save_index_file(tmp_path, patient_id, "vectors.faiss", f"write {number}".encode())
        except BaseException as error:  # the test must see a failure on any thread
            errors.append(error)

    threads = [threading.Thread(target=write, args=(n,)) for n in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=10)

    assert errors == []
    assert get_index_file(tmp_path, patient_id, "vectors.faiss").startswith(b"write ")
    assert list(patient_dir(tmp_path, patient_id).rglob("*.tmp")) == []


def test_a_failed_index_write_leaves_no_temp_file_behind(tmp_path, ids, monkeypatch):
    patient_id, _ = ids

    def fail(self, target):
        raise OSError("disk full")

    monkeypatch.setattr("pathlib.Path.replace", fail)
    with pytest.raises(OSError):
        save_index_file(tmp_path, patient_id, "vectors.faiss", b"data")

    assert list(patient_dir(tmp_path, patient_id).rglob("*.tmp")) == []
