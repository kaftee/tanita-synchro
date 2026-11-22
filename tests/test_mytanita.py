import subprocess

import pytest

from tanita_synchro import mytanita
from tanita_synchro.mytanita import MyTanita, MyTanitaError, parse_csv

from .conftest import WARSAW


def test_parse_csv_sorts_dedups_and_localizes(csv_text):
    ms = parse_csv(csv_text, WARSAW)
    assert [m.time.isoformat() for m in ms] == [
        "2026-01-10T06:50:30+01:00", "2026-03-02T07:15:00+01:00", "2026-03-05T21:05:10+01:00"]


def test_parse_csv_fields(csv_text):
    first, second, _ = parse_csv(csv_text, WARSAW)
    assert first.percent_fat is None  # "-" in the export
    assert second.weight == 70.4 and second.muscle_mass == 54.3 and second.bone_mass == 2.9
    assert second.visceral_fat_rating == 4.5 and second.basal_met == 1650
    assert second.metabolic_age == 31 and second.percent_hydration == 57.8
    assert second.physique_rating == 5 and second.bmi == 22.1


def test_parse_csv_summer_time(csv_text):
    text = csv_text.replace("2026-03-05 21:05:10", "2026-07-01 08:00:00")
    assert parse_csv(text, WARSAW)[-1].time.isoformat() == "2026-07-01T08:00:00+02:00"


class FakeResponse:
    def __init__(self, text="", content=b""):
        self.text, self.content = text, content

    def raise_for_status(self):
        pass


class FakeSession:
    def __init__(self, login_ok=True):
        self.login_ok = login_ok
        self.posted = None
        self.headers = {}

    def get(self, url, timeout=None):
        if url.endswith("/login"):
            return FakeResponse('<form><input type="hidden" name="token" value="t0k"></form>')
        return FakeResponse(content=b"\xef\xbb\xbfDate\n")

    def post(self, url, data=None, timeout=None):
        self.posted = data
        return FakeResponse("<h1>Trends</h1>" if self.login_ok else '<form action="/en/user/processlogin">')


def test_login_sends_csrf_token():
    t = MyTanita()
    t.s = FakeSession()
    t.login("a@example.com", "secret")
    assert t.s.posted == {"mail": "a@example.com", "password": "secret", "token": "t0k", "login": "Login"}
    assert t.export_csv() == "Date\n"  # BOM stripped


def test_login_failure_raises():
    t = MyTanita()
    t.s = FakeSession(login_ok=False)
    with pytest.raises(MyTanitaError):
        t.login("a@example.com", "wrong")


def test_login_page_without_token_raises():
    t = MyTanita()
    t.s = FakeSession()
    t.s.get = lambda url, timeout=None: FakeResponse("<form></form>")
    with pytest.raises(MyTanitaError, match="sign-in page has changed"):
        t.login("a@example.com", "secret")


def _security_output(monkeypatch, stdout, stderr, returncode=0):
    """Answer `security` calls with this output; return the calls made, as (argv, stdin, kwargs)."""
    calls = []

    def run(argv, input=None, **kwargs):
        calls.append((argv, input, kwargs))
        return subprocess.CompletedProcess(argv, returncode, stdout, stderr)
    monkeypatch.setattr(mytanita.subprocess, "run", run)
    return calls


def test_keychain_plain_password(monkeypatch):
    _security_output(monkeypatch, '    "acct"<blob>="a@example.com"\n', 'password: "se"cret"\n')
    assert mytanita.keychain_credentials() == ("a@example.com", 'se"cret')


def test_keychain_non_ascii_password_is_printed_as_hex(monkeypatch):
    # What `security -g` prints for 'pä"ss wörd$1'
    stderr = 'password: 0x70C3A42273732077C3B672642431  "p\\303\\244"ss w\\303\\266rd$1"\n'
    _security_output(monkeypatch, '    "acct"<blob>="a@example.com"\n', stderr)
    assert mytanita.keychain_credentials() == ("a@example.com", 'pä"ss wörd$1')


def test_keychain_missing_item(monkeypatch):
    _security_output(monkeypatch, "", "security: The specified item could not be found.\n", returncode=44)
    assert mytanita.keychain_credentials() is None


def test_saved_password_goes_through_stdin_not_argv(monkeypatch):
    calls = _security_output(monkeypatch, "", "")
    mytanita.save_keychain_credentials("a@example.com", "secret")
    (argv, stdin, kwargs), = calls
    assert "secret" not in argv and argv[-1] == "-w"
    assert stdin == "secret\nsecret\n"
    # Without its own session, `security` would read the password from the terminal, not stdin
    assert kwargs["start_new_session"] is True


def test_credentials_from_environment(monkeypatch):
    monkeypatch.setenv("MYTANITA_EMAIL", "a@example.com")
    monkeypatch.setenv("MYTANITA_PASSWORD", "secret")
    assert mytanita.credentials() == ("a@example.com", "secret")


def test_local_zone_from_tz(monkeypatch):
    monkeypatch.setenv("TZ", "America/New_York")
    assert mytanita.local_zone().key == "America/New_York"
