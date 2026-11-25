
import os
from dotenv import load_dotenv

load_dotenv()


class Config:

    SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "change-this-secret-before-deployment")

    MONGO_URI = os.getenv(
        "MONGO_URI",
        "mongodb://localhost:27017/"
    )

    MONGO_DB_NAME = os.getenv(
        "MONGO_DB_NAME",
        "evomindagri"
    )

    # Local LLM configuration
    OLLAMA_MODEL = os.getenv(
        "OLLAMA_MODEL",
        "qwen2.5:3b"
    )
