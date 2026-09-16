"""Build the optional local macOS adapter before ingestion, never with input data.

Run: venv/bin/python -m app.interfaces.ocr.build_vision
Apple's system frameworks are linked, not redistributed. No downloads.
"""
from pathlib import Path
import subprocess
import sys


def build():
    if sys.platform != 'darwin':
        raise SystemExit('Apple Vision requires macOS; raster imports remain unavailable.')
    root = Path(__file__).resolve().parent
    target = root / '.build'
    target.mkdir(exist_ok=True)
    subprocess.run(['/usr/bin/clang', '-fobjc-arc', '-framework', 'Foundation', '-framework', 'Vision',
                    str(root / 'vision.m'), '-o', str(target / 'vision')], check=True)


if __name__ == '__main__':
    build()
