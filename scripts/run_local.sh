#!/usr/bin/env bash
set -e
cd ocr_service
uvicorn app:app --host 0.0.0.0 --port 8000
