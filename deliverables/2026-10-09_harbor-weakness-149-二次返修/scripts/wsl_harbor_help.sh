#!/usr/bin/env bash
export PATH="$PATH:/home/wff/.local/bin"
echo "=== harbor --help ==="
harbor --help 2>&1 | head -50
echo "=== harbor trial --help ==="
harbor trial --help 2>&1 | head -40
echo "=== harbor run --help (if exists) ==="
harbor run --help 2>&1 | head -40
