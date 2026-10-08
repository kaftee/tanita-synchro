# Usage

```bash
tanita-synchro [--since YYYY-MM-DD | --all] [--dry-run] [--timezone ZONE]
               [--tokenstore DIR] [--delay SECONDS] [--version]
```

Each run signs in to MyTanita, downloads the measurement export, asks Garmin
which weigh-ins it already has in that period and uploads the rest. A first
run with `--all` brings over your whole history; after that the default window
(the last 30 days) is enough.

## Options

| Option | Default | Meaning |
|---|---|---|
| `--since YYYY-MM-DD` | 30 days ago | Sync measurements taken on or after this date. |
| `--all` | — | Sync the whole MyTanita history. |
| `--dry-run` | — | List what would be uploaded, upload nothing. |
| `--timezone ZONE` | system zone | Time zone the measurements were taken in, e.g. `Europe/Warsaw`. |
| `--tokenstore DIR` | `~/.garminconnect` | Where the Garmin session is kept. |
| `--delay SECONDS` | `1.0` | Pause between uploads, to stay gentle with Garmin. |
| `--version` | — | Print the version and exit. |

### Credentials

**MyTanita** — the first match wins:

1. `MYTANITA_EMAIL` and `MYTANITA_PASSWORD` environment variables.
2. On macOS, the login Keychain item with service `mytanita.eu`.
3. Otherwise you are asked: a dialog on macOS, the terminal elsewhere. The
   credentials are checked by signing in and, on macOS, saved to the Keychain.

To change the saved password: `security delete-generic-password -s mytanita.eu`,
then run `tanita-synchro` again.

**Garmin** — the session is cached in `--tokenstore` (`~/.garminconnect`, the
same default as [activy-checker](https://github.com/kaftee/activy-checker) and
the `garminconnect` library). Without a valid session you are asked for your
Garmin email, password and, with two-step verification, the emailed code. In a
scheduled (non-interactive) run a missing session is an error instead.

### Time zone

The MyTanita export has local times without an offset. They are read in the
system time zone (or `TZ`, or `--timezone`), with daylight saving time applied
per date, and sent to Garmin in UTC.

## Running on a schedule (macOS)

```bash
launchd/install.sh
```

installs a launchd agent (`com.kaftee.tanita-synchro`) that runs the sync from
this checkout at 10:00 and 20:00. If the Mac was asleep, the missed run happens
after wake. Output goes to `~/Library/Logs/tanita-synchro.log`.

```bash
launchctl kickstart gui/$(id -u)/com.kaftee.tanita-synchro   # run now
launchd/uninstall.sh                                        # remove
```

Sign in to Garmin once in a terminal before installing, so the session exists.

## Exit codes

| Code | Meaning |
|---|---|
| 0 | Everything in range is in Garmin (or nothing to do). |
| 1 | Some uploads failed; the others went through. Run again to retry. |
| 2 | Could not sign in to MyTanita or Garmin. |
