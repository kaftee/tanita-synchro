# Changelog

## Unreleased

### Added
- Failure mail: `--notify ADDRESS` mails the error when a run fails, over SMTP
  (`--smtp-server`, Gmail by default; `--mail-from` for the sender).
  `--test-notify` sends a test mail and saves the SMTP login to the macOS
  Keychain; `SMTP_USER` / `SMTP_PASSWORD` work too.
- `launchd/install.sh` passes its arguments on to every scheduled run;
  `SCHEDULE="HH:MM ..."` sets other run times than 9:30 and 20:00.
- Retries: a run that fails on the network (e.g. MyTanita resetting the
  connection) or on a MyTanita / Garmin server error runs again after 1, 5 and
  15 minutes (`--retries N`, default 3, `0` turns it off). A wrong password or
  an expired Garmin session is not retried.
- `--after-upload COMMAND` runs a shell command after a run that uploaded
  something, e.g. to make another app fetch the new weigh-in.

### Changed
- An unexpected error (e.g. no network) now ends the run with exit code 2 (was
  1, the same as failed uploads).

## 0.1.0

First release.

### Added
- Sign in to MyTanita (mytanita.eu) and read measurements from the CSV export.
- Upload measurements to Garmin Connect as FIT `weight_scale` records with the
  original time: weight, BMI, body fat, body water, muscle mass, bone mass, BMR,
  metabolic age, physique rating and visceral fat rating.
- Skip measurements Garmin already has (matched by time), so runs are repeatable.
- `--since`, `--all`, `--dry-run`, `--timezone`, `--tokenstore`, `--delay`,
  `--version` options.
- MyTanita credentials from `MYTANITA_EMAIL` / `MYTANITA_PASSWORD`, or the macOS
  Keychain (asked for once with a dialog).
- launchd agent for running the sync twice a day on macOS.
