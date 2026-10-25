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


@pytest.fixture
def mails(monkeypatch):
    """Failure mails the CLI sends, as (to, sender, error)."""
    sent = []
    monkeypatch.setattr(cli.notify, "failure", lambda server, to, sender, error: sent.append((to, sender, error)))
    return sent


def test_failure_is_mailed(setup, mails, monkeypatch):
    setup()

    def expired(tokenstore):
        raise garmin.GarminError("Garmin session in ~/.garminconnect is missing or expired")
    monkeypatch.setattr(garmin, "login", expired)
    assert cli.main(["--all", "--notify", "me@example.com", "--mail-from", "bot@example.com"]) == cli.EXIT_ERROR
    assert mails == [("me@example.com", "bot@example.com",
                      "error: Garmin session in ~/.garminconnect is missing or expired")]


def test_failed_upload_is_mailed(setup, mails):
    setup(fail=True)
    assert cli.main(["--all", "--delay", "0", "--notify", "me@example.com"]) == cli.EXIT_UPLOAD_FAILED
    assert len(mails) == 1


def test_unexpected_error_is_mailed(setup, mails, monkeypatch):
    setup()

    def offline(tokenstore):
        raise ConnectionError("network is unreachable")
    monkeypatch.setattr(garmin, "login", offline)
    assert cli.main(["--all", "--notify", "me@example.com"]) == cli.EXIT_ERROR
    assert mails[0][2] == "ConnectionError: network is unreachable"


def test_no_mail_on_success_or_without_notify(setup, mails):
    setup()
    assert cli.main(["--all", "--delay", "0", "--notify", "me@example.com"]) == cli.EXIT_OK
    setup(fail=True)
    assert cli.main(["--all", "--delay", "0"]) == cli.EXIT_UPLOAD_FAILED
    assert mails == []


def test_mail_failure_keeps_exit_code(setup, monkeypatch, capsys):
    setup(fail=True)

    def broken(*args):
        raise cli.notify.NotifyError("mail via smtp.example.com failed")
    monkeypatch.setattr(cli.notify, "failure", broken)
    assert cli.main(["--all", "--delay", "0", "--notify", "me@example.com"]) == cli.EXIT_UPLOAD_FAILED
    assert "not mailed: mail via smtp.example.com failed" in capsys.readouterr().err


def test_test_notify_needs_an_address():
    with pytest.raises(SystemExit):
        cli.main(["--test-notify"])
