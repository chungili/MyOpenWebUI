"""
title: PDF Reader (Marker)
author: local
version: 2.0.0
description: Convert PDF to Markdown using Marker. Accepts file path or filename of an uploaded file.
"""

import httpx
import os
import sqlite3


class Tools:
    def __init__(self):
        self.marker_url = "http://localhost:8003/convert"
        self.db_path = "/app/backend/data/webui.db"
        self.uploads_dir = "/app/backend/data/uploads"

    def _find_uploaded_pdf(self, filename: str) -> str | None:
        """Look up an uploaded file by filename in the Open WebUI database."""
        try:
            conn = sqlite3.connect(self.db_path)
            cur = conn.cursor()
            cur.execute(
                "SELECT path FROM file WHERE filename LIKE ? ORDER BY created_at DESC LIMIT 1",
                (f"%{filename}%",)
            )
            row = cur.fetchone()
            conn.close()
            if row and row[0] and os.path.exists(row[0]):
                return row[0]
        except Exception:
            pass
        return None

    async def read_pdf(self, file_path: str) -> str:
        """
        Read a PDF file and convert it to Markdown, including text, tables, formulas, and figure descriptions.
        Use this when the user wants to read, analyze, or summarize a PDF document or academic paper.
        The file_path can be:
        - An absolute path on the server (e.g. /home/user/paper.pdf)
        - Just the filename of a file uploaded in this conversation (e.g. paper.pdf)
        :param file_path: absolute path or uploaded filename of the PDF
        :return: full Markdown content of the PDF
        """
        # resolve path: try absolute first, then look up in uploads
        resolved_path = None

        if os.path.exists(file_path):
            resolved_path = file_path
        else:
            # try to find by filename in uploaded files
            resolved_path = self._find_uploaded_pdf(os.path.basename(file_path))

        if not resolved_path:
            return (
                f"Error: cannot find '{file_path}'.\n"
                "Please either:\n"
                "1. Upload the PDF using the [+] button in the chat, then say the filename\n"
                "2. Provide the full path on the server (e.g. /home/user/paper.pdf)"
            )

        if not resolved_path.lower().endswith(".pdf"):
            return "Error: only PDF files are supported"

        try:
            async with httpx.AsyncClient(timeout=300.0) as client:
                with open(resolved_path, "rb") as f:
                    response = await client.post(
                        self.marker_url,
                        files={"file": (os.path.basename(resolved_path), f, "application/pdf")}
                    )
            if response.status_code != 200:
                return f"Error: Marker server returned {response.status_code}: {response.text}"

            data = response.json()
            markdown = data.get("markdown", "")
            if not markdown:
                return "Error: no content extracted from PDF"

            return f"# {os.path.basename(resolved_path)}\n\n{markdown}"

        except httpx.ConnectError:
            return "Error: cannot connect to Marker server (port 8003). Please ensure the marker-server service is running."
        except Exception as e:
            return f"Error: {str(e)}"
