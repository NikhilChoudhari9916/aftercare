from datetime import timedelta

import pytest
from sqlmodel import Session, select

from app.auth.session import create_session, end_session, get_session_user, hash_token
from app.config import Settings
from app.models import LoginSession, User, utc_now
from tests.auth.helpers import count, make_settings


@pytest.fixture
def user(db: Session) -> User:
    user = User(google_sub="sub-1", email="ada@example.com", display_name="Ada")
    db.add(user)
    db.commit()
    return user


def test_only_the_hash_of_the_token_is_stored(db: Session, user: User, settings: Settings):
    token = create_session(db, user, settings)
    row = db.exec(select(LoginSession)).one()
    assert row.token_hash == hash_token(token)
    assert token not in str(row.model_dump())
    assert len(token) >= 40


def test_a_known_token_gives_the_user_and_an_unknown_one_does_not(
    db: Session, user: User, settings: Settings
):
    token = create_session(db, user, settings)
    assert get_session_user(db, token, settings).id == user.id
    assert get_session_user(db, "not-a-real-token", settings) is None


def test_session_ends_after_the_idle_limit(db: Session, user: User, settings: Settings):
    start = utc_now()
    token = create_session(db, user, settings, now=start)
    almost = start + timedelta(hours=settings.session_idle_hours) - timedelta(minutes=1)
    assert get_session_user(db, token, settings, now=almost) is not None

    later = almost + timedelta(hours=settings.session_idle_hours)
    assert get_session_user(db, token, settings, now=later) is None
    assert count(db, LoginSession) == 0


def test_session_ends_after_the_absolute_limit_even_if_always_active(db: Session, user: User):
    settings = make_settings(session_idle_hours=48, session_max_days=1)
    start = utc_now()
    token = create_session(db, user, settings, now=start)
    assert get_session_user(db, token, settings, now=start + timedelta(hours=23)) is not None
    assert get_session_user(db, token, settings, now=start + timedelta(hours=25)) is None
    assert count(db, LoginSession) == 0


def test_last_seen_is_updated_at_most_once_a_minute(db: Session, user: User, settings: Settings):
    start = utc_now()
    token = create_session(db, user, settings, now=start)

    get_session_user(db, token, settings, now=start + timedelta(seconds=30))
    assert db.exec(select(LoginSession)).one().last_seen_at == start

    get_session_user(db, token, settings, now=start + timedelta(seconds=90))
    assert db.exec(select(LoginSession)).one().last_seen_at == start + timedelta(seconds=90)


def test_end_session_deletes_it_and_ignores_unknown_tokens(
    db: Session, user: User, settings: Settings
):
    token = create_session(db, user, settings)
    end_session(db, "unknown")
    assert count(db, LoginSession) == 1
    end_session(db, token)
    assert count(db, LoginSession) == 0
    assert get_session_user(db, token, settings) is None
