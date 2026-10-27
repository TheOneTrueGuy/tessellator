#!/usr/bin/env bash
# Launch the Tessellator UI with all model work offloaded to the RunPod pod.
set -a
source "$(dirname "$0")/runpod.env"
set +a
exec .venv/Scripts/python.exe app.py
