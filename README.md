# MyOpenWebUI

A local LLM inference environment running Gemma 4 via Ollama, with Open WebUI as the chat interface, Traditional Chinese speech input/output, and a set of custom tools for research and coding assistance.

本機 LLM 推論環境，使用 Ollama 跑 Gemma 4 模型，透過 Open WebUI 提供網頁介面，支援繁體中文語音輸入輸出，並內建研究與程式輔助工具。

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Hardware Requirements](#hardware-requirements)
3. [Service Architecture](#service-architecture)
4. [Installation](#installation)
5. [Adding Models](#adding-models)
6. [Open WebUI Tools](#open-webui-tools)
7. [Adding New Tools](#adding-new-tools)
8. [Configuration Reference](#configuration-reference)
9. [LAN Access via nginx](#lan-access-via-nginx)
10. [Maintenance Commands](#maintenance-commands)
11. [Known Issues](#known-issues)

---

## Architecture Overview

```
User Browser
     │
     ▼
nginx :80  ──────────────────────────────────────────────
     │                                                   │
     │ proxy_pass                              static files
     ▼                                        /var/www/cili/html
Open WebUI :9090  (Docker, --network=host)
     │
     ├── Ollama :11434  (systemd)  ──► Gemma 4 12B / 26B
     ├── faster-whisper :8001  (Docker, STT)
     ├── edge-tts :8002  (Docker, TTS)
     └── Marker PDF Server :8003  (systemd, virtualenv)
```

- External access: `http://<YOUR-SERVER-IP>` → nginx → Open WebUI
- Local access: `http://localhost:9090`
- The university firewall only allows port 80; nginx acts as the reverse proxy.

---

## Hardware Requirements

| Component | This Machine | Recommended Minimum |
|-----------|-------------|---------------------|
| GPU | NVIDIA RTX 3080 (12 GB VRAM) | 8 GB VRAM |
| RAM | 32 GB | 16 GB |
| Storage | 931 GB NVMe SSD | 100 GB free |
| OS | Ubuntu 22.04 | Ubuntu 20.04+ |
| CUDA | 13.0 | 11.8+ |

**VRAM breakdown:**
- Gemma 4 12B QAT: ~7.2 GB
- Marker PDF Server: ~3.6 GB
- Total (both active): ~10.8 GB — fits within 12 GB

> Using Gemma 4 26B requires stopping `marker-server` first to free VRAM.

---

## Service Architecture

| Service | Docker Name | Port | Type | Description |
|---------|------------|------|------|-------------|
| Ollama | systemd | 11434 | systemd | LLM inference engine |
| Open WebUI | `open-webui` | 9090 | Docker (`--network=host`) | Web chat interface |
| faster-whisper | `faster-whisper` | 8001 | Docker | STT — Traditional Chinese |
| edge-tts | `edge-tts` | 8002 | Docker | TTS — zh-TW-HsiaoChenNeural |
| Marker PDF | `marker-server` | 8003 | systemd (virtualenv) | PDF to Markdown conversion |
| nginx | systemd | 80 | systemd | Reverse proxy for LAN access |

**Access URLs / 存取網址**
- Local: `http://localhost:9090`
- LAN: `http://<YOUR-SERVER-IP>` (via nginx)

---

## Models

| Model Tag | Size | Use Case |
|-----------|------|----------|
| `gemma4:12b-it-qat` | 7.2 GB | Daily use — full GPU, fast |
| `gemma4:26b-a4b-it-q4_K_M` | 17 GB | Deep reasoning — partial CPU offload, slower |

Models are stored in `~/.ollama/models/`.

> Using 26B requires stopping `marker-server` first: `sudo systemctl stop marker-server`

---

## Installation

### 1. Ollama

```bash
curl -fsSL https://ollama.com/install.sh | sh

# Allow network access (optional, for API access from other hosts)
sudo systemctl edit ollama --force
# Add under [Service]:
# Environment="OLLAMA_HOST=0.0.0.0"

sudo systemctl restart ollama

# Pull models
ollama pull gemma4:12b-it-qat
ollama pull gemma4:26b-a4b-it-q4_K_M
```

### 2. Open WebUI

```bash
docker run -d \
  --name open-webui \
  --network=host \
  --restart always \
  -e PORT=9090 \
  -e OLLAMA_BASE_URL=http://127.0.0.1:11434 \
  -v open-webui:/app/backend/data \
  ghcr.io/open-webui/open-webui:main
```

> **Note:** `--network=host` is required. Do NOT use `-p` port mapping, as this breaks localhost service discovery inside the container.

### 3. faster-whisper (STT)

```bash
docker run -d \
  --name faster-whisper \
  --restart always \
  -p 8001:8000 \
  -e ASR_MODEL=small \
  -e ASR_ENGINE=faster_whisper \
  fedirz/faster-whisper-server:latest-cpu
```

### 4. edge-tts (TTS)

```bash
docker run -d \
  --name edge-tts \
  --restart always \
  -p 8002:5050 \
  -e REQUIRE_API_KEY=False \
  travisvn/openai-edge-tts:latest
```

### 5. Marker PDF Server

Marker converts academic PDFs (text, tables, LaTeX formulas, images) to Markdown.

```bash
# Create virtualenv
python3 -m venv ~/Gemma/marker-env
source ~/Gemma/marker-env/bin/activate
pip install marker-pdf fastapi uvicorn python-multipart

# Server script is at ~/Gemma/scripts/marker_server.py
# Install as systemd service
sudo tee /etc/systemd/system/marker-server.service > /dev/null << 'EOF'
[Unit]
Description=Marker PDF Processing Server
After=network.target

[Service]
User=user
WorkingDirectory=/home/user/Gemma
ExecStart=/home/user/Gemma/marker-env/bin/python /home/user/Gemma/scripts/marker_server.py
Environment="TORCH_DEVICE=cuda"
Restart=on-failure

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable marker-server
sudo systemctl start marker-server

# Verify
curl http://localhost:8003/health
```

### 6. Audio Settings (STT + TTS)

Audio settings cannot be configured from the Open WebUI UI in v0.9.6. Write directly to the SQLite database:

```bash
docker exec open-webui python3 -c "
import sqlite3, json
conn = sqlite3.connect('/app/backend/data/webui.db')
cur = conn.cursor()
cur.execute('SELECT data FROM config WHERE id=1')
data = json.loads(cur.fetchone()[0])
data['audio'] = {
    'stt': {
        'engine': 'openai',
        'model': 'small',
        'openai': {
            'api_base_url': 'http://localhost:8001/v1',
            'api_key': 'sk-none',
            'language': 'zh'
        }
    },
    'tts': {
        'engine': 'openai',
        'model': 'tts-1',
        'voice': 'zh-TW-HsiaoChenNeural',
        'openai': {
            'api_base_url': 'http://localhost:8002/v1',
            'api_key': 'sk-none'
        }
    }
}
cur.execute('UPDATE config SET data=? WHERE id=1', (json.dumps(data),))
conn.commit()
conn.close()
print('Audio settings updated.')
"
docker restart open-webui
```

### 7. Verify Audio Settings

To read the current audio config from the database:

```bash
docker exec open-webui python3 -c "
import sqlite3, json
conn = sqlite3.connect('/app/backend/data/webui.db')
cur = conn.cursor()
cur.execute('SELECT data FROM config WHERE id=1')
data = json.loads(cur.fetchone()[0])
print(json.dumps(data.get('audio', {}), indent=2))
conn.close()
"
```

### 8. Date Auto-Injection (Cron)

The model's system prompt is updated daily with the current date so it does not answer from stale training data.

```bash
# Make script executable
chmod +x ~/Gemma/scripts/update_date_prompt.sh

# Add to cron (runs at midnight)
(crontab -l 2>/dev/null; echo "0 0 * * * /home/user/Gemma/scripts/update_date_prompt.sh") | crontab -

# Run once immediately to initialize
~/Gemma/scripts/update_date_prompt.sh
```

---

## Adding Models

### Step 1 — Pull the model from Ollama

```bash
ollama pull <model-tag>
# Example:
ollama pull llama3.2:3b
```

Browse available models at [ollama.com/library](https://ollama.com/library).

### Step 2 — Create a model entry in Open WebUI

In Open WebUI: **Workspace → Models → +**

Set a display name, select the base Ollama model, then save. Note the model ID shown (used in the next steps).

### Step 3 — Bind Tools to the new model

Replace `your-model-id` with the actual ID shown in Open WebUI:

```bash
docker exec open-webui python3 -c "
import sqlite3, json, time
conn = sqlite3.connect('/app/backend/data/webui.db')
cur = conn.cursor()
tools = ['system_info', 'web_search_duckduckgo', 'code_interpreter_python_r', 'pdf_reader_marker']
mid = 'your-model-id'
cur.execute('SELECT meta FROM model WHERE id=?', (mid,))
row = cur.fetchone()
meta = json.loads(row[0]) if row and row[0] else {}
meta['toolIds'] = tools
cur.execute('UPDATE model SET meta=?, updated_at=? WHERE id=?', (json.dumps(meta), int(time.time()), mid))
conn.commit()
conn.close()
print('Tools bound to', mid)
"
```

### Step 4 — Inject the current date into the system prompt

```bash
~/Gemma/scripts/update_date_prompt.sh
```

This script updates **all active models** in the database. Run it once after adding any new model.

> The cron job handles this automatically every midnight going forward.

---

## Open WebUI Tools

All tools are stored in [`tools/`](tools/) and installed into Open WebUI's SQLite database.

| Tool | File | Functions | Description |
|------|------|-----------|-------------|
| System Info | [`system_info.py`](tools/system_info.py) | `get_current_datetime` | Returns current date and time (Asia/Taipei) |
| Web Search | [`web_search.py`](tools/web_search.py) | `search_web` | DuckDuckGo search with time range filter |
| Code Interpreter | [`code_interpreter.py`](tools/code_interpreter.py) | `run_python`, `run_r` | Execute Python or R code inside the container |
| PDF Reader | [`pdf_reader.py`](tools/pdf_reader.py) | `read_pdf` | Convert PDF to Markdown via Marker server |

### Installing a Tool

1. Open **Workspace → Tools → +** in Open WebUI
2. Paste the full contents of the tool file
3. Save — the tool ID is derived from the `title:` field in the file header
4. Bind the tool to models (see [Step 3 in Adding Models](#step-3--bind-tools-to-the-new-model))

### Using PDF Reader

- **Upload via UI**: Click **[+]** in the chat input, upload the PDF, then say: `Read this PDF: filename.pdf`
- **Absolute path**: Say `Read this PDF: /absolute/path/file.pdf` (path must be accessible inside the container)

### Notes

- R (`r-base`) must be installed inside the container after every restart:
  ```bash
  docker exec open-webui apt-get install -y r-base
  ```
- Web search uses the `ddgs` package (renamed from `duckduckgo_search`). Install if missing:
  ```bash
  docker exec open-webui pip install ddgs
  ```

---

## Adding New Tools

### Tool File Structure

Every tool is a Python file with a metadata header and a `Tools` class:

```python
"""
title: My Tool Name          ← becomes the tool ID (spaces → underscores, lowercased)
author: local
version: 1.0.0
description: What this tool does.
"""

from typing import Optional


class Tools:
    def __init__(self):
        pass

    async def my_function(self, param: str) -> str:
        """
        One-line description of what this function does.
        Use this when the user asks about X or Y.
        :param param: description of the parameter
        :return: description of the return value
        """
        # implementation
        return result
```

**Key rules:**
- Class must be named exactly `Tools`
- All public methods become callable functions for the LLM
- Type annotations on parameters are required (`str`, `int`, `Optional[str]`, etc.)
- The docstring is sent to the LLM as the function description — write it clearly
- Prefix private helpers with `_` so they are not exposed as tools

### Installation Steps

**Option A — via UI:**
1. Open **Workspace → Tools → +**
2. Paste the full file content and save

**Option B — via database (for updates/fixes):**

```bash
# Copy the file into the container
docker cp tools/my_tool.py open-webui:/tmp/my_tool.py

# Update the database
docker exec open-webui python3 -c "
import sqlite3, json, time, inspect

with open('/tmp/my_tool.py') as f:
    code = f.read()

ns = {}
exec(compile(code, 'tool', 'exec'), ns)
t = ns['Tools']()

specs = []
for name, method in inspect.getmembers(t, predicate=inspect.ismethod):
    if name.startswith('_'):
        continue
    sig = inspect.signature(method)
    doc = inspect.getdoc(method) or ''
    desc = doc.split(':param')[0].strip()
    props = {}
    required = []
    for pname, param in sig.parameters.items():
        if pname in ('self', '__user__'):
            continue
        ann = param.annotation
        type_str = 'integer' if ann == int else 'string'
        props[pname] = {'type': type_str, 'description': pname}
        if param.default is inspect.Parameter.empty:
            required.append(pname)
    specs.append({
        'name': name,
        'description': desc,
        'parameters': {'type': 'object', 'properties': props, 'required': required}
    })

tool_id = 'my_tool_id'  # must match the existing ID in the database
conn = sqlite3.connect('/app/backend/data/webui.db')
cur = conn.cursor()
cur.execute('UPDATE tool SET specs=?, content=?, updated_at=? WHERE id=?',
            (json.dumps(specs), code, int(time.time()), tool_id))
conn.commit()
conn.close()
print('Updated:', [s['name'] for s in specs])
"
```

> **Important:** The `specs` column in the database is the JSON schema sent to the LLM for function calling. If `specs` is wrong or stale, the LLM will fail to call the tool correctly (symptom: `'Tools' object has no attribute 'calculator'` error). Always regenerate `specs` using `inspect` when updating a tool.

### After Adding a Tool

Bind it to all models:

```bash
docker exec open-webui python3 -c "
import sqlite3, json, time
conn = sqlite3.connect('/app/backend/data/webui.db')
cur = conn.cursor()
new_tool_id = 'your_new_tool_id'
cur.execute('SELECT id, meta FROM model WHERE is_active=1')
for mid, meta_json in cur.fetchall():
    meta = json.loads(meta_json) if meta_json else {}
    tools = meta.get('toolIds', [])
    if new_tool_id not in tools:
        tools.append(new_tool_id)
        meta['toolIds'] = tools
        cur.execute('UPDATE model SET meta=?, updated_at=? WHERE id=?',
                    (json.dumps(meta), int(time.time()), mid))
conn.commit()
conn.close()
print('Done')
"
```

---

## Configuration Reference

### nginx (`/etc/nginx/sites-available/cili`)

```nginx
# Open WebUI — accessible via IP from LAN
server {
    listen 80;
    listen [::]:80;
    server_name <YOUR-SERVER-IP>;

    client_max_body_size 100M;

    location / {
        proxy_pass http://127.0.0.1:9090;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_http_version 1.1;
        proxy_read_timeout 600s;
    }
}

# Portal website — accessible via hostname from internal network
server {
    listen 80;
    listen [::]:80;
    server_name cili;

    root /var/www/cili/html;
    index index.html index.htm;

    location / {
        try_files $uri $uri/ =404;
    }
}
```

After editing:
```bash
sudo nginx -t && sudo systemctl reload nginx
```

### Open WebUI Database Location

```
/var/lib/docker/volumes/open-webui/_data/webui.db   # host path
/app/backend/data/webui.db                           # inside container
```

Access via:
```bash
docker exec open-webui sqlite3 /app/backend/data/webui.db
```

---

## LAN Access via nginx

The university network firewall blocks non-standard ports (8080, 9090, etc.). Only port 80 is accessible from the LAN.

**How it works:**
- Open WebUI runs on `localhost:9090` (not exposed directly)
- nginx listens on port 80 and proxies to 9090 based on `server_name`
- Requests to `http://<YOUR-SERVER-IP>` → Open WebUI
- Requests to `http://cili` (internal hostname) → original portal

**VS Code SSH Remote users:** VS Code automatically tunnels port 9090 through SSH, so `localhost:9090` works on your local machine without any additional setup.

---

## Boot Behavior

| Service | Type | Auto-start |
|---------|------|-----------|
| Ollama | systemd | ✓ (`enabled`) |
| Open WebUI | Docker `--restart always` | ✓ |
| faster-whisper | Docker `--restart always` | ✓ |
| edge-tts | Docker `--restart always` | ✓ |
| marker-server | systemd | ✓ (`enabled`) |
| nginx | systemd | ✓ (`enabled`) |

> After every container restart, R must be reinstalled: `docker exec open-webui apt-get install -y r-base`

---

## Ollama API Usage

```python
from ollama import chat

response = chat(
    model="gemma4:12b-it-qat",
    messages=[{"role": "user", "content": "你好"}]
)
print(response.message.content)
```

```bash
# REST API
curl http://localhost:11434/api/chat -d '{
  "model": "gemma4:12b-it-qat",
  "messages": [{"role": "user", "content": "你好"}]
}'
```

---

## Maintenance Commands

```bash
# --- Service Status ---
systemctl status ollama
systemctl status marker-server
docker ps

# --- Restart Services ---
sudo systemctl restart ollama
sudo systemctl restart marker-server
docker restart open-webui

# --- VRAM Usage ---
nvidia-smi

# --- Logs ---
docker logs open-webui --tail 50
docker logs faster-whisper --tail 50
docker logs edge-tts --tail 50
journalctl -u marker-server --no-pager -n 30

# --- Ollama ---
ollama list
ollama pull <model-tag>

# --- Reinstall R inside container (required after every container restart) ---
docker exec open-webui apt-get install -y r-base

# --- Update date in all model system prompts ---
~/Gemma/scripts/update_date_prompt.sh

# --- nginx ---
sudo nginx -t
sudo systemctl reload nginx
```

---

## Known Issues

| Issue | Solution |
|-------|----------|
| `'Tools' object has no attribute 'calculator'` | The `specs` column in the database is stale. Regenerate using the `inspect`-based script (see [Adding New Tools](#adding-new-tools)) |
| faster-whisper model name must be `small`, not `Systran/faster-whisper-small` | Use the short name in the Docker `-e ASR_MODEL=small` env var |
| STT model key in database is `audio.stt.model`, not `audio.stt.openai.model` | Use the correct key path when writing to the config table |
| `No Tools class found in the module` | Tool content in database is corrupted. Re-upload via `docker cp` + database update |
| Open WebUI returns 500 error | `docker restart open-webui` |
| R not found after container restart | `docker exec open-webui apt-get install -y r-base` |
| PDF Reader: file not found | Upload via the **[+]** button in the chat UI, or verify the path is accessible inside the container |
| Date is wrong (shows training cutoff year) | Run `~/Gemma/scripts/update_date_prompt.sh` to reinject today's date |
| Marker + Gemma 4 26B VRAM conflict | Stop marker before loading 26B: `sudo systemctl stop marker-server` |
| `breezyvoice-server` occupying 3+ GB VRAM | Kill it: `sudo kill -9 $(lsof -t -i:7860)` |
| Open WebUI audio settings not visible in UI | Edit SQLite directly (see [Installation → Audio Settings](#6-audio-settings-stt--tts)) |
| `host.docker.internal` not resolving in container | Use `127.0.0.1` instead (container uses `--network=host`) |
| Port 9090 not accessible from LAN | By design — university firewall blocks it. Use `http://<YOUR-SERVER-IP>` via nginx |

---

## Project Structure

```
~/Gemma/
├── tools/
│   ├── system_info.py          # System Info tool
│   ├── web_search.py           # Web Search tool (DuckDuckGo)
│   ├── code_interpreter.py     # Code Interpreter (Python + R)
│   └── pdf_reader.py           # PDF Reader (via Marker)
├── scripts/
│   ├── marker_server.py        # FastAPI server wrapping marker-pdf
│   └── update_date_prompt.sh  # Injects today's date into all model system prompts
├── marker-env/                 # Python virtualenv for Marker
└── CLAUDE.md                   # Claude Code project instructions
```
