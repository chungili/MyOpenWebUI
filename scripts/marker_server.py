#!/usr/bin/env python3
"""Marker PDF processing server for Open WebUI integration."""

import os
import tempfile
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse

app = FastAPI()


@app.post("/convert")
async def convert_pdf(file: UploadFile = File(...)):
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    with tempfile.TemporaryDirectory() as tmpdir:
        pdf_path = os.path.join(tmpdir, file.filename)
        with open(pdf_path, "wb") as f:
            f.write(await file.read())

        from marker.converters.pdf import PdfConverter
        from marker.models import create_model_dict
        from marker.config.parser import ConfigParser

        config = ConfigParser({"output_format": "markdown"})
        models = create_model_dict()
        converter = PdfConverter(config=config.generate_config_dict(), artifact_dict=models)
        rendered = converter(pdf_path)

        return JSONResponse({"markdown": rendered.markdown, "filename": file.filename})


@app.get("/health")
async def health():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8003)
