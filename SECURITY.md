# Security policy

## Supported versions

Only the latest release on [PyPI](https://pypi.org/project/tanita-synchro/)
receives fixes.

## Reporting a vulnerability

Please **do not open a public issue** for a security problem. Report it
privately through GitHub instead:
[Report a vulnerability](https://github.com/kaftee/tanita-synchro/security/advisories/new).

Include what you found, how to reproduce it and what it affects. You can expect
a first answer within a week.

## How credentials are handled

- The MyTanita password and the SMTP login are kept in the macOS Keychain (or
  read from environment variables). They are never written to files or logs,
  and are passed to the `security` tool on stdin, not on its command line.
- The Garmin session is cached by the `garminconnect` library in
  `~/.garminconnect`; anyone who can read that directory can use your Garmin
  session.
- Nothing is sent anywhere except mytanita.eu, Garmin Connect and, with
  `--notify`, your SMTP server.
