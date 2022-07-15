import typing as t

import utilities.exceptions

from . import models


class ContentNotCached(utilities.exceptions.NotCached):
    """The provided content page could not be found in the Redis cache."""

    def __init__(self, key: str, model: t.Type[models.AnyModel]):
        self.key = key
        self.model = model

    def __str__(self):
        return f"Could not find a cached {self.model.__name__} with key {self.key}."
