class NotCached(KeyError):
    """The provided key could not be found in the Redis cache."""

    def __init__(self, key: str):
        self.key = key

    def __str__(self):
        return f"Key {self.key} could not be found in the redis cache."
