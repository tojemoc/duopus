import importlib
from datetime import datetime, timezone

import pytest
from sqlmodel import select


@pytest.mark.asyncio
async def test_seed_creates_admin_template_and_today_rundown(monkeypatch, tmp_path):
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{tmp_path}/duopus_test.db")
    monkeypatch.setenv("SECRET_KEY", "x" * 32)
    monkeypatch.setenv("ADMIN_PASSWORD", "test-seed-admin-pass-123")

    import config as config_mod
    import database as database_mod

    importlib.reload(config_mod)
    importlib.reload(database_mod)

    import models as models_mod

    await database_mod.init_db()

    import seed as seed_mod

    await seed_mod.ensure_seed_data()

    SessionMaker = database_mod.get_sessionmaker()
    async with SessionMaker() as session:
        admin = (await session.execute(select(models_mod.User).where(models_mod.User.email == "admin@example.com"))).scalars().first()
        assert admin is not None
        assert admin.role == "admin"

        tmpl = (await session.execute(select(models_mod.Template))).scalars().first()
        assert tmpl is not None

        today = datetime.now(timezone.utc).date()
        rd = (
            await session.execute(
                select(models_mod.Rundown).where(models_mod.Rundown.template_id == tmpl.id, models_mod.Rundown.show_date == today)
            )
        ).scalars().first()
        assert rd is not None


def test_planned_duration_derives_from_beats():
    from beat_utils import planned_duration_from_beats

    beats = '[{"id":"1","category":"VO","duration":20,"note":""},{"id":"2","category":"SYN","duration":30,"note":""}]'
    assert planned_duration_from_beats(beats, override=None) == 50

    beats_zero = '[{"id":"1","category":"VO","duration":0,"note":""}]'
    assert planned_duration_from_beats(beats_zero, override=40) == 40
