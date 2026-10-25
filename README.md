# tanita-synchro

[![tests](https://github.com/kaftee/tanita-synchro/actions/workflows/tests.yml/badge.svg)](https://github.com/kaftee/tanita-synchro/actions/workflows/tests.yml)

Copy your [Tanita](https://tanita.eu) scale measurements from
[MyTanita](https://mytanita.eu) to [Garmin Connect](https://connect.garmin.com):
weight and full body composition, with the original date and time, as if they
came from a Garmin Index scale.

```
2026-10-08 10:00:02 MyTanita: 12 measurements (2026-09-08 .. 2026-10-08), already in Garmin: 11, to upload: 1
[1/1] 2026-10-08 07:41 70.40 kg ok
```

## Why I built this

My Tanita RD-953 talks only to the My TANITA app. Garmin Connect, where the rest
of my training and health data lives, cannot read weight from it, and it does
not read weight from Apple Health either. Typing weigh-ins in by hand loses
everything except the weight and is easy to forget.

`tanita-synchro` signs in to your MyTanita account, downloads the measurement
export and uploads every measurement Garmin does not have yet. Run it once to
bring over your whole history, then let it run on a schedule.

## Features

- **Full body composition** — weight, BMI, body fat, body water, muscle mass,
  bone mass, BMR, metabolic age, physique rating and visceral fat rating.
- **Original timestamps** — each weigh-in keeps the date and time it was taken.
- **Safe to repeat** — measurements already in Garmin are skipped, so you can run
  it as often as you like; nothing is stored locally.
- **History backfill** — `--all` uploads everything in your MyTanita account.
- **Dry run** — `--dry-run` shows what would be uploaded.
- **Scheduling on macOS** — a launchd agent runs the sync twice a day.
- **Failure mail** — `--notify` mails you when a run fails, e.g. when the
  Garmin session has expired (SMTP, Gmail by default).
- Your MyTanita password stays in the macOS Keychain (or in environment
  variables); the Garmin session is cached so MFA is needed only once.

## Disclaimer

This is an **unofficial** tool, not affiliated with or endorsed by Tanita or
Garmin. Neither MyTanita nor Garmin Connect offers a public API for this, so
`tanita-synchro` uses the MyTanita website's CSV export and the upload endpoint
of Garmin Connect, signing in with your own credentials. Use it only with
**your own accounts and your own data**, at your own risk. Either service can
change without notice and break the tool.

## Quick start

Requires **Python 3.12+**. The easiest way is [pipx](https://pipx.pypa.io):

```bash
pipx install tanita-synchro
tanita-synchro --all --dry-run     # see what would be uploaded
tanita-synchro --all               # upload your whole history
```

On the first run you are asked for your MyTanita email and password (a dialog
on macOS, saved to the Keychain), then for your Garmin email, password and — if
your account uses two-step verification — the code Garmin emails you.

## Common commands

```bash
tanita-synchro                         # the last 30 days (default)
tanita-synchro --since 2026-09-01
tanita-synchro --all                   # the whole MyTanita history
tanita-synchro --dry-run               # show, do not upload
tanita-synchro --timezone Europe/Warsaw
```

## Running on a schedule (macOS)

From a git checkout with its `.venv` set up (see
[Contributing](https://github.com/kaftee/tanita-synchro/blob/main/CONTRIBUTING.md#development-setup)):

```bash
launchd/install.sh      # runs at 9:30 and 20:00; missed runs happen after wake
launchd/install.sh --notify you@example.com   # the same, mailing you when a run fails
tail -f ~/Library/Logs/tanita-synchro.log
launchd/uninstall.sh
```

## Documentation

- [Usage](https://github.com/kaftee/tanita-synchro/blob/main/docs/usage.md) — options, credentials, scheduling, exit codes
- [How it works](https://github.com/kaftee/tanita-synchro/blob/main/docs/how-it-works.md) — MyTanita export, field mapping, Garmin upload
- [Troubleshooting](https://github.com/kaftee/tanita-synchro/blob/main/docs/troubleshooting.md)
- [Contributing](https://github.com/kaftee/tanita-synchro/blob/main/CONTRIBUTING.md)
- [Changelog](https://github.com/kaftee/tanita-synchro/blob/main/CHANGELOG.md)

## License

[MIT](https://github.com/kaftee/tanita-synchro/blob/main/LICENSE)
