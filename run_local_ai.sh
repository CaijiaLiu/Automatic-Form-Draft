#!/usr/bin/env zsh
# Only loopback is exposed. No patient files are uploaded to a hosted service.
set -e
cd "${0:A:h}"
model_path="$PWD/work/models/Qwen3-1.7B-local-Q4_K_M.gguf"
if [[ ! -f "$model_path" ]]; then
  print 'Local model weights are missing. See README.md for the pinned download source.'
  exit 1
fi
mkdir -p work/semantic
# CPU defaults also work in restricted environments without Metal access.
server_path="$(command -v llama-server)"
exec "$server_path" -m "$model_path" \
  --alias itp-local-qwen3-1.7b-q4 --host 127.0.0.1 --port 8081 \
  -c 8192 -np 1 --device none --fit off -ngl 0 -t 4 -tb 4 \
  --cache-type-k q8_0 --cache-type-v q8_0 \
  -b 256 -ub 128 --no-warmup -fa on \
  --reasoning off --no-webui --log-file work/semantic/model_server.log
