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


def test_credentials_from_environment(monkeypatch):
    monkeypatch.setenv("MYTANITA_EMAIL", "a@example.com")
    monkeypatch.setenv("MYTANITA_PASSWORD", "secret")
    assert mytanita.credentials() == ("a@example.com", "secret")


def test_local_zone_from_tz(monkeypatch):
    monkeypatch.setenv("TZ", "America/New_York")
    assert mytanita.local_zone().key == "America/New_York"
