import smtplib

import pytest

from tanita_synchro import notify


class FakeSMTP:
    """Stands in for smtplib.SMTP / SMTP_SSL: records what a run does."""

    instances = []

    def __init__(self, host, port, timeout=None):
        self.host, self.port = host, port
        self.tls, self.login_as, self.messages = False, None, []
        self.esmtp_features = {}
        FakeSMTP.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def starttls(self):
        self.tls = True

    def ehlo(self):
        self.esmtp_features = {"auth": " LOGIN PLAIN XOAUTH2"}

    def login(self, user, password):
        if password == "wrong":
            raise smtplib.SMTPAuthenticationError(535, b"Username and Password not accepted")
        self.login_as = user

    def send_message(self, msg):
        self.messages.append(msg)


@pytest.fixture
def smtp(monkeypatch):
    FakeSMTP.instances = []
    monkeypatch.setattr(notify.smtplib, "SMTP_SSL", FakeSMTP)
    monkeypatch.setattr(notify.smtplib, "SMTP", FakeSMTP)
    monkeypatch.delenv("SMTP_USER", raising=False)
    monkeypatch.delenv("SMTP_PASSWORD", raising=False)
    return FakeSMTP.instances


def test_send_over_ssl(smtp):
    notify.send("smtp.example.com:465", ("me@example.com", "secret"), "to@example.com",
                "bot@example.com", "subject", "body")
    s, = smtp
    assert (s.host, s.port, s.tls, s.login_as) == ("smtp.example.com", 465, False, "me@example.com")
    assert s.esmtp_features["auth"] == "PLAIN"
    msg, = s.messages
    assert msg["From"] == "Tanita synchro <bot@example.com>"
    assert msg["To"] == "to@example.com" and msg["Subject"] == "subject"


def test_send_with_starttls_and_default_sender(smtp):
    notify.send("smtp.example.com:587", ("me@example.com", "secret"), "to@example.com",
                None, "subject", "body")
    s, = smtp
    assert s.tls
    assert s.messages[0]["From"] == "Tanita synchro <me@example.com>"


def test_rejected_login_raises(smtp):
    with pytest.raises(notify.NotifyError, match="535"):
        notify.send("smtp.example.com", ("me@example.com", "wrong"), "to@example.com",
                    None, "subject", "body")


def test_failure_mail_carries_the_error(smtp, monkeypatch):
    monkeypatch.setenv("SMTP_USER", "me@example.com")
    monkeypatch.setenv("SMTP_PASSWORD", "secret")
    notify.failure("smtp.example.com", "to@example.com", None, "error: Garmin session expired")
    assert "error: Garmin session expired" in smtp[0].messages[0].get_content()


def test_failure_without_login_raises(smtp, monkeypatch):
    monkeypatch.setattr(notify, "keychain_credentials", lambda service: None)
    with pytest.raises(notify.NotifyError, match="--test-notify"):
        notify.failure("smtp.example.com", "to@example.com", None, "error")
    assert smtp == []


def test_setup_saves_the_login_only_after_it_works(smtp, monkeypatch):
    saved = []
    monkeypatch.setattr(notify, "keychain_credentials", lambda service: None)
    monkeypatch.setattr(notify, "save_keychain_credentials", lambda *a: saved.append(a))
    monkeypatch.setattr(notify.sys, "platform", "darwin")
    answers = iter(["me@example.com", "wrong", "me@example.com", "secret"])
    monkeypatch.setattr(notify, "dialog", lambda prompt, hidden=False: next(answers))
    with pytest.raises(notify.NotifyError):
        notify.setup("smtp.example.com", "to@example.com", None)
    assert saved == []
    notify.setup("smtp.example.com", "to@example.com", None)
    assert saved == [("me@example.com", "secret", notify.KEYCHAIN_SERVICE)]
