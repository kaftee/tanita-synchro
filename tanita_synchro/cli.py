"""tanita-synchro: copy MyTanita body composition measurements to Garmin Connect.

Garmin itself is the record of what has been synced: a measurement is skipped
when Garmin already has a weigh-in at the same time, so runs are safe to repeat.
"""
from __future__ import annotations

import argparse
import sys
import time
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from . import __version__, garmin
from .mytanita import MyTanita, MyTanitaError, credentials

EXIT_OK, EXIT_UPLOAD_FAILED, EXIT_ERROR = 0, 1, 2


def _log(msg: str, err: bool = False) -> None:
    print(f"{datetime.now():%Y-%m-%d %H:%M:%S} {msg}", file=sys.stderr if err else sys.stdout)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="tanita-synchro",
        description="Copy MyTanita body composition measurements to Garmin Connect.")
    window = p.add_mutually_exclusive_group()
    window.add_argument("--since", type=date.fromisoformat, metavar="YYYY-MM-DD",
                        help="sync measurements from this date (default: the last 30 days)")
    window.add_argument("--all", action="store_true", help="sync the whole MyTanita history")
    p.add_argument("--dry-run", action="store_true",
                   help="show what would be uploaded without uploading")
    p.add_argument("--tokenstore", default=garmin.DEFAULT_TOKENSTORE,
                   help="directory with the saved Garmin session (default: %(default)s)")
    p.add_argument("--timezone", type=ZoneInfo, metavar="ZONE",
                   help="time zone of the MyTanita times, e.g. Europe/Warsaw (default: system)")
    p.add_argument("--delay", type=float, default=1.0, metavar="SECONDS",
                   help="pause between uploads (default: %(default)s)")
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return sync(args)
    except (MyTanitaError, garmin.GarminError) as e:
        _log(f"error: {e}", err=True)
        return EXIT_ERROR
    except KeyboardInterrupt:
        return EXIT_ERROR


def sync(args: argparse.Namespace) -> int:
    tanita = MyTanita()
    tanita.login(*credentials())
    measurements = tanita.measurements(args.timezone)
    if not args.all:
        since = args.since or date.today() - timedelta(days=30)
        measurements = [m for m in measurements if m.time.date() >= since]
    if not measurements:
        _log("No MyTanita measurements in range.")
        return EXIT_OK

    api = garmin.login(args.tokenstore)
    existing = garmin.weigh_ins(api, measurements[0].time.date() - timedelta(days=1),
                                measurements[-1].time.date() + timedelta(days=1))
    todo = [m for m in measurements if not garmin.is_in_garmin(m, existing)]
    _log(f"MyTanita: {len(measurements)} measurements "
         f"({measurements[0].time:%Y-%m-%d} .. {measurements[-1].time:%Y-%m-%d}), "
         f"already in Garmin: {len(measurements) - len(todo)}, to upload: {len(todo)}")

    failed = 0
    for i, m in enumerate(todo, 1):
        label = f"[{i}/{len(todo)}] {m.time:%Y-%m-%d %H:%M} {m.weight:.2f} kg"
        if args.dry_run:
            print(label, "(dry run)")
            continue
        try:
            garmin.upload(api, m)
            print(label, "ok")
        except Exception as e:
            failed += 1
            print(label, "FAILED:", e, file=sys.stderr)
        if i < len(todo):
            time.sleep(args.delay)

    if failed:
        _log(f"{failed} of {len(todo)} uploads failed", err=True)
        return EXIT_UPLOAD_FAILED
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
