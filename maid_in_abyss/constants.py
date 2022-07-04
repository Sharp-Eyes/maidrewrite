import os

import dotenv

dotenv.load_dotenv()


class BotConfig:
    TOKEN = os.environ["BOT_TOKEN"]


class RedisConfig:
    URL = os.environ.get("REDIS_URI", "redis://127.0.0.1/6379")
    USE_FAKEREDIS = os.environ.get("USE_FAKEREDIS", "false").lower() == "true"


class DBConfig:
    URL = os.environ.get("DB_URL", "")
