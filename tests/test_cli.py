import pytest

from tanita_synchro import cli, garmin, mytanita
from tanita_synchro.mytanita import parse_csv

from .conftest import WARSAW


@pytest.fixture
def setup(monkeypatch, csv_text, fake_garmin):
    """Wire the CLI to a fake MyTanita export and a fake Garmin account."""
    def make(existing=None, fail=False):
        api = fake_garmin(existing=existing, fail=fail)

        class FakeTanita:
            def login(self, email, password):
                pass

            def measurements(self, tz=None):
                return parse_csv(csv_text, WARSAW)

        monkeypatch.setattr(cli, "MyTanita", FakeTanita)
        monkeypatch.setattr(cli, "credentials", lambda: ("a@example.com", "secret"))
        monkeypatch.setattr(garmin, "login", lambda tokenstore: api)
        return api
    return make


def _entry(m):
    return {"calendarDate": m.time.date().isoformat(), "timestampGMT": int(m.time.timestamp() * 1000)}


def test_uploads_only_missing_measurements(setup, csv_text):
    first = parse_csv(csv_text, WARSAW)[0]
    api = setup(existing=[_entry(first)])
    assert cli.main(["--all", "--delay", "0"]) == cli.EXIT_OK
    assert len(api.uploads) == 2


def test_dry_run_uploads_nothing(setup, capsys):
    api = setup()
    assert cli.main(["--all", "--dry-run"]) == cli.EXIT_OK
    assert api.uploads == []
    assert capsys.readouterr().out.count("(dry run)") == 3


def test_since_limits_the_window(setup):
    api = setup()
    cli.main(["--since", "2026-03-03", "--delay", "0"])
    assert len(api.uploads) == 1


def test_failed_upload_sets_exit_code(setup):
    setup(fail=True)
    assert cli.main(["--all", "--delay", "0"]) == cli.EXIT_UPLOAD_FAILED


def test_sign_in_error_is_reported(setup, monkeypatch, capsys):
    setup()

    def broken():
        raise mytanita.MyTanitaError("MyTanita sign-in failed")
    monkeypatch.setattr(cli, "credentials", broken)
    assert cli.main(["--all"]) == cli.EXIT_ERROR
    assert "MyTanita sign-in failed" in capsys.readouterr().err
