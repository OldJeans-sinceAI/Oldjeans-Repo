"""Keep simulator truth in the separate supplied mock API process."""

import os, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "mock_api"))
import server

server.STATE_FILE = os.environ["CONNECT_MOCK_STATE"]
os.environ["MOCK_QUIET"] = "1"
server.main()
