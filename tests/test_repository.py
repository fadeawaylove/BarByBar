from pathlib import Path

from barbybar.domain.engine import ReviewEngine
from barbybar.domain.models import ActionType
from barbybar.storage.repository import Repository


def test_repository_roundtrip(tmp_path: Path) -> None:
    db_path = tmp_path / "barbybar.db"
    repo = Repository(db_path)
    dataset = repo.import_csv(Path("sample_data/if_sample.csv"), "IF", "1m")
    session = repo.create_session(dataset.id or 0, start_index=2)
    bars = repo.get_bars(dataset.id or 0)
    engine = ReviewEngine(session, bars)
    engine.record_action(ActionType.OPEN_LONG, quantity=1)
    engine.step_forward()
    engine.record_action(ActionType.CLOSE, quantity=1)
    engine.set_notes("Breakout failed after resistance retest")
    engine.set_tags(["breakout", "morning"])
    repo.save_session(engine.session, engine.actions)

    saved = repo.get_session(session.id or 0)
    actions = repo.get_session_actions(session.id or 0)
    assert saved.notes.startswith("Breakout")
    assert saved.stats.total_trades == 1
    assert len(actions) == 2
