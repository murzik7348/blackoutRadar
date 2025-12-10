#!/usr/bin/env bash
set -e
cd ocr_service
docker build -t uk-blackout-ai .
docker run --rm -p 8000:8000 -e TESSERACT_CMD=tesseract uk-blackout-ai
