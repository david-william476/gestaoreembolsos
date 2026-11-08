import os
from pathlib import Path

# Os dados locais ficam juntos na pasta BD do projeto.
BASE_DIR = Path(__file__).resolve().parent.parent
DATABASE_DIR = BASE_DIR / "BD"
DATABASE_DIR.mkdir(parents=True, exist_ok=True)
DATABASE_PATH = DATABASE_DIR / "reembolsos.db"
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DATABASE_PATH.as_posix()}")
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "dev-only-change-this-secret-before-deployment")
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_MINUTES = int(os.getenv("ACCESS_TOKEN_MINUTES", "30"))
