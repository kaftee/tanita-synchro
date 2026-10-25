"""Failure mail: tell someone when a (scheduled) run fails, so a broken sync is not missed."""
from __future__ import annotations

import getpass
import os
import smtplib
import socket
import sys
from datetime import datetime
from email.message import EmailMessage
from email.utils import formataddr, formatdate

from .mytanita import dialog, keychain_credentials, save_keychain_credentials

KEYCHAIN_SERVICE = "tanita-synchro-smtp"
DEFAULT_SERVER = "smtp.gmail.com:465"
SENDER_NAME = "Tanita synchro"


class NotifyError(RuntimeError):
    pass


def credentials() -> tuple[str, str] | None:
    """SMTP login and password from SMTP_USER / SMTP_PASSWORD, else the macOS Keychain.

    Never asks: a scheduled run has nobody to answer. ``setup`` saves them.
    """
    user, password = os.environ.get("SMTP_USER"), os.environ.get("SMTP_PASSWORD")
    if user and password:
        return user, password
    if sys.platform == "darwin":
        return keychain_credentials(KEYCHAIN_SERVICE)
    return None


def _ask_credentials() -> tuple[str, str]:
    if sys.platform == "darwin":
        user = (dialog("SMTP login (for Gmail: your Gmail address):") or "").strip()
        password = dialog("SMTP password (for Gmail: an app password):", hidden=True) if user else None
    elif sys.stdin.isatty():
        user = input("SMTP login: ").strip()
        password = getpass.getpass("SMTP password: ")
    else:
        raise NotifyError("set SMTP_USER and SMTP_PASSWORD")
    if not user or not password:
        raise NotifyError("SMTP sign-in cancelled")
    return user, password


def send(server: str, creds: tuple[str, str], to: str, sender: str | None,
         subject: str, body: str) -> None:
    """Send a plain-text mail. Port 465 uses SSL, any other port STARTTLS."""
    host, _, port = server.partition(":")
    port = int(port or 465)
    msg = EmailMessage()
    msg["From"] = formataddr((SENDER_NAME, sender or creds[0]))
    msg["To"] = to
    msg["Date"] = formatdate(localtime=True)
    msg["Subject"] = subject
    msg.set_content(body)
    step = "connect"
    try:
        with (smtplib.SMTP_SSL if port == 465 else smtplib.SMTP)(host, port, timeout=30) as s:
            if port != 465:
                step = "starttls"
                s.starttls()
            step = "login"
            s.ehlo()
            # One mechanism only: after a rejected login Gmail hangs up on the next one,
            # which would hide its "535 Username and Password not accepted".
            if "PLAIN" in s.esmtp_features.get("auth", "").upper().split():
                s.esmtp_features["auth"] = "PLAIN"
            s.login(*creds)
            step = "send"
            s.send_message(msg)
    except (smtplib.SMTPException, OSError) as e:
        raise NotifyError(f"mail via {host} failed at {step}: {e}") from e


def failure(server: str, to: str, sender: str | None, error: str) -> None:
    """Mail ``error`` to ``to``. Raises NotifyError when there is no SMTP login or sending fails."""
    creds = credentials()
    if not creds:
        raise NotifyError("no SMTP login saved; run once with --test-notify")
    body = (f"tanita-synchro failed on {socket.gethostname()} at {datetime.now():%Y-%m-%d %H:%M}:\n\n"
            f"{error}\n\n"
            "Measurements are not lost: the next successful run uploads everything still missing.\n"
            "This mail is sent after every failed run.\n")
    send(server, creds, to, sender, "tanita-synchro: sync failed", body)


def setup(server: str, to: str, sender: str | None) -> None:
    """Send a test mail, asking for the SMTP login when none is saved; save it once it works."""
    creds = credentials()
    fresh = creds is None
    if fresh:
        creds = _ask_credentials()
    send(server, creds, to, sender, "tanita-synchro: test mail",
         f"Failure mails from tanita-synchro on {socket.gethostname()} work.\n")
    if fresh and sys.platform == "darwin":
        save_keychain_credentials(creds[0], creds[1], KEYCHAIN_SERVICE)
