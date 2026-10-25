# Troubleshooting

## Signing in

### `error: MyTanita sign-in failed: check email and password`

The saved or provided credentials were rejected by mytanita.eu. Check that you
can sign in at <https://mytanita.eu/en/user/login>. On macOS, remove the saved
item and run again to be asked anew:

```bash
security delete-generic-password -s mytanita.eu
```

### `error: Garmin session in ~/.garminconnect is missing or expired`

A scheduled run cannot ask for your Garmin password. Run `tanita-synchro` once
in a terminal to sign in (and enter the MFA code if asked); scheduled runs then
reuse the new session.

### Garmin sign-in fails with `429`

Garmin rate-limits sign-ins. Wait a while (up to an hour) and try again. With a
cached session in `--tokenstore`, sign-in is rarely needed.

## Results

### A measurement has the wrong time in Garmin

The export has no time zone; it is read in the system zone. If you measured in
another zone, pass `--timezone`, e.g. `--timezone Europe/Warsaw`.

### A measurement is uploaded again on every run

The sync checks Garmin for a weigh-in within one minute of the measurement. If
Garmin did not keep an upload (the run says `ok` but the weigh-in is missing in
Garmin Connect), please [open a bug report](https://github.com/kaftee/tanita-synchro/issues/new?template=bug_report.yml).

### Garmin shows a different visceral fat value

Garmin stores the visceral fat rating as a whole number, so Tanita's 6.5 shows
as 6.

### Some uploads failed (exit code 1)

The other measurements went through. Run the same command again: only the
missing ones are uploaded.

## Failure mail

### `not mailed: no SMTP login saved; run once with --test-notify`

The SMTP login is saved by `--test-notify`, never by a scheduled run. Run it
once in a terminal with the same `--notify` and `--mail-from` options.

### `mail via smtp.gmail.com failed at login: (535, ...)` or `(534, ... Application-specific password required)`

Gmail rejected the login: 535 for an unknown login or a wrong password, 534
for the account password instead of an
[app password](https://myaccount.google.com/apppasswords). The login is the
Google account's own address, not a *Send mail as* alias. Replace the saved
login and test again:

```bash
security delete-generic-password -s tanita-synchro-smtp
tanita-synchro --test-notify --notify you@example.com
```

### The mail comes from the Gmail address, not from `--mail-from`

Gmail sends only from addresses added under Settings → Accounts and Import →
*Send mail as*. Add and verify the address there.

## Undoing an upload

Delete the weigh-in in Garmin Connect (Health Stats → Weight → the bin icon next
to the entry). It will be uploaded again on the next run that covers its date,
unless you narrow the window with `--since`.
