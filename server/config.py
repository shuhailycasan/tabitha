import os
from pathlib import Path

LLM_BASE_URL = os.environ.get("LLM_BASE_URL", "http://127.0.0.1:2828/v1")  # start.sh runs llama-server locally; override for a LAN/remote server
LLM_MODEL = os.environ.get("LLM_MODEL", "models/MiniCPM5-2B-Q4_K_M.gguf")

SERVER_DIR = Path(__file__).parent
UPLOAD_DIR = SERVER_DIR / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)
CLIENT_DIR = SERVER_DIR.parent / "client" / "dist"  # vite build output

MAX_TOOL_RESULT_CHARS = 4000  # keep results small; the model has 16384 tokens per slot
CTX_TOKENS = int(os.environ.get("CTX_TOKENS", "16384"))  # must match llama-server's per-slot ctx (-c / -np)
MAX_TOKENS = 4096  # reasoning model: ~2500 tokens of thinking before a tool call; 1024 truncated to nothing
AUTO_COMPACT = 0.60  # drop oldest history once the prompt would exceed 60% of the window
THINK_BUDGET = int(os.environ.get("THINK_BUDGET", "500"))  # llama.cpp reasoning_budget — ~500 tok ≈ ~1500 chars of thinking
THINK_MAX_CHARS = int(os.environ.get("THINK_MAX_CHARS", "1500"))  # hard cap on the thinking text shown in the UI

HOST = os.environ.get("HOST", "0.0.0.0")
PORT = int(os.environ.get("PORT", "2424"))  # 5000 reserved, 8000 in use
