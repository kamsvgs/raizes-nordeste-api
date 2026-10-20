import os

os.environ["DATABASE_URL"] = "sqlite://"  # banco em memória para os testes
os.environ["BCRYPT_ROUNDS"] = "4"        # hash mais leve só nos testes

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool

from app.infrastructure.db import base


@pytest.fixture()
def client():
    from sqlalchemy import create_engine, event
    from sqlalchemy.orm import sessionmaker

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)

    @event.listens_for(engine, "connect")
    def _fk(c, _):
        c.execute("PRAGMA foreign_keys=ON")

    base.engine = engine
    base.SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    from app.api import deps
    from app.infrastructure.db import models  # noqa: F401
    from app.infrastructure.db.seed import seed

    deps.SessionLocal = base.SessionLocal
    base.Base.metadata.create_all(engine)
    with base.SessionLocal() as s:
        seed(s)
    from app.api.main import app

    with TestClient(app) as c:
        yield c
    base.Base.metadata.drop_all(engine)


def _login(client, email):
    r = client.post("/auth/login", json={"email": email, "senha": "Senha@123"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['accessToken']}"}


@pytest.fixture()
def h(client):
    return {
        "cliente": _login(client, "cliente@raizes.test"),
        "cliente2": _login(client, "cliente2@raizes.test"),
        "admin": _login(client, "admin@raizes.test"),
        "gerente": _login(client, "gerente.recife@raizes.test"),
        "atendente": _login(client, "atendente.recife@raizes.test"),
        "cozinha": _login(client, "cozinha.recife@raizes.test"),
    }
