"""Garmin Connect side: session, reading existing weigh-ins, uploading body composition."""
from __future__ import annotations

import getpass
import logging
import os
import sys
from datetime import date, timedelta
from typing import Any

from garminconnect import Garmin
from garminconnect.fit import FitEncoderWeight

from .mytanita import Measurement

DEFAULT_TOKENSTORE = os.path.expanduser("~/.garminconnect")
# A Garmin entry within this distance of a Tanita measurement is the same weigh-in.
SAME_WEIGH_IN_MS = 60_000

logging.getLogger("garminconnect").setLevel(logging.ERROR)


class GarminError(RuntimeError):
    pass


class RoundingFitEncoderWeight(FitEncoderWeight):
    """garminconnect truncates scaled values (64.6 * 100 -> 6459); round them instead."""

    def _build_content_block(self, content):
        fixed = [
            (num, basetype, round(value * scale), 1)
            if value is not None and scale not in (None, 1) else (num, basetype, value, scale)
            for num, basetype, value, scale in content
        ]
        return super()._build_content_block(fixed)


def login(tokenstore: str = DEFAULT_TOKENSTORE) -> Garmin:
    """Resume the saved session; fall back to an interactive login (may ask for MFA)."""
    try:
        api = Garmin()
        api.login(tokenstore)
        return api
    except Exception as e:
        # Chained on purpose: cli.transient() looks for a network error behind this one.
        if not sys.stdin.isatty():
            raise GarminError(f"Garmin session in {tokenstore} is missing or expired; run "
                              "tanita-synchro once in a terminal to sign in again") from e
    api = Garmin(email=input("Garmin email: ").strip(), password=getpass.getpass("Garmin password: "),
                 prompt_mfa=lambda: input("Garmin sent you a verification code, enter it: ").strip())
    try:
        api.login(tokenstore)
    except Exception as e:
        raise GarminError(f"Garmin sign-in failed: {e}") from e
    return api


def weigh_ins(api: Garmin, start: date, end: date) -> list[dict[str, Any]]:
    """Every weigh-in between the dates.

    Uses the weight range endpoint: the body composition one (``weight/dateRange``)
    returns only the latest weigh-in of each day.
    """
    out = []
    while start <= end:
        chunk_end = min(start + timedelta(days=365), end)
        r = api.get_weigh_ins(start.isoformat(), chunk_end.isoformat())
        for day in r.get("dailyWeightSummaries") or []:
            out += day.get("allWeightMetrics") or []
        start = chunk_end + timedelta(days=1)
    return out


def is_in_garmin(m: Measurement, existing: list[dict[str, Any]]) -> bool:
    ts = int(m.time.timestamp() * 1000)
    return any(abs((e.get("timestampGMT") or 0) - ts) < SAME_WEIGH_IN_MS for e in existing)


def fit_file(m: Measurement) -> bytes:
    enc = RoundingFitEncoderWeight()
    enc.write_file_info()
    enc.write_file_creator()
    enc.write_device_info(m.time)
    enc.write_weight_scale(
        m.time,
        weight=m.weight,
        percent_fat=m.percent_fat,
        percent_hydration=m.percent_hydration,
        bone_mass=m.bone_mass,
        muscle_mass=m.muscle_mass,
        basal_met=m.basal_met,
        physique_rating=m.physique_rating,
        metabolic_age=m.metabolic_age,
        visceral_fat_rating=m.visceral_fat_rating,
        bmi=m.bmi,
    )
    enc.finish()
    return enc.getvalue()


def upload(api: Garmin, m: Measurement) -> None:
    files = {"file": ("body_composition.fit", fit_file(m))}
    result = api.client.post("connectapi", api.garmin_connect_upload, files=files, api=True)
    failures = ((result or {}).get("detailedImportResult") or {}).get("failures") or []
    if failures:
        raise GarminError(f"Garmin rejected the upload: {failures}")
