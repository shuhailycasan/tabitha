#!/usr/bin/env bash
# Tabitha — one-click setup & run (Linux / macOS)
# Downloads the model from GitHub Releases on first run, starts the bundled
# llama.cpp server, builds the client if needed, then runs the Flask app.
set -euo pipefail
cd "$(dirname "$0")"

# ---- config ---------------------------------------------------------------
REPO="shuhailycasan/tabitha"
RELEASE_TAG="Model"
MODEL_DIR="models"
MODEL_NAME="MiniCPM5-2B-Q4_K_M.gguf"
MODEL_FILE="$MODEL_DIR/$MODEL_NAME"
MODEL_SHA256="ec2d5801640099e97d8d7e8003ad4d81f336e757811f03a26173dddf386602fd"
MODEL_URL="https://github.com/$REPO/releases/download/$RELEASE_TAG/$MODEL_NAME"
LLAMA_PORT="${LLAMA_PORT:-2828}"
LLAMA_URL="http://127.0.0.1:$LLAMA_PORT"
APP_PORT="${PORT:-2424}"

say() { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
die() { printf '\033[1;31merror:\033[0m %s\n' "$*" >&2; exit 1; }
sha256() { sha256sum "$1" 2>/dev/null | cut -d' ' -f1 || shasum -a 256 "$1" | cut -d' ' -f1; }
need() { command -v "$1" >/dev/null || die "'$1' not found. $2"; }

# free a TCP port — kills whatever is listening; no-op if already free
kill_port() {
  local pids=""
  if command -v lsof >/dev/null; then
    pids=$(lsof -ti tcp:"$1" -sTCP:LISTEN 2>/dev/null || true)
  elif command -v fuser >/dev/null; then
    pids=$(fuser "$1"/tcp 2>/dev/null || true)
  fi
  if [ -n "$pids" ]; then
    say "Freeing :$1 (killing pid $pids)"
    kill $pids 2>/dev/null || true
    for _ in 1 2 3 4 5; do sleep 1; kill -0 $pids 2>/dev/null || return 0; done
    kill -9 $pids 2>/dev/null || true
  fi
}

# ---- pick bundled llama-server -------------------------------------------
LLAMA_BUILD="b11527"
case "$(uname -s)-$(uname -m)" in
  Linux-x86_64)  LLAMA_DIR="vendor/llama/linux-x64";  LLAMA_PKG="llama-${LLAMA_BUILD}-bin-ubuntu-x64.tar.gz" ;;
  Darwin-arm64)  LLAMA_DIR="vendor/llama/macos-arm64"; LLAMA_PKG="llama-${LLAMA_BUILD}-bin-macos-arm64.tar.gz" ;;
  Darwin-x86_64) LLAMA_DIR="vendor/llama/macos-x64";  LLAMA_PKG="llama-${LLAMA_BUILD}-bin-macos-x64.tar.gz" ;;
  *) die "unsupported platform $(uname -s)/$(uname -m) — install llama.cpp yourself and set LLM_BASE_URL" ;;
esac
LLAMA_BIN="$LLAMA_DIR/llama-server"
# vendored binary missing (vendor/ not committed)? fetch the official llama.cpp tarball
if [ ! -f "$LLAMA_BIN" ]; then
  say "No vendored llama-server — downloading llama.cpp $LLAMA_BUILD"
  mkdir -p "$LLAMA_DIR"
  curl -fL --progress-bar -o "/tmp/$LLAMA_PKG" \
    "https://github.com/ggml-org/llama.cpp/releases/download/$LLAMA_BUILD/$LLAMA_PKG" \
    || die "llama.cpp download failed"
  tar xzf "/tmp/$LLAMA_PKG" -C "$LLAMA_DIR" --strip-components=1 && rm "/tmp/$LLAMA_PKG"
fi
[ -x "$LLAMA_BIN" ] || chmod +x "$LLAMA_BIN"

need python3 "Install Python 3.10+"
need curl "Install curl"
need npm "Install Node.js 20+"

# ---- external LLM escape hatch -------------------------------------------
# Point at another server (e.g. the LAN box) to skip model download entirely:
#   LLM_BASE_URL=http://192.168.0.159:2828/v1 ./start.sh
RUN_LOCAL_LLM=1
if [ -n "${LLM_BASE_URL:-}" ] && [ "$LLM_BASE_URL" != "$LLAMA_URL/v1" ]; then
  RUN_LOCAL_LLM=0
  say "Using external LLM at $LLM_BASE_URL — skipping local model"
fi

# ---- model ----------------------------------------------------------------
if [ "$RUN_LOCAL_LLM" = 1 ]; then
  mkdir -p "$MODEL_DIR"
  if [ -f "$MODEL_FILE" ] && [ "$(sha256 "$MODEL_FILE")" = "$MODEL_SHA256" ]; then
    say "Model already downloaded ($MODEL_FILE)"
  else
    rm -f "$MODEL_FILE"
    say "Downloading $MODEL_NAME (~1.5 GB) from GitHub Releases…"
    curl -fL --progress-bar -C - -o "$MODEL_FILE.part" "$MODEL_URL" \
      || die "model download failed — is release '$RELEASE_TAG' published with $MODEL_NAME?"
    mv "$MODEL_FILE.part" "$MODEL_FILE"
    [ "$(sha256 "$MODEL_FILE")" = "$MODEL_SHA256" ] || die "model checksum mismatch — file corrupted, delete it and retry"
  fi
fi

# ---- python deps ----------------------------------------------------------
PY=.venv/bin/python
if [ ! -x "$PY" ]; then
  say "Creating virtualenv"
  python3 -m venv .venv
fi
if ! "$PY" -c "import flask, pandas, openpyxl, openai" 2>/dev/null; then
  say "Installing Python deps"
  if command -v uv >/dev/null; then
    uv pip install -q -p "$PY" -r requirements.txt
  elif ! "$PY" -m pip install -q -r requirements.txt 2>/dev/null; then
    "$PY" -m ensurepip -q && "$PY" -m pip install -q -r requirements.txt
  fi
fi

# ---- client ---------------------------------------------------------------
if [ ! -d client/node_modules ]; then
  say "Installing client deps"
  (cd client && npm ci --no-fund --no-audit)
fi
if [ ! -d client/dist ] || [ "${REBUILD_CLIENT:-0}" = 1 ]; then
  say "Building client"
  (cd client && npm run build)
fi

# ---- llama-server ---------------------------------------------------------
LLAMA_PID=""
cleanup() { [ -n "$LLAMA_PID" ] && kill "$LLAMA_PID" 2>/dev/null; }
trap cleanup EXIT INT TERM

if [ "$RUN_LOCAL_LLM" = 1 ]; then
  if curl -sf --max-time 2 "$LLAMA_URL/health" >/dev/null 2>&1; then
    say "llama-server already healthy on :$LLAMA_PORT — reusing it"
  else
    kill_port "$LLAMA_PORT"
    say "Starting llama-server on $LLAMA_URL (logs: llama-server.log)"
    # find bundled libs next to the binary on both linux (.so) and mac (.dylib)
    # -np splits ctx across slots: -np 1 gives each request the full 16384 (matches CTX_TOKENS in app.py)
    LD_LIBRARY_PATH="$LLAMA_DIR${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}" \
    DYLD_LIBRARY_PATH="$LLAMA_DIR${DYLD_LIBRARY_PATH:+:$DYLD_LIBRARY_PATH}" \
      "$LLAMA_BIN" -m "$MODEL_FILE" --alias "models/$MODEL_NAME" \
        --host 127.0.0.1 --port "$LLAMA_PORT" -c 16384 -np 1 \
        > llama-server.log 2>&1 &
    LLAMA_PID=$!
    say "Waiting for model to load…"
    for i in $(seq 1 120); do
      curl -sf --max-time 2 "$LLAMA_URL/health" >/dev/null 2>&1 && break
      kill -0 "$LLAMA_PID" 2>/dev/null || { tail -20 llama-server.log; die "llama-server exited"; }
      sleep 1
    done
    curl -sf "$LLAMA_URL/health" >/dev/null || die "llama-server did not become healthy in 120s — see llama-server.log"
  fi
fi

# ---- flask ----------------------------------------------------------------
kill_port "$APP_PORT"
say "Starting Tabitha → http://localhost:$APP_PORT"
export PORT="$APP_PORT"
export LLM_BASE_URL="${LLM_BASE_URL:-$LLAMA_URL/v1}"
"$PY" server/app.py  # not exec: the EXIT trap must live to kill llama-server
