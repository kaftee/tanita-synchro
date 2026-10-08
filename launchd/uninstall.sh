#!/bin/sh
set -eu
LABEL=com.kaftee.tanita-synchro
launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null || true
rm -f "$HOME/Library/LaunchAgents/$LABEL.plist"
echo "removed $LABEL"
