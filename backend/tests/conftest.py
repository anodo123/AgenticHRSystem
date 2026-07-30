"""Shared backend test fixtures."""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
import app.models  # noqa: F401 - register every mapped model
from app.llm import OpenAIResponsesClient
from app.models.user import Role, User


@pytest.fixture(autouse=True)
def isolate_openai_network(monkeypatch, request):
    """Keep tests offline while production remains real-API-only."""
    if request.node.get_closest_marker("real_llm_client"):
        return

    def return_validated_facts(self, **kwargs):
        return kwargs["candidate"]

    monkeypatch.setattr(OpenAIResponsesClient, "generate", return_validated_facts)


@pytest.fixture()
def db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)


@pytest.fixture()
def users(db):
    requester = User(
        username="requester", email="requester@example.com", full_name="Requester",
        hashed_password="unused",
    )
    approver_role = Role(name="HR_ADMIN")
    approver = User(
        username="approver", email="approver@example.com", full_name="Approver",
        hashed_password="unused", roles=[approver_role],
    )
    outsider = User(
        username="outsider", email="outsider@example.com", full_name="Outsider",
        hashed_password="unused",
    )
    db.add_all([requester, approver, outsider])
    db.commit()
    return requester, approver, outsider
