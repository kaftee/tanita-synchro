"""MyTanita (mytanita.eu) client: log in and download measurements as CSV."""
from __future__ import annotations

import csv
import getpass
import io
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

BASE = "https://mytanita.eu"
KEYCHAIN_SERVICE = "mytanita.eu"


class MyTanitaError(RuntimeError):
    pass


@dataclass
class Measurement:
    time: datetime  # timezone-aware, local
    weight: float
    bmi: float | None
    percent_fat: float | None
    visceral_fat_rating: float | None
    muscle_mass: float | None
    bone_mass: float | None
    basal_met: float | None
    metabolic_age: float | None
    percent_hydration: float | None
    physique_rating: float | None


def dialog(prompt: str, hidden: bool = False) -> str | None:
    """Ask in a macOS dialog; None when cancelled."""
    script = (f'display dialog "{prompt}" default answer "" '
              f'{"with hidden answer " if hidden else ""}'
              'with title "tanita-synchro" buttons {"Cancel", "OK"} default button "OK"')
    r = subprocess.run(["osascript", "-e", script, "-e", "text returned of result"],
                       capture_output=True, text=True)
    return r.stdout.rstrip("\n") if r.returncode == 0 else None


def credentials() -> tuple[str, str]:
    """MyTanita email and password.

    Taken from MYTANITA_EMAIL / MYTANITA_PASSWORD, else from the macOS Keychain.
    When neither has them, they are asked for (a dialog on macOS, the terminal
    elsewhere), checked by signing in, and saved to the Keychain on macOS.
    """
    email, password = os.environ.get("MYTANITA_EMAIL"), os.environ.get("MYTANITA_PASSWORD")
    if email and password:
        return email, password
    if sys.platform == "darwin":
        creds = keychain_credentials()
        if creds:
            return creds
        email = dialog("MyTanita email:")
        password = dialog("MyTanita password:", hidden=True) if email is not None else None
        if email is None or password is None:
            raise MyTanitaError("MyTanita sign-in cancelled")
    elif sys.stdin.isatty():
        email = input("MyTanita email: ").strip()
        password = getpass.getpass("MyTanita password: ")
    else:
        raise MyTanitaError("Set MYTANITA_EMAIL and MYTANITA_PASSWORD")
    MyTanita().login(email, password)
    if sys.platform == "darwin":
        save_keychain_credentials(email, password)
    return email, password


def keychain_credentials(service: str = KEYCHAIN_SERVICE) -> tuple[str, str] | None:
    r = subprocess.run(["security", "find-generic-password", "-s", service, "-g"],
                       capture_output=True, text=True)
    if r.returncode != 0:
        return None
    acct = re.search(r'"acct"<blob>="([^"]*)"', r.stdout)
    pw = re.search(r'password: "(.*)"', r.stderr)
    return (acct.group(1), pw.group(1)) if acct and pw else None


def save_keychain_credentials(account: str, password: str, service: str = KEYCHAIN_SERVICE) -> None:
    subprocess.run(["security", "add-generic-password", "-U", "-s", service,
                    "-a", account, "-w", password], check=True)


def local_zone() -> ZoneInfo:
    """The system time zone (MyTanita exports local times without an offset)."""
    if os.environ.get("TZ"):
        return ZoneInfo(os.environ["TZ"])
    link = os.path.realpath("/etc/localtime")
    if "zoneinfo/" in link:
        return ZoneInfo(link.split("zoneinfo/", 1)[1])
    return ZoneInfo("UTC")


class MyTanita:
    def __init__(self) -> None:
        self.s = requests.Session()
        self.s.headers["User-Agent"] = (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36")

    def login(self, email: str, password: str) -> None:
        page = self.s.get(f"{BASE}/en/user/login", timeout=30)
        page.raise_for_status()
        token = BeautifulSoup(page.text, "html.parser").find("input", {"name": "token"})["value"]
        r = self.s.post(f"{BASE}/en/user/processlogin", timeout=30,
                        data={"mail": email, "password": password, "token": token, "login": "Login"})
        r.raise_for_status()
        if "processlogin" in r.text:
            raise MyTanitaError("MyTanita sign-in failed: check email and password")

    def export_csv(self) -> str:
        r = self.s.get(f"{BASE}/en/user/export-csv", timeout=60)
        r.raise_for_status()
        return r.content.decode("utf-8-sig")

    def measurements(self, tz: ZoneInfo | None = None) -> list[Measurement]:
        return parse_csv(self.export_csv(), tz)


def _num(v: str) -> float | None:
    v = (v or "").strip()
    if v in ("", "-"):
        return None
    return float(v)


def parse_csv(text: str, tz: ZoneInfo | None = None) -> list[Measurement]:
    tz = tz or local_zone()
    out = []
    for row in csv.DictReader(io.StringIO(text)):
        out.append(Measurement(
            time=datetime.strptime(row["Date"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=tz),
            weight=float(row["Weight (kg)"]),
            bmi=_num(row["BMI"]),
            percent_fat=_num(row["Body Fat (%)"]),
            visceral_fat_rating=_num(row["Visc Fat"]),  # Tanita reports a rating, not a mass
            muscle_mass=_num(row["Muscle Mass (kg)"]),
            bone_mass=_num(row["Bone Mass (kg)"]),
            basal_met=_num(row["BMR (kcal)"]),
            metabolic_age=_num(row["Metab Age"]),
            percent_hydration=_num(row["Body Water (%)"]),
            physique_rating=_num(row["Physique Rating"]),
        ))
    # The export can repeat a measurement; keep one per timestamp
    return sorted({m.time: m for m in out}.values(), key=lambda m: m.time)
