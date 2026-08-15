#!/bin/bash
# Runs the full sync cycle in order — sync_leads.py must go first, since
# everything else (alerts, anomaly checks, webhook export) depends on
# fresh lead/cost data existing before they check it.
#
# Scheduled via launchd (see ~/Library/LaunchAgents/com.lsacompanion.sync.plist)
# every 30 minutes, matching the capacity math from Phase 1 (Explorer
# access's 2,880 ops/day cap).

cd "$(dirname "$0")" || exit 1

# Absolute path, not just "python3" — launchd runs with a minimal PATH
# that doesn't match an interactive shell's, confirmed the hard way: the
# first scheduled run silently used a different, package-less Python 3.9
# instead of the 3.14 install everything was actually built/tested against.
PYTHON="/Library/Frameworks/Python.framework/Versions/3.14/bin/python3"

LOG_FILE="sync.log"
echo "=== Sync run started: $(date) ===" >> "$LOG_FILE"

"$PYTHON" sync_leads.py >> "$LOG_FILE" 2>&1
"$PYTHON" send_alerts.py >> "$LOG_FILE" 2>&1
"$PYTHON" check_spend_anomaly.py >> "$LOG_FILE" 2>&1
"$PYTHON" check_verification_expiry.py >> "$LOG_FILE" 2>&1
"$PYTHON" webhook_export.py >> "$LOG_FILE" 2>&1

echo "=== Sync run finished: $(date) ===" >> "$LOG_FILE"
