import struct
from datetime import date

import pytest

from tanita_synchro import garmin
from tanita_synchro.mytanita import parse_csv

from .conftest import WARSAW


def _weight_scale_values(data):
    # weight_scale data record starts with timestamp (uint32) followed by weight, fat,
    # hydration, visceral fat mass, bone and muscle mass (uint16, scale 100)
    for i in range(len(data) - 16):
        values = struct.unpack_from("<IHHHHHH", data, i)
        if values[1] == 7040 and values[2] == 1820:
            return values
    raise AssertionError("weight_scale record not found")


def test_fit_values_are_rounded_not_truncated(csv_text):
    m = parse_csv(csv_text, WARSAW)[1]
    _, weight, fat, hydration, visceral_mass, bone, muscle = _weight_scale_values(garmin.fit_file(m))
    # 54.3 * 100 is 5429.999... in floating point; garminconnect alone would store 5429
    assert (weight, fat, hydration, bone, muscle) == (7040, 1820, 5780, 290, 5430)
    assert visceral_mass == 0xFFFF  # not sent: Tanita gives a rating, not a mass


def test_fit_timestamp_is_utc(csv_text):
    m = parse_csv(csv_text, WARSAW)[1]  # 2026-03-02 07:15 CET = 06:15 UTC
    ts = _weight_scale_values(garmin.fit_file(m))[0]
    assert ts + 631065600 == int(m.time.timestamp())


def test_is_in_garmin_matches_gmt_timestamp(csv_text):
    m = parse_csv(csv_text, WARSAW)[0]
    ms = int(m.time.timestamp() * 1000)
    assert garmin.is_in_garmin(m, [{"timestampGMT": ms + 30_000}])
    assert not garmin.is_in_garmin(m, [{"timestampGMT": ms + 3_600_000}])
    assert not garmin.is_in_garmin(m, [])


def test_weigh_ins_returns_every_entry_of_a_day(fake_garmin):
    api = fake_garmin(existing=[
        {"calendarDate": "2026-01-10", "timestampGMT": 1},
        {"calendarDate": "2026-01-10", "timestampGMT": 2},
        {"calendarDate": "2026-02-01", "timestampGMT": 3},
    ])
    assert [e["timestampGMT"] for e in garmin.weigh_ins(api, date(2026, 1, 1), date(2026, 3, 1))] == [1, 2, 3]


def test_weigh_ins_splits_long_ranges(fake_garmin):
    api = fake_garmin()
    garmin.weigh_ins(api, date(2023, 12, 1), date(2026, 10, 8))
    assert api.ranges[0][0] == "2023-12-01" and api.ranges[-1][1] == "2026-10-08"
    assert len(api.ranges) == 3


def test_upload_raises_when_garmin_rejects(csv_text, fake_garmin):
    m = parse_csv(csv_text, WARSAW)[0]
    with pytest.raises(garmin.GarminError):
        garmin.upload(fake_garmin(fail=True), m)
