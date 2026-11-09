#!/usr/bin/env bash
systemctl --user list-units 'arcagi-*' --plain --no-legend | awk '{print $1}' | xargs -r systemctl --user stop
