# Usage

```bash
tanita-synchro [--since YYYY-MM-DD | --all] [--dry-run] [--timezone ZONE]
               [--tokenstore DIR] [--delay SECONDS] [--version]
               [--notify ADDRESS [--mail-from ADDRESS] [--smtp-server HOST[:PORT]]]
tanita-synchro --test-notify --notify ADDRESS [--mail-from ADDRESS] [--smtp-server HOST[:PORT]]
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
| `--notify ADDRESS` | — | Mail this address when the run fails (see [Failure mail](#failure-mail)). |
| `--mail-from ADDRESS` | SMTP login | Sender of the failure mail. |
| `--smtp-server HOST[:PORT]` | `smtp.gmail.com:465` | SMTP server; port 465 uses SSL, any other port STARTTLS. |
| `--test-notify` | — | Send a test mail to `--notify`, asking for the SMTP login once, and exit. |

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

**SMTP** (only for `--notify`) — `SMTP_USER` and `SMTP_PASSWORD`, else on macOS
the Keychain item with service `tanita-synchro-smtp`. A normal run never asks
for them; `--test-notify` does (a dialog on macOS, the terminal elsewhere) and,
on macOS, saves them to the Keychain once the test mail has gone out. To change
them: `security delete-generic-password -s tanita-synchro-smtp`, then run
`--test-notify` again.

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
Arguments to `install.sh` are passed on to every run, e.g.
`launchd/install.sh --notify you@example.com`.

## Failure mail

A scheduled run that fails (an expired Garmin session, a wrong MyTanita
password, no network) only writes to the log. With `--notify ADDRESS`, every
failed run also sends a short mail with the error. Nothing is lost while the
sync is broken: the next successful run uploads whatever is still missing in its
window. Dry runs never mail.

With Gmail as the SMTP server (the default):

1. Turn on 2-Step Verification for the Google account and create an
   [app password](https://myaccount.google.com/apppasswords); the normal
   password is not accepted over SMTP.
2. To send from another address than the Gmail one, add it in Gmail under
   Settings → Accounts and Import → *Send mail as*; otherwise Gmail replaces
   the sender with the Gmail address.
3. Send a test mail; it asks for the Gmail address and the app password:

   ```bash
   tanita-synchro --test-notify --notify you@example.com --mail-from sync@example.com
   ```

4. Add the same `--notify` / `--mail-from` options to the scheduled runs:

   ```bash
   launchd/install.sh --notify you@example.com --mail-from sync@example.com
   ```

If the mail itself cannot be sent, the run logs `not mailed: ...` and keeps its
exit code.

## Exit codes

| Code | Meaning |
|---|---|
| 0 | Everything in range is in Garmin (or nothing to do). |
| 1 | Some uploads failed; the others went through. Run again to retry. |
| 2 | Could not sign in to MyTanita or Garmin, or another error stopped the run. |
