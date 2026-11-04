#!/usr/bin/env zsh
# Starts the synthetic-data-only local demo from this folder.
set -e
cd "${0:A:h}"

if [[ ! -x .venv/bin/python ]]; then
  python3 -m venv .venv
fi

if ! .venv/bin/python -c 'import streamlit, pypdf, docx, reportlab, pandas, PIL' >/dev/null 2>&1; then
  .venv/bin/python -m pip install -r requirements.txt
fi
exec .venv/bin/python -m streamlit run app.py --server.headless=true --server.address=127.0.0.1 --server.port=8503 --browser.gatherUsageStats=false
