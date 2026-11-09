#!/usr/bin/env bash
# Night watchdog: stops the newest arcagi-* user unit when resources are tight.
LOG=/home/lorkhan/repo/arcagi/notes/rounds/gpu-night-1109/watchdog.log
END=$(date -d 'TZ="Asia/Taipei" 2026-11-10 07:45' +%s)
MEM_MIN_KB=$((6*1024*1024))
[ "${WATCHDOG_TEST:-0}" = 1 ] && MEM_MIN_KB=$((999*1024*1024))
last_status=0

units() { systemctl --user list-units 'arcagi-*' --plain --no-legend 2>/dev/null | awk '{print $1}' | grep -v '^arcagi-watchdog'; }
log() { echo "$(date '+%F %T') $*" >> "$LOG"; }

while :; do
  now=$(date +%s)
  [ "$now" -ge "$END" ] && { log "mem=- swap=- gpu=- disk=- action=end-time-exit"; exit 0; }
  mem_kb=$(awk '/^MemAvailable:/{print $2}' /proc/meminfo)
  swap_kb=$(awk '/^SwapTotal:/{t=$2}/^SwapFree:/{f=$2}END{print t-f}' /proc/meminfo)
  IFS=',' read -r gt gm gu < <(nvidia-smi --query-gpu=temperature.gpu,memory.used,utilization.gpu --format=csv,noheader,nounits 2>/dev/null | head -1)
  gt=${gt// /}; gm=${gm// /}; gu=${gu// /}; gt=${gt:-0}; gm=${gm:-0}; gu=${gu:-0}
  disk=$(df --output=avail -BG / | tail -1 | tr -dc 0-9)
  mem_g=$((mem_kb/1024/1024)); swap_m=$((swap_kb/1024))
  line="mem=${mem_g}G swap=${swap_m}M gpu=${gt}C/${gm}MiB/${gu}% disk=${disk}G"

  if [ -e "$HOME/arcagi-STOP" ]; then
    for u in $(units); do systemctl --user stop "$u"; done
    log "$line action=STOP-switch stopped-all"
    exit 0
  fi

  reason=""
  [ "$mem_kb" -lt "$MEM_MIN_KB" ] && reason+="mem "
  [ "$swap_m" -gt 400 ] && reason+="swap "
  [ "$gt" -gt 85 ] && reason+="temp "
  [ "$gm" -gt 15000 ] && reason+="vram "
  [ "$disk" -lt 100 ] && reason+="disk "

  if [ -n "$reason" ]; then
    best=""; bestts=-1
    for u in $(units); do
      ts=$(systemctl --user show -p ActiveEnterTimestampMonotonic --value "$u" 2>/dev/null)
      ts=${ts:-0}
      if [ "$ts" -gt "$bestts" ]; then bestts=$ts; best=$u; fi
    done
    if [ -n "$best" ]; then
      systemctl --user stop "$best"
      log "$line action=TRIGGER(${reason% }) stopped=$best"
    else
      log "$line action=TRIGGER(${reason% }) nothing-to-stop"
    fi
    last_status=$now
  elif [ $((now-last_status)) -ge 600 ]; then
    log "$line action=ok"
    last_status=$now
  fi
  [ "${WATCHDOG_TEST:-0}" = 1 ] && exit 0
  sleep 60
done
