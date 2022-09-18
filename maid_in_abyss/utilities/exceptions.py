import typing as t

import disnake


class MaidException(Exception):
    """Base class for all custom exceptions, mainly for ease of type introspection."""

    def __embed_repr__(self) -> t.List[disnake.Embed]:
        return [disnake.Embed(title="Oh no!", description=str(self))]


class CacheFailure(KeyError, MaidException):
    """Base exception for when the provided key could not be found in the Redis cache."""

    def __init__(self, key: str):
        self.key = key

    def __str__(self) -> str:
        return f"Key `{self.key}` could not be found in the redis cache."


class DBFailure(KeyError, MaidException):
    """Base exception for when the provided DB query unintentionally failed to produce results."""

    def __init__(self, key: str):
        self.query = key

    def __str__(self) -> str:
        return f"Query `{self.query}` did not produce any results."


class NotPermitted(ValueError, MaidException):
    """Base exception for when a user tries an action that is not permitted."""

    def __init__(
        self,
        reason: str,
        permissions: t.Optional[disnake.Permissions] = None,
        required: t.Optional[disnake.Permissions] = None,
    ):
        self.reason = reason

        if permissions and required:
            diff = required.value - permissions.value
            self.perms = disnake.Permissions(diff)
        else:
            self.perms = None

    def __str__(self) -> str:
        return self.reason

    def __embed_repr__(self) -> t.List[disnake.Embed]:
        embed = disnake.Embed(
            title="You are not permitted to take this action...",
            description=self.reason,
        )
        if self.perms:
            embed.add_field(
                name="Missing permissions:",
                value=", ".join(perm for perm, value in self.perms if value),
            )

        return [embed]
