#!/bin/sh
# Double-click on macOS or Linux to start PokerNow Tracker.
cd "$(dirname "$0")" || exit 1
exec python3 launch.py "$@"
