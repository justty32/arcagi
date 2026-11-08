#!/bin/sh
cd "$(dirname "$0")/../.." || exit 1
export PYTHONDONTWRITEBYTECODE=1
exec .venv/bin/python native/hybrid.py "$@"
