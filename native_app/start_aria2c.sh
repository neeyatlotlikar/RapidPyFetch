#!/bin/bash
aria2c \
  --enable-rpc \
  --rpc-listen-port=6800 \
  --rpc-secret="YOUR_SECRET" \
  --rpc-allow-origin-all=false \
  --rpc-listen-all=false \
  --dir="/path/to/downloads" \
  --continue=true
