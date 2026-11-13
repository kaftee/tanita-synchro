"""tanita-synchro: copy MyTanita body composition measurements to Garmin Connect.

Garmin itself is the record of what has been synced: a measurement is skipped
when Garmin already has a weigh-in at the same time, so runs are safe to repeat.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
import traceback
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import requests

from . import __version__, garmin, notify
from .mytanita import MyTanita, MyTanitaError, credentials

EXIT_OK, EXIT_UPLOAD_FAILED, EXIT_ERROR = 0, 1, 2
# Pauses before each new try after a network failure or a server error (seconds); further tries wait the last one.
# Three tries take a scheduled 9:30 run to about 9:52 at most.
RETRY_DELAYS = (60, 300, 900)
AFTER_UPLOAD_TIMEOUT = 600  # seconds


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
    p.add_argument("--retries", type=int, default=len(RETRY_DELAYS), metavar="N",
                   help="run again up to N times after a network failure or a MyTanita/Garmin server error, "
                        f"waiting {', '.join(f'{d // 60} min' for d in RETRY_DELAYS)} (default: %(default)s)")
    p.add_argument("--after-upload", metavar="COMMAND",
                   help="shell command to run after a run that uploaded something, e.g. to tell another app")
    mail = p.add_argument_group("failure mail")
    mail.add_argument("--notify", metavar="ADDRESS", help="mail this address when the run fails")
    mail.add_argument("--mail-from", metavar="ADDRESS",
                      help="sender of the mail (default: the SMTP login)")
    mail.add_argument("--smtp-server", default=notify.DEFAULT_SERVER, metavar="HOST[:PORT]",
                      help="SMTP server; port 465 uses SSL, others STARTTLS (default: %(default)s)")
    mail.add_argument("--test-notify", action="store_true",
                      help="send a test mail to --notify, asking for the SMTP login once, and exit")
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.test_notify:
        if not args.notify:
            parser.error("--test-notify needs --notify ADDRESS")
        try:
            notify.setup(args.smtp_server, args.notify, args.mail_from)
        except notify.NotifyError as e:
            _log(f"error: {e}", err=True)
            return EXIT_ERROR
        _log(f"Test mail sent to {args.notify}.")
        return EXIT_OK

    error = None
    try:
        code, uploaded = sync_with_retries(args)
        if code == EXIT_UPLOAD_FAILED:
            error = "Some uploads to Garmin failed; the next run retries them."
        if uploaded and args.after_upload and not args.dry_run:
            after_upload(args.after_upload)
    except (MyTanitaError, garmin.GarminError) as e:
        _log(f"error: {e}", err=True)
        code, error = EXIT_ERROR, f"error: {e}"
    except KeyboardInterrupt:
        return EXIT_ERROR
    except Exception as e:
        traceback.print_exc()
        code, error = EXIT_ERROR, "".join(traceback.format_exception_only(e)).strip()
    if error and args.notify and not args.dry_run:
        try:
            notify.failure(args.smtp_server, args.notify, args.mail_from, error)
            _log(f"Failure mailed to {args.notify}.")
        except notify.NotifyError as e:
            _log(f"not mailed: {e}", err=True)
    return code


def after_upload(command: str) -> None:
    """Run the --after-upload command; its failure is only logged (the weigh-ins are in Garmin either way)."""
    _log(f"after upload: {command}")
    try:
        r = subprocess.run(command, shell=True, timeout=AFTER_UPLOAD_TIMEOUT)
    except subprocess.TimeoutExpired:
        _log(f"after upload: still running after {AFTER_UPLOAD_TIMEOUT} s, stopped", err=True)
        return
    if r.returncode:
        _log(f"after upload: exit code {r.returncode}", err=True)


def transient(e: BaseException) -> bool:
    """A network failure or a server error (5xx), here or anywhere in the exception chain: worth another try.

    The chain matters because a failed Garmin session resume surfaces as GarminError with the network error as its
    context.
    """
    seen: set[int] = set()
    cur: BaseException | None = e
    while cur is not None and id(cur) not in seen:
        seen.add(id(cur))
        if isinstance(cur, (requests.ConnectionError, requests.Timeout, ConnectionError, TimeoutError)):
            return True
        if isinstance(cur, requests.HTTPError) and cur.response is not None and cur.response.status_code >= 500:
            return True
        cur = cur.__cause__ or cur.__context__
    return False


def sync_with_retries(args: argparse.Namespace) -> tuple[int, int]:
    """sync(), run again after a transient failure; safe because a run skips what Garmin already has."""
    delays = [RETRY_DELAYS[min(i, len(RETRY_DELAYS) - 1)] for i in range(max(args.retries, 0))]
    for attempt, delay in enumerate([*delays, None]):
        try:
            return sync(args)
        except Exception as e:
            if delay is None or not transient(e):
                raise
            reason = "".join(traceback.format_exception_only(e)).strip()
            _log(f"{reason[:300]}; trying again in {delay // 60} min ({attempt + 1}/{len(delays)})", err=True)
            time.sleep(delay)
    raise AssertionError("unreachable")


def sync(args: argparse.Namespace) -> tuple[int, int]:
    """Exit code and the number of measurements uploaded."""
    tanita = MyTanita()
    tanita.login(*credentials())
    measurements = tanita.measurements(args.timezone)
    if not args.all:
        since = args.since or date.today() - timedelta(days=30)
        measurements = [m for m in measurements if m.time.date() >= since]
    if not measurements:
        _log("No MyTanita measurements in range.")
        return EXIT_OK, 0

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

    uploaded = 0 if args.dry_run else len(todo) - failed
    if failed:
        _log(f"{failed} of {len(todo)} uploads failed", err=True)
        return EXIT_UPLOAD_FAILED, uploaded
    return EXIT_OK, uploaded


if __name__ == "__main__":
    sys.exit(main())
