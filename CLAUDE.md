# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 專案概述

本機 LLM 推論環境，使用 Ollama 跑 Gemma 4 模型，透過 Open WebUI 提供網頁介面，支援繁體中文語音輸入輸出。

## 硬體規格

- **GPU**: NVIDIA RTX 3080（12 GB VRAM）
- **RAM**: 32 GB
- **儲存**: 931 GB NVMe SSD（模型與專案存放位置）
- **OS**: Ubuntu / CUDA 13.0

## 服務架構

| 服務 | Docker 名稱 | Port | 說明 |
|------|------------|------|------|
| Ollama | systemd | 11434 | 模型推論引擎 |
| Open WebUI | `open-webui` | 9090 | 網頁對話介面（`--network=host`）|
| faster-whisper | `faster-whisper` | 8001 | STT 語音辨識（CPU，繁體中文）|
| edge-tts | `edge-tts` | 8002 | TTS 語音合成（zh-TW-HsiaoChenNeural）|
| nginx | systemd | 80 | 反向代理（區網存取 Open WebUI）|

**存取網址**
- 本機：`http://localhost:9090`
- 區網：`http://<YOUR-SERVER-IP>`（nginx → 9090）

**nginx 設定**（`/etc/nginx/sites-available/cili`）
- `server_name <YOUR-SERVER-IP>` → proxy_pass `http://127.0.0.1:9090`（Open WebUI）
- `server_name cili` → `/var/www/cili/html`（原有 portal，內網 hostname 存取）

## 模型

| 模型 tag | 大小 | 用途 |
|---------|------|------|
| `gemma4:12b-it-qat` | 7.2 GB | 日常使用（全 GPU，速度快）|
| `gemma4:26b-a4b-it-q4_K_M` | 17 GB | 深度推理（部分 CPU offload，速度較慢）|

模型儲存於 `~/.ollama/models/`。

## 常用指令

```bash
# 查看模型清單
ollama list

# 下載新模型
ollama pull <model-tag>

# 查看服務狀態
systemctl status ollama
systemctl status marker-server
docker ps

# 重啟服務
sudo systemctl restart ollama
sudo systemctl restart marker-server
docker restart open-webui

# 查看 VRAM 使用
nvidia-smi

# 查看各服務 log
docker logs open-webui
docker logs faster-whisper
docker logs edge-tts
journalctl -u marker-server --no-pager -n 30
```

## Open WebUI Tools

已安裝並綁定至所有模型的 Tools（儲存於`~/Gemma/tools/`）：

| Tool | 檔案 | 功能 |
|------|------|------|
| System Info | `system_info.py` | 取得系統當前時間（Asia/Taipei）|
| Web Search | `web_search_duckduckgo.py` | DuckDuckGo 網頁搜尋 |
| Code Interpreter | `code_interpreter.py` | 執行 Python / R 程式碼 |
| PDF Reader | `pdf_reader.py` | 讀取 PDF，支援文字、表格、公式（透過 Marker）|

### PDF Reader 使用方式
- **上傳檔案**：對話框 [+] 上傳 PDF，然後說「幫我讀這份 PDF：檔名.pdf」
- **指定路徑**：說「幫我讀這份 PDF：/絕對路徑/檔案.pdf」（需路徑在 container 內可存取）

### 新增 Tool 的方式
1. **Workspace → Tools → +** 貼上程式碼
2. 直接修改資料庫：`docker exec open-webui sqlite3 /app/backend/data/webui.db`
3. 新增後執行以下指令綁定至所有模型：

```bash
docker exec open-webui python3 -c "
import sqlite3, json, time
conn = sqlite3.connect('/app/backend/data/webui.db')
cur = conn.cursor()
tools = ['system_info', 'web_search_duckduckgo', 'code_interpreter_python_r', 'pdf_reader_marker']
for mid in ('gemma4-12bqat', 'gemma4:12b-it-qat'):
    cur.execute('SELECT meta FROM model WHERE id=?', (mid,))
    row = cur.fetchone()
    meta = json.loads(row[0]) if row[0] else {}
    meta['toolIds'] = tools
    cur.execute('UPDATE model SET meta=?, updated_at=? WHERE id=?', (json.dumps(meta), int(time.time()), mid))
conn.commit()
conn.close()
"
```

### 注意事項
- container 重啟後 R（`r-base`）會消失，需重新安裝：`docker exec open-webui apt-get install -y r-base`
- 每次新增模型後執行 `~/Gemma/scripts/update_date_prompt.sh` 注入當天日期

### 日期自動注入
- cron 每天午夜更新所有模型的 system prompt 為當天日期
- 腳本：`~/Gemma/scripts/update_date_prompt.sh`
- Open WebUI Filter（`datetime_injector`）目前無法自動觸發，改用 cron 方案

## Marker PDF 服務

| 項目 | 說明 |
|------|------|
| 服務名稱 | `marker-server`（systemd）|
| Port | 8003 |
| 虛擬環境 | `~/Gemma/marker-env/` |
| 伺服器腳本 | `~/Gemma/scripts/marker_server.py` |
| 支援格式 | 數位 PDF（文字、表格、LaTeX 公式、圖片）|
| 不支援 | 掃描版 PDF（OCR）|

```bash
# 狀態查看
sudo systemctl status marker-server

# 重啟
sudo systemctl restart marker-server

# 健康檢查
curl http://localhost:8003/health

# 測試轉換
curl -X POST http://localhost:8003/convert -F "file=@/path/to/file.pdf"
```

**VRAM 狀況**：Marker 常駐佔用約 3.6 GB，Gemma 4 12B（7.2 GB）合計 10.8 GB，在 12 GB 範圍內可同時運行。使用 26B 模型前建議停止 marker-server。

## 重開機行為

- Ollama：systemd 服務，自動啟動
- Open WebUI / faster-whisper / edge-tts：Docker `--restart always`，自動啟動
- marker-server：systemd 服務，自動啟動

## 音訊設定說明

Open WebUI v0.9.6 的音訊設定 UI 只顯示「預設」和「瀏覽器」，**沒有 OpenAI 選項**。實際設定需直接修改 SQLite 資料庫：

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

資料庫音訊設定結構：
```json
{
  "stt": {
    "engine": "openai",
    "model": "small",
    "openai": {
      "api_base_url": "http://localhost:8001/v1",
      "api_key": "sk-none",
      "language": "zh"
    }
  },
  "tts": {
    "engine": "openai",
    "model": "tts-1",
    "voice": "zh-TW-HsiaoChenNeural",
    "openai": {
      "api_base_url": "http://localhost:8002/v1",
      "api_key": "sk-none"
    }
  }
}
```

**重要**：修改資料庫後須重啟 Open WebUI：`docker restart open-webui`

## Ollama API 使用範例

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

## 已知問題與解法

| 問題 | 解法 |
|------|------|
| faster-whisper 模型名稱須用 `small` 不能用 `Systran/faster-whisper-small` | 已修正 |
| STT model key 在資料庫是 `audio.stt.model`（非 `audio.stt.openai.model`）| 已修正 |
| edge-tts 預設需要 API Key | 啟動時加 `-e REQUIRE_API_KEY=False` |
| Open WebUI 用 `--network=host`，`host.docker.internal` 無效 | 改用 `127.0.0.1` |
| breezyvoice-server（port 7860）佔用 3.27 GB VRAM | 需要時 `sudo kill -9 <pid>` 釋放 |
| Open WebUI 日期回答錯誤 | Filter 無法自動注入，改用 cron 更新 system prompt |
| Marker 與 Gemma 4 26B VRAM 衝突 | 使用 26B 前停止 marker-server |
| container 重啟後 R 消失 | `docker exec open-webui apt-get install -y r-base` |
| PDF Reader 找不到檔案 | 用對話框 [+] 上傳檔案，或確認路徑在 container 內可存取 |
| Open WebUI 出現 500 error | `docker restart open-webui` |
