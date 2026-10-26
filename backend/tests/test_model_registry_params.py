"""Tests for model registry parameter counts and seed behavior.

These are UNIT tests: they use an in-memory SQLite database (via the shared
`db_session` fixture) and a monkeypatched session factory for the seed script.
They do NOT require a live Neon connection.

The core regression covered here is that parameter counts larger than the
32-bit INTEGER range (e.g. 27_000_000_000 for a 27B model) are stored and
returned without overflow. On PostgreSQL this requires a BIGINT column; the
migration `0002_bigint_params` provides that.
"""
from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy import BigInteger, select
from sqlalchemy.orm import Session, sessionmaker

import app.seed_registry as seed_registry
from app.models import ModelRegistry


# ---------------------------------------------------------------------------
# Column type
# ---------------------------------------------------------------------------
def test_param_columns_are_bigint() -> None:
    """total_params and active_params must be BIGINT, not 32-bit INTEGER."""
    assert isinstance(ModelRegistry.__table__.c.total_params.type, BigInteger)
    assert isinstance(ModelRegistry.__table__.c.active_params.type, BigInteger)


# ---------------------------------------------------------------------------
# Large / nullable parameter counts
# ---------------------------------------------------------------------------
def test_large_total_params_round_trips(db_session: Session) -> None:
    """A 27B model (27_000_000_000) exceeds the 32-bit range and must persist."""
    model = ModelRegistry(
        name="qwen3.8-27b",
        provider="Alibaba",
        classification="SLM",
        classification_reason="27B < 150B threshold",
        total_params=27_000_000_000,
        active_params=None,
    )
    db_session.add(model)
    db_session.commit()

    row = db_session.execute(
        select(ModelRegistry).where(ModelRegistry.name == "qwen3.8-27b")
    ).scalar_one()
    assert row.total_params == 27_000_000_000
    assert row.active_params is None


def test_large_active_params_round_trips(db_session: Session) -> None:
    """A large active_params value (MoE active count) must persist."""
    model = ModelRegistry(
        name="moe-large",
        provider="Test",
        classification="LLM",
        classification_reason=">= 150B threshold",
        total_params=200_000_000_000,
        active_params=32_000_000_000,
    )
    db_session.add(model)
    db_session.commit()

    row = db_session.execute(
        select(ModelRegistry).where(ModelRegistry.name == "moe-large")
    ).scalar_one()
    assert row.total_params == 200_000_000_000
    assert row.active_params == 32_000_000_000


def test_nullable_param_counts(db_session: Session) -> None:
    """Parameter counts may be None (unknown) and must stay None."""
    model = ModelRegistry(
        name="gpt-4o",
        provider="OpenAI",
        classification="unknown",
        classification_reason="Parameter count not disclosed",
        total_params=None,
        active_params=None,
    )
    db_session.add(model)
    db_session.commit()

    row = db_session.execute(
        select(ModelRegistry).where(ModelRegistry.name == "gpt-4o")
    ).scalar_one()
    assert row.total_params is None
    assert row.active_params is None


# ---------------------------------------------------------------------------
# Seed script idempotency
# ---------------------------------------------------------------------------
def _patch_seed_session(monkeypatch: pytest.MonkeyPatch, engine: Any) -> None:
    """Point the seed script at an in-memory engine."""
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr(seed_registry, "get_session_factory", lambda: factory)


def test_seed_is_idempotent(db_session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    """Running seed() twice must not create duplicate registry entries."""
    # Bind the seed to the same in-memory engine the fixture created.
    engine = db_session.get_bind()
    _patch_seed_session(monkeypatch, engine)

    first = seed_registry.seed()
    assert first > 0  # something was inserted

    # Second run must insert nothing (idempotent).
    second = seed_registry.seed()
    assert second == 0

    # Exactly one row per seeded model name.
    for entry in seed_registry.SEED:
        rows = db_session.execute(
            select(ModelRegistry).where(ModelRegistry.name == entry["name"])
        ).scalars().all()
        assert len(rows) == 1


def test_seed_stores_large_params_without_overflow(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The 27B seed entry must be stored as 27_000_000_000, not truncated."""
    engine = db_session.get_bind()
    _patch_seed_session(monkeypatch, engine)

    seed_registry.seed()

    row = db_session.execute(
        select(ModelRegistry).where(ModelRegistry.name == "qwen3.8-27b")
    ).scalar_one()
    assert row is not None
    assert row.total_params == 27_000_000_000
    # 27B is below the 150B threshold -> SLM.
    assert row.classification == "SLM"


def test_seed_preserves_existing_registry_behavior(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Seeding must not alter classification logic or drop unknown counts."""
    engine = db_session.get_bind()
    _patch_seed_session(monkeypatch, engine)

    seed_registry.seed()

    # GPT-4o has no disclosed parameter count -> total_params is None, unknown.
    gpt = db_session.execute(
        select(ModelRegistry).where(ModelRegistry.name == "GPT-4o")
    ).scalar_one()
    assert gpt.total_params is None
    assert gpt.classification == "unknown"

    # Llama 3.1 70B is below 150B -> SLM, stored as 70_000_000_000.
    llama = db_session.execute(
        select(ModelRegistry).where(ModelRegistry.name == "Llama 3.1 70B")
    ).scalar_one()
    assert llama.total_params == 70_000_000_000
    assert llama.classification == "SLM"
