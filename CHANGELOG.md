# Changelog

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
