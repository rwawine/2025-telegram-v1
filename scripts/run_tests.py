from __future__ import annotations

import os
import sys
from pathlib import Path


def main() -> None:
    # Ensure project root on PYTHONPATH
    project_root = Path(__file__).resolve().parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    # Disable bot to avoid aiogram dependency during smoke tests
    os.environ["ENABLE_BOT"] = "false"

    # Run web smoke test
    from scripts.smoke_test import main as smoke
    smoke()
    print("All tests passed.")


if __name__ == "__main__":
    main()




