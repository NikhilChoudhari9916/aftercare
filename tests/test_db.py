from sqlalchemy import text

from app.db import init_db, make_engine


def test_in_memory_engine_shares_one_database_across_connections():
    engine = make_engine("sqlite://")
    init_db(engine)
    with engine.connect() as first:
        first.execute(text("CREATE TABLE t (x INTEGER)"))
        first.execute(text("INSERT INTO t VALUES (1)"))
        first.commit()
    with engine.connect() as second:
        assert second.execute(text("SELECT x FROM t")).scalar() == 1


def test_file_database_uses_wal_and_enforces_foreign_keys(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path / 'test.db'}")
    with engine.connect() as connection:
        assert connection.execute(text("PRAGMA journal_mode")).scalar() == "wal"
        assert connection.execute(text("PRAGMA foreign_keys")).scalar() == 1
