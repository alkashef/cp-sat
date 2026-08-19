"""Ensures backend/ is importable so app.py's bare `import storage` resolves."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))
