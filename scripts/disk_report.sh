#!/bin/bash

# SIMBA disk-space report
# Checks the server's disks every day and emails a full report only when a disk is at or over
# WARN_PERCENT. The forecasts (updates, next deploy, growth, backup age) are part of the report
# but never send an email on their own.
# Runs as root from cron (needs root for du on /var, docker, apt and snap):
#   30 7 * * * /usr/local/Users/mperezsa/simba/scripts/disk_report.sh 2>>/local/simba/disk-report/errors.log
# Test without sending anything:
#   sudo ./scripts/disk_report.sh --print

export LC_ALL=C
export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

MAIL_TO="${MAIL_TO:-}"
MAIL_CC="${MAIL_CC:-}"                   # comma-separated, e.g. "a@server.com,b@server.com"
WARN_PERCENT="${WARN_PERCENT:-80}"
CRITICAL_PERCENT="${CRITICAL_PERCENT:-90}"
DISKS="${DISKS:-/ /var /local}"
STATE_DIR="${STATE_DIR:-/local/simba/disk-report}"
BACKUP_DIR="${BACKUP_DIR:-/local/simba/backups}"
DEPLOY_MB="${DEPLOY_MB:-2500}"           # deploy.sh builds new images on /var: about 2 GB on Oct 1, 2026
SOON_DAYS=14                             # growth trend: warn if a disk reaches CRITICAL_PERCENT within this many days

PRINT_ONLY=0
[ "$1" = "--print" ] && PRINT_ONLY=1

HOST=$(hostname)
TODAY=$(date +%F)
mkdir -p "$STATE_DIR"
HISTORY="$STATE_DIR/history.txt"         # one line per disk per day: date mount used_kb size_kb

LEVEL=0                                  # 0 = OK, 1 = WARNING, 2 = CRITICAL
OVER_THRESHOLD=0                         # 1 = a disk is at or over WARN_PERCENT: the only case that sends an email
REASONS=""

raise() {   # raise LEVEL REASON
    [ "$1" -gt "$LEVEL" ] && LEVEL=$1
    REASONS="${REASONS}  - $2"$'\n'
}

has() {
    command -v "$1" > /dev/null 2>&1
}

# Converts sizes like "56.7 MB", "1,234 kB", "77MB" or "2 GB" to whole MB
to_mb() {
    echo "$1" | tr -d ',' | awk '{
        s = $0; n = s + 0; sub(/^[0-9.]+ */, "", s)
        if (s ~ /^G/) n *= 1024; else if (s ~ /^[kK]/) n /= 1024; else if (s ~ /^B/) n /= 1048576
        printf "%d", n + 0.5 }'
}

section() {
    printf '\n%s\n%s\n' "$1" "$(echo "$1" | sed 's/./-/g')"
}

# --- Disk usage now, and history for the growth trend -----------------------------------------

DISK_TABLE=""
for MOUNT in $DISKS; do
    read -r SIZE_KB USED_KB AVAIL_KB < <(df -P -k "$MOUNT" 2>/dev/null | awk 'NR == 2 {print $2, $3, $4}')
    [ -z "$SIZE_KB" ] && continue
    PCT=$(( (USED_KB * 100 + SIZE_KB - 1) / SIZE_KB ))
    eval "SIZE_$(echo "$MOUNT" | tr -c 'a-z\n' '_')=$SIZE_KB USED_$(echo "$MOUNT" | tr -c 'a-z\n' '_')=$USED_KB"
    DISK_TABLE="${DISK_TABLE}$(printf '  %-8s %3d%% used   %6.1f GB free of %5.1f GB' "$MOUNT" "$PCT" \
        "$(echo "$AVAIL_KB" | awk '{print $1 / 1048576}')" "$(echo "$SIZE_KB" | awk '{print $1 / 1048576}')")"$'\n'
    [ "$PCT" -ge "$WARN_PERCENT" ] && OVER_THRESHOLD=1
    if [ "$PCT" -ge "$CRITICAL_PERCENT" ]; then
        raise 2 "$MOUNT is ${PCT}% full (critical from ${CRITICAL_PERCENT}%)"
    elif [ "$PCT" -ge "$WARN_PERCENT" ]; then
        raise 1 "$MOUNT is ${PCT}% full (warning from ${WARN_PERCENT}%)"
    fi
    # Keep one entry per disk per day (the first run of the day)
    grep -q "^$TODAY $MOUNT " "$HISTORY" 2>/dev/null || echo "$TODAY $MOUNT $USED_KB $SIZE_KB" >> "$HISTORY"
done

# Growth over the last 7 days (or since the oldest entry if there is less history)
TREND=""
WEEK_AGO=$(date -d '7 days ago' +%F)
for MOUNT in $DISKS; do
    KEY=$(echo "$MOUNT" | tr -c 'a-z\n' '_')
    eval "SIZE_KB=\${SIZE_$KEY:-} USED_KB=\${USED_$KEY:-}"
    [ -z "$SIZE_KB" ] && continue
    OLDEST=$(awk -v m="$MOUNT" -v since="$WEEK_AGO" '$2 == m && $1 >= since' "$HISTORY" | sort | head -n 1)
    OLD_DATE=$(echo "$OLDEST" | awk '{print $1}')
    OLD_USED=$(echo "$OLDEST" | awk '{print $3}')
    DAYS=$(( ( $(date -d "$TODAY" +%s) - $(date -d "${OLD_DATE:-$TODAY}" +%s) ) / 86400 ))
    if [ "$DAYS" -lt 1 ]; then
        TREND="${TREND}  $MOUNT: not enough history yet (needs at least one earlier day)"$'\n'
        continue
    fi
    MB_PER_DAY=$(( (USED_KB - OLD_USED) / 1024 / DAYS ))
    LINE="$(printf '  %-8s %+d MB per day (over %d days)' "$MOUNT" "$MB_PER_DAY" "$DAYS")"
    if [ "$MB_PER_DAY" -gt 0 ]; then
        LIMIT_KB=$(( SIZE_KB * CRITICAL_PERCENT / 100 ))
        DAYS_LEFT=$(( (LIMIT_KB - USED_KB) / 1024 / MB_PER_DAY ))
        if [ "$DAYS_LEFT" -le 0 ]; then
            LINE="$LINE, already over ${CRITICAL_PERCENT}%"
        else
            LINE="$LINE, reaches ${CRITICAL_PERCENT}% in about $DAYS_LEFT days ($(date -d "+$DAYS_LEFT days" +%F))"
            [ "$DAYS_LEFT" -lt "$SOON_DAYS" ] && raise 1 "$MOUNT reaches ${CRITICAL_PERCENT}% in about $DAYS_LEFT days at the current growth"
        fi
    fi
    TREND="${TREND}${LINE}"$'\n'
done

# --- What is coming up: backups, software updates, snap, the next deploy ------------------------

UPCOMING=""
add_upcoming() {
    UPCOMING="${UPCOMING}$1"$'\n'
}

# Database backups (on /local)
BACKUP_CRON=$(crontab -l 2>/dev/null | grep -v '^#' | grep 'backup.sh' | head -n 1)
if [ -n "$BACKUP_CRON" ]; then
    BACKUP_WHEN=$(echo "$BACKUP_CRON" | awk '{printf "%02d:%02d", $2, $1}')
    BACKUP_WHEN="daily at $BACKUP_WHEN (root crontab)"
else
    BACKUP_WHEN="NOT SCHEDULED (no backup.sh in root's crontab)"
    raise 1 "the nightly database backup is not scheduled"
fi
LATEST_BACKUP=$(ls -t "$BACKUP_DIR"/simba_backup_*.sql.gz 2>/dev/null | head -n 1)
if [ -n "$LATEST_BACKUP" ]; then
    BACKUP_COUNT=$(ls "$BACKUP_DIR"/simba_backup_*.sql.gz | wc -l)
    add_upcoming "  Database backup:   $BACKUP_WHEN, next one about $(du -h "$LATEST_BACKUP" | cut -f1) on /local"
    add_upcoming "                     ($BACKUP_COUNT kept, $(du -sh "$BACKUP_DIR" | cut -f1) in total; the oldest is deleted after 30)"
    if [ "$(find "$LATEST_BACKUP" -mmin +1560 2>/dev/null)" ]; then
        raise 1 "the newest database backup is more than a day old ($(basename "$LATEST_BACKUP"))"
    fi
else
    add_upcoming "  Database backup:   $BACKUP_WHEN, no backup found in $BACKUP_DIR"
fi

# apt software updates (installed automatically by unattended-upgrades)
APT_DOWNLOAD_MB=0
if has apt-get; then
    APT_NEXT=$(systemctl list-timers apt-daily-upgrade.timer --no-legend 2>/dev/null | awk '{print $1, $2, $3, $4}')
    APT_SIM=$(apt-get -o Debug::NoLocking=1 --assume-no dist-upgrade 2>/dev/null)
    APT_COUNT=$(echo "$APT_SIM" | grep -E '^[0-9]+ upgraded' | awk '{print $1 + $3}')
    APT_GET=$(echo "$APT_SIM" | grep '^Need to get' | sed -e 's/^Need to get //' -e 's/ of archives.*//' -e 's#/.*##')
    [ -n "$APT_GET" ] && APT_DOWNLOAD_MB=$(to_mb "$APT_GET")
    APT_CACHE=$(du -sh /var/cache/apt/archives 2>/dev/null | cut -f1)
    add_upcoming "  Software updates:  next automatic run ${APT_NEXT:-unknown}"
    add_upcoming "                     ${APT_COUNT:-0} packages pending, about $APT_DOWNLOAD_MB MB to download into /var/cache/apt"
    add_upcoming "                     (downloaded packages are kept, cache is now ${APT_CACHE:-unknown}; 'sudo apt-get clean' empties it)"
fi

# snap refreshes (on /var/lib/snapd; snap downloads the new version before removing the old one)
SNAP_MB=0
if has snap; then
    SNAP_NEXT=$(snap refresh --time 2>/dev/null | grep '^next:' | sed 's/^next: *//')
    SNAP_LIST=$(snap refresh --list 2>/dev/null | tail -n +2)
    if [ -n "$SNAP_LIST" ]; then
        SNAP_MB=$(echo "$SNAP_LIST" | awk '{for (i = 1; i <= NF; i++) if ($i ~ /^[0-9.]+[kMG]B$/) print $i}' \
            | while read -r S; do to_mb "$S"; echo; done | awk '{t += $1} END {printf "%d", t}')
        SNAP_NAMES=$(echo "$SNAP_LIST" | awk '{print $1}' | paste -sd ' ')
        add_upcoming "  Snap refresh:      next ${SNAP_NEXT:-unknown}, about $SNAP_MB MB pending ($SNAP_NAMES)"
    else
        add_upcoming "  Snap refresh:      next ${SNAP_NEXT:-unknown}, nothing pending"
    fi
fi

add_upcoming "  Next SIMBA deploy: about $DEPLOY_MB MB on /var for the new images (old ones stay until removed)"

# Can /var take what is coming?
eval "VAR_SIZE=\${SIZE__var:-} VAR_USED=\${USED__var:-}"
ESTIMATE=""
if [ -n "$VAR_SIZE" ]; then
    VAR_FREE_MB=$(( (VAR_SIZE - VAR_USED) / 1024 ))
    UPDATES_MB=$(( APT_DOWNLOAD_MB + SNAP_MB ))
    AFTER_UPDATES_PCT=$(( ((VAR_USED / 1024 + UPDATES_MB) * 100 + VAR_SIZE / 1024 - 1) / (VAR_SIZE / 1024) ))
    AFTER_DEPLOY_PCT=$(( ((VAR_USED / 1024 + UPDATES_MB + DEPLOY_MB) * 100 + VAR_SIZE / 1024 - 1) / (VAR_SIZE / 1024) ))
    ESTIMATE="  /var has $VAR_FREE_MB MB free.
  After the pending updates ($UPDATES_MB MB):             about ${AFTER_UPDATES_PCT}% used
  After the updates and the next deploy (+$DEPLOY_MB MB): about ${AFTER_DEPLOY_PCT}% used"
    if [ "$AFTER_UPDATES_PCT" -ge 100 ]; then
        raise 2 "the pending software updates do not fit on /var: the database and site can go down when they install"
    elif [ "$AFTER_UPDATES_PCT" -ge "$CRITICAL_PERCENT" ]; then
        raise 1 "the pending software updates would take /var to about ${AFTER_UPDATES_PCT}%"
    fi
    if [ "$AFTER_DEPLOY_PCT" -ge 100 ]; then
        raise 1 "not enough room on /var for the next deploy (about ${AFTER_DEPLOY_PCT}% needed): free space first"
    fi
fi

# --- Decide whether to send ------------------------------------------------------------------------

STATUS=("OK" "WARNING" "CRITICAL")
if [ "$OVER_THRESHOLD" -eq 0 ] && [ "$PRINT_ONLY" -eq 0 ]; then
    exit 0
fi

WORST=$(for MOUNT in $DISKS; do df -P "$MOUNT" 2>/dev/null | awk -v m="$MOUNT" 'NR == 2 {print $5 + 0, m}'; done | sort -rn | head -n 1)
if [ "$LEVEL" -gt 0 ]; then
    SUBJECT="[SIMBA disk] ${STATUS[$LEVEL]}: $(echo "$WORST" | awk '{print $2, $1 "%"}') used on $HOST"
else
    SUBJECT="[SIMBA disk] All disks OK on $HOST"
fi

# --- The report ------------------------------------------------------------------------------------

REPORT_FILE="$STATE_DIR/last-report.txt"
{
    echo "SIMBA disk report for $HOST, $(date '+%Y-%m-%d %H:%M %Z')"
    echo "Status: ${STATUS[$LEVEL]}"
    if [ -n "$REASONS" ]; then
        echo
        echo "Why:"
        printf '%s' "$REASONS"
    fi

    section "Disks"
    printf '%s' "$DISK_TABLE"

    section "Coming up"
    printf '%s' "$UPCOMING"
    [ -n "$ESTIMATE" ] && printf '\n%s\n' "$ESTIMATE"

    section "Growth"
    printf '%s' "$TREND"

    section "Biggest folders on /var"
    du -xh --max-depth=2 /var 2>/dev/null | sort -rh | head -n 15 | sed "s/^/  /"

    section "Docker"
    if has docker; then
        docker system df 2>/dev/null
        echo
        echo "Container logs:"
        docker ps -aq 2>/dev/null | while read -r ID; do
            NAME=$(docker inspect --format '{{.Name}}' "$ID" | sed 's#^/##')
            LOG=$(docker inspect --format '{{.LogPath}}' "$ID")
            printf '  %-30s %s\n' "$NAME" "$( [ -f "$LOG" ] && du -h "$LOG" | cut -f1 || echo '-')"
        done
    else
        echo "  docker not available"
    fi

    section "System logs"
    if has journalctl; then
        echo "  $(journalctl --disk-usage 2>/dev/null)"
    fi
    du -xh --max-depth=1 /var/log 2>/dev/null | sort -rh | head -n 6 | sed 's/^/  /'

    section "SIMBA data on /local"
    du -sh /local/simba/* 2>/dev/null | sort -rh | sed 's/^/  /'

    section "Biggest folders on /"
    du -xh --max-depth=1 / 2>/dev/null | sort -rh | head -n 8 | sed 's/^/  /'

    echo
    echo "Sent by scripts/disk_report.sh (root crontab). Warning from ${WARN_PERCENT}%, critical from ${CRITICAL_PERCENT}%."
} > "$REPORT_FILE"

if [ "$PRINT_ONLY" -eq 1 ]; then
    echo "Subject: $SUBJECT"
    echo "To: $MAIL_TO${MAIL_CC:+, Cc: $MAIL_CC}"
    echo
    cat "$REPORT_FILE"
    exit 0
fi

# --- Send ------------------------------------------------------------------------------------------

if has sendmail; then
    {
        echo "To: $MAIL_TO"
        [ -n "$MAIL_CC" ] && echo "Cc: $MAIL_CC"
        echo "Subject: $SUBJECT"
        echo "Content-Type: text/plain; charset=UTF-8"
        echo
        cat "$REPORT_FILE"
    } | sendmail -t
elif has mail; then
    mail -s "$SUBJECT" ${MAIL_CC:+-c "$MAIL_CC"} "$MAIL_TO" < "$REPORT_FILE"
else
    echo "$(date '+%F %T') disk_report.sh: no sendmail or mail command, report saved in $REPORT_FILE" >&2
    exit 1
fi
