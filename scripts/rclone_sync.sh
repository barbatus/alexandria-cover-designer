#!/bin/bash
set -euo pipefail

# Requires: rclone configured with Google Drive remote named "gdrive"
# Setup: rclone config -> New remote -> Google Drive -> follow prompts
rclone copy "Output Covers/" "gdrive:Alexandria Publishing/Output Covers/" \
  --include "*.jpg" --include "*.pdf" --include "*.ai" \
  --progress --transfers 4
