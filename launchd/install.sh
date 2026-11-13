#!/bin/sh
# Install (or reinstall) the launchd agent that runs tanita-synchro at 9:30 and 20:00.
# Arguments are passed on to every run, e.g. launchd/install.sh --notify you@example.com
# SCHEDULE sets other times (HH:MM, space-separated), e.g. SCHEDULE="7:45 8:45 20:00" launchd/install.sh
set -eu
LABEL=com.kaftee.tanita-synchro
DIR=$(cd "$(dirname "$0")/.." && pwd)
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
LOG="$HOME/Library/Logs/tanita-synchro.log"
ARGS=""
for a in "$@"; do
    a=$(printf '%s' "$a" | sed -e 's/&/\&amp;/g' -e 's/</\&lt;/g' -e 's/>/\&gt;/g')
    ARGS="$ARGS<string>$a</string>"
done
TIMES=""
for t in ${SCHEDULE:-9:30 20:00}; do
    case "$t" in
        [0-9]:[0-5][0-9] | [01][0-9]:[0-5][0-9] | 2[0-3]:[0-5][0-9]) ;;
        *) echo "SCHEDULE: '$t' is not HH:MM" >&2; exit 1 ;;
    esac
    TIMES="$TIMES
        <dict><key>Hour</key><integer>$((10#${t%%:*}))</integer><key>Minute</key><integer>$((10#${t#*:}))</integer></dict>"
done

cat > "$PLIST" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key><string>$LABEL</string>
    <key>ProgramArguments</key>
    <array><string>$DIR/.venv/bin/tanita-synchro</string>$ARGS</array>
    <key>WorkingDirectory</key><string>$DIR</string>
    <key>EnvironmentVariables</key>
    <dict><key>PYTHONUNBUFFERED</key><string>1</string></dict>
    <key>StartCalendarInterval</key>
    <array>$TIMES
    </array>
    <key>StandardOutPath</key><string>$LOG</string>
    <key>StandardErrorPath</key><string>$LOG</string>
</dict>
</plist>
PLIST

launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$PLIST"
echo "installed $PLIST (log: $LOG)"
echo "run now: launchctl kickstart gui/$(id -u)/$LABEL"
