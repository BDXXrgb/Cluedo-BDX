import os

SECRET_KEY = os.getenv("SECRET_KEY", "change-moi")
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./bdx_cluedo.db")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "240"))
ALGORITHM = "HS256"