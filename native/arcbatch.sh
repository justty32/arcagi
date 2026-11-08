#!/bin/sh
# Batch evaluation entry: arcsearch --batch (see reports/native-s1c/README.md).
exec "$(dirname "$0")/arcsearch" --batch "$@"
