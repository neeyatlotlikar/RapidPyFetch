#!/bin/bash
aria2c \
  --enable-rpc \
  --log=/path/to/aria2c.log \
  --log-level=info \
  --rpc-listen-port=6800 \
  --rpc-secret="YOUR_SECRET" \
  --rpc-allow-origin-all=false \
  --rpc-listen-all=false \
  --dir="/path/to/downloads" \
  --max-tries=20 \
  --retry-wait=5 \
  --continue=true \
  -D
