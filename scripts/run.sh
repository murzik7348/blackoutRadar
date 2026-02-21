
#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"

# Create venv next to project
if [ ! -d ".venv" ]; then
  python3 -m venv .venv
fi

. .venv/bin/activate
python -m pip install --upgrade pip
pip install --no-cache-dir -r requirements.txt

# Run your project via module launcher
python -m telegram_bot
