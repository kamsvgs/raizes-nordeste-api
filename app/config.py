"""Configuração da aplicação (variáveis de ambiente / arquivo .env)."""
import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./raizes.db")
    SECRET_KEY: str = os.getenv("SECRET_KEY", "troque-esta-chave-em-desenvolvimento-com-32-chars-ou-mais")
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_MINUTES: int = int(os.getenv("ACCESS_TOKEN_MINUTES", "60"))
    BCRYPT_ROUNDS: int = int(os.getenv("BCRYPT_ROUNDS", "12"))
    GATEWAY_TIMEOUT_SECONDS: float = float(os.getenv("GATEWAY_TIMEOUT_SECONDS", "3"))


settings = Settings()
