import os
from pathlib import Path

import uvicorn
from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parent
load_dotenv(PROJECT_ROOT / ".env")


def main() -> None:
    from backend.main import app

    port = int(os.getenv("PORT", "8000"))
    if not 0 <= port <= 65535:
        raise ValueError("PORT must be between 0 and 65535.")
    uvicorn.run(app, host=os.getenv("HOST", "0.0.0.0"), port=port)


if __name__ == "__main__":
    main()
