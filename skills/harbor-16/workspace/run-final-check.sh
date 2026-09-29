#!/usr/bin/env bash
# Restore delivery-check.py from backup and run the final gate check.
set -u
BK=$(ls -d /home/wff/harbor/task/_full_job_backups/block-storage-c-feature-20260813-1515/*-full-* | head -1)
cp "$BK/delivery-check.py" /tmp/delivery-check.py
python3 /tmp/delivery-check.py
