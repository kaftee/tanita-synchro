import subprocess

import pytest
import requests

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
    assert mails == [("me@example.com", None, "ConnectionError: network is unreachable")]


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


@pytest.fixture(autouse=True)
def sleeps(monkeypatch):
    """Pauses the CLI took between tries, in seconds (never really slept; --delay 0 pauses are left out)."""
    taken = []
    monkeypatch.setattr(cli.time, "sleep", lambda s: taken.append(s) if s else None)
    return taken


@pytest.fixture
def flaky_tanita(monkeypatch, csv_text):
    """Make the MyTanita export raise each of ``errors`` in turn, then work."""
    def make(*errors):
        left = list(errors)

        class FlakyTanita:
            def login(self, email, password):
                pass

            def measurements(self, tz=None):
                if left:
                    raise left.pop(0)
                return parse_csv(csv_text, WARSAW)

        monkeypatch.setattr(cli, "MyTanita", FlakyTanita)
    return make


def _http_error(status):
    response = requests.Response()
    response.status_code = status
    return requests.HTTPError(f"{status} error", response=response)


def test_network_failure_is_retried(setup, flaky_tanita, sleeps, mails):
    api = setup()
    flaky_tanita(requests.ConnectionError("Connection reset by peer"), requests.Timeout("read timed out"))
    assert cli.main(["--all", "--delay", "0", "--notify", "me@example.com"]) == cli.EXIT_OK
    assert sleeps == list(cli.RETRY_DELAYS[:2])
    assert len(api.uploads) == 3
    assert mails == []


def test_server_error_is_retried_client_error_is_not(setup, flaky_tanita, sleeps):
    setup()
    flaky_tanita(_http_error(503))
    assert cli.main(["--all", "--delay", "0"]) == cli.EXIT_OK
    flaky_tanita(_http_error(404))
    assert cli.main(["--all", "--delay", "0"]) == cli.EXIT_ERROR
    assert sleeps == [cli.RETRY_DELAYS[0]]


def test_wrong_password_is_not_retried(setup, sleeps, monkeypatch):
    setup()

    def wrong():
        raise mytanita.MyTanitaError("MyTanita sign-in failed: check email and password")
    monkeypatch.setattr(cli, "credentials", wrong)
    assert cli.main(["--all"]) == cli.EXIT_ERROR
    assert sleeps == []


def test_garmin_resume_failing_on_the_network_is_retried(setup, sleeps, monkeypatch):
    api = setup()
    calls = []

    def login(tokenstore):
        calls.append(tokenstore)
        if len(calls) == 1:
            try:
                raise requests.ConnectionError("Connection reset by peer")
            except requests.ConnectionError:
                raise garmin.GarminError("Garmin session is missing or expired")
        return api
    monkeypatch.setattr(garmin, "login", login)
    assert cli.main(["--all", "--delay", "0"]) == cli.EXIT_OK
    assert len(calls) == 2 and len(sleeps) == 1


def test_gives_up_after_the_retries_and_mails_once(setup, flaky_tanita, sleeps, mails, capsys):
    setup()
    flaky_tanita(*[requests.ConnectionError("Connection reset by peer")] * 5)
    assert cli.main(["--all", "--retries", "4", "--notify", "me@example.com"]) == cli.EXIT_ERROR
    assert sleeps == [*cli.RETRY_DELAYS, cli.RETRY_DELAYS[-1]]
    assert len(mails) == 1 and "Connection reset by peer" in mails[0][2]
    assert capsys.readouterr().err.count("trying again in") == 4


def test_retries_zero_tries_once(setup, flaky_tanita, sleeps):
    setup()
    flaky_tanita(requests.ConnectionError("Connection reset by peer"))
    assert cli.main(["--all", "--retries", "0"]) == cli.EXIT_ERROR
    assert sleeps == []


class Ran(list):
    code = 0


@pytest.fixture
def commands(monkeypatch):
    """Commands the CLI ran with the shell, each answered with exit code ``commands.code``."""
    ran = Ran()

    def run(command, shell, timeout):
        ran.append(command)
        return subprocess.CompletedProcess(command, ran.code)
    monkeypatch.setattr(cli.subprocess, "run", run)
    return ran


def test_after_upload_runs_only_when_something_was_uploaded(setup, csv_text, commands):
    first, *rest = parse_csv(csv_text, WARSAW)
    setup()
    assert cli.main(["--all", "--delay", "0", "--after-upload", "ssh host notify"]) == cli.EXIT_OK
    assert commands == ["ssh host notify"]
    # Everything already in Garmin, a dry run, or no option: nothing runs.
    setup(existing=[_entry(m) for m in [first, *rest]])
    assert cli.main(["--all", "--after-upload", "ssh host notify"]) == cli.EXIT_OK
    setup()
    assert cli.main(["--all", "--dry-run", "--after-upload", "ssh host notify"]) == cli.EXIT_OK
    assert cli.main(["--all", "--delay", "0"]) == cli.EXIT_OK
    assert commands == ["ssh host notify"]


def test_after_upload_failure_is_only_logged(setup, commands, mails, capsys):
    setup()
    commands.code = 255
    assert cli.main(["--all", "--delay", "0", "--after-upload", "false", "--notify", "me@example.com"]) == cli.EXIT_OK
    assert "after upload: exit code 255" in capsys.readouterr().err
    assert mails == []


def test_after_upload_not_run_when_every_upload_failed(setup, commands):
    setup(fail=True)  # every upload rejected: nothing new in Garmin
    assert cli.main(["--all", "--delay", "0", "--after-upload", "x"]) == cli.EXIT_UPLOAD_FAILED
    assert commands == []


def test_test_notify_needs_an_address():
    with pytest.raises(SystemExit):
        cli.main(["--test-notify"])
