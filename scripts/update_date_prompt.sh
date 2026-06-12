#!/bin/bash
docker exec open-webui python3 -c "
import sqlite3, json, time
from datetime import datetime
from zoneinfo import ZoneInfo

now = datetime.now(ZoneInfo('Asia/Taipei'))
date_str = now.strftime('%Y-%m-%d (%A)')

new_system = f'''Today is {date_str} (Asia/Taipei).

You have access to the following tools — use them proactively:
- get_current_datetime: call this for any question about current date or time
- search_web: call this for any question about current events, recent news, latest information, or anything that may have changed after your training cutoff
- run_python / run_r: call this to execute code or perform calculations
- read_pdf: call this when the user provides a PDF filename or path

Never answer questions about current events or recent information from memory. Always use search_web instead.'''

params = json.dumps({'system': new_system})
ts = int(time.time())

conn = sqlite3.connect('/app/backend/data/webui.db')
cur = conn.cursor()
cur.execute(\"SELECT id FROM model WHERE is_active = 1\")
model_ids = [row[0] for row in cur.fetchall()]
for mid in model_ids:
    cur.execute('UPDATE model SET params=?, updated_at=? WHERE id=?', (params, ts, mid))
conn.commit()
conn.close()
print(f'Updated {len(model_ids)} models')
"
