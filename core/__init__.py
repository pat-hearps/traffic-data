import sys
from pathlib import Path

# using versioning option 4 from https://packaging.python.org/en/latest/guides/single-sourcing-package-version/
version_file = Path(__file__).parent / "VERSION"
__version__ = version_file.read_text().strip()

print(f"Initiating core module with Python version {sys.version}")
print(f"traffic-data version = {__version__}")
