#!/bin/bash
# Pornește generatorul de scheme monofilare și deschide browserul (dublu-clic în Finder).
cd "$(dirname "$0")"
python3 -c "import ezdxf" 2>/dev/null || python3 -m pip install --user ezdxf
(sleep 1.5; open "http://localhost:8765") &
python3 app.py 8765
