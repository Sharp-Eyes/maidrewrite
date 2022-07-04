from __future__ import annotations
import asyncio

import dataclasses
import inspect
import typing as t

import disnake
from disnake.ext import commands

import logging

__all__ = ("Plugin",)

LOGGER = logging.getLogger(__name__)


T = t.TypeVar("T")
P = t.ParamSpec("P")
Coro = t.Coroutine[t.Any, t.Any, T]
EmptyAsync = t.Callable[[], Coro[None]]

AnyCommand = commands.Command[t.Any, t.Any, t.Any]

LocalizedOptional = t.Union[t.Optional[str], disnake.Localized[t.Optional[str]]]
PermissionsOptional = t.Optional[t.Union[disnake.Permissions, int]]


MAX_FRAME_DEPTH = 10


class CommandParams(t.TypedDict, total=False):
    name: str
    help: str
    brief: str
    usage: str
    aliases: t.Union[t.List[str], t.Tuple[str]]
    enabled: bool
    description: str
    hidden: bool
    ignore_extra: bool
    cooldown_after_parsing: bool
    extras: t.Dict[str, t.Any]


class AppCommandParams(t.TypedDict, total=False):
    name: LocalizedOptional
    auto_sync: bool
    dm_permission: bool
    default_member_permissions: PermissionsOptional
    guild_ids: t.Sequence[int]
    extras: t.Dict[str, t.Any]


class SlashCommandParams(AppCommandParams, total=False):
    description: LocalizedOptional
    connectors: t.Dict[str, str]


@dataclasses.dataclass
class PluginMetadata:
    name: str
    category: t.Optional[str] = None
    
    command_attrs: CommandParams = dataclasses.field(default_factory=CommandParams)
    slash_command_attrs: SlashCommandParams = dataclasses.field(default_factory=SlashCommandParams)
    message_command_attrs: AppCommandParams = dataclasses.field(default_factory=AppCommandParams)
    user_command_attrs: AppCommandParams = dataclasses.field(default_factory=AppCommandParams)


def _get_source_module_name() -> str:
    try:
        frame = inspect.currentframe()
        for _ in range(MAX_FRAME_DEPTH):
            name = (frame := frame.f_back).f_globals["__name__"]  # type: ignore[reportOptionalMemberAccess]
            if name != __name__:
                return name

    except (AttributeError, KeyError):
        pass
    
    raise TypeError("Failed to infer a name for this plugin. Please provide one manually.")


class Plugin:

    __slots__ = (
        "metadata",
        "commands",
        "slash_commands",
        "message_commands",
        "listeners",
        "user_commands",
        "_pre_load_hooks",
        "_post_load_hooks",
    )

    _pre_load_hooks: t.List[t.Callable[[], Coro[None]]]
    _post_load_hooks: t.List[t.Callable[[], Coro[None]]]

    # dependencies: PluginDependencyManager
    # global_dependencies: PluginDependencyManager = PluginDependencyManager()  # TODO: remove?

    def __init__(self, metadata: PluginMetadata):
        self.metadata = metadata
        self.commands: t.Dict[str, commands.Command[Plugin, t.Any, t.Any]] = {}  # type: ignore
        self.slash_commands: t.Dict[str, commands.InvokableSlashCommand] = {}
        self.message_commands: t.Dict[str, commands.InvokableMessageCommand] = {}
        self.user_commands: t.Dict[str, commands.InvokableUserCommand] = {}

        self.listeners: t.Dict[str, t.List[t.Callable[..., Coro[t.Any]]]] = {}

        self._pre_load_hooks = []
        self._post_load_hooks = []

        # self.dependencies = PluginDependencyManager()


    @classmethod
    def with_metadata(
        cls,
        *,
        name: t.Optional[str] = None,
        category: t.Optional[str] = None,
        command_attrs: CommandParams = CommandParams(),
        slash_command_attrs: SlashCommandParams = SlashCommandParams(),
        message_command_attrs: AppCommandParams = AppCommandParams(),
        user_command_attrs: AppCommandParams = AppCommandParams(),
    ) -> Plugin:
        return cls(PluginMetadata(
            name=name or _get_source_module_name(),
            category=category,
            command_attrs=command_attrs,
            slash_command_attrs=slash_command_attrs,
            message_command_attrs=message_command_attrs,
            user_command_attrs=user_command_attrs, 
        ))

    @property
    def name(self) -> str:
        return self.metadata.name

    @property
    def category(self) -> t.Optional[str]:
        return self.metadata.category

    def apply_attrs(self, attrs: t.Mapping[str, t.Any], **kwargs: t.Any) -> t.Dict[str, t.Any]:
        new_attrs = attrs | {k: v for k, v in kwargs.items() if v is not None}
        new_attrs.setdefault("extras", {})["metadata"] = self.metadata
        return new_attrs

    def command(
        self,
        name: t.Optional[str] = None,
        *,
        cls: t.Optional[t.Type[commands.Command[t.Any, t.Any, t.Any]]] = None,
        **kwargs: t.Any,
    ):
        attributes = self.apply_attrs(self.metadata.command_attrs, name=name, **kwargs)

        if cls is None:
            cls = t.cast(t.Type[AnyCommand], attributes.pop("cls", AnyCommand))

        def decorator(callback: t.Callable[..., Coro[t.Any]]) -> AnyCommand:
            if not asyncio.iscoroutinefunction(callback):
                raise TypeError(f"<{callback.__qualname__}> must be a coroutine function")

            if attributes["name"] is None:
                attributes["name"] = callback.__name__

            command = cls(callback, **attributes)
            self.commands[command.qualified_name] = command

            return command
        return decorator

    def slash_command(
        self,
        *,
        name: LocalizedOptional = None,
        description: LocalizedOptional = None,
        dm_permission: t.Optional[bool] = None,
        default_member_permissions: PermissionsOptional = None,
        guild_ids: t.Optional[t.Sequence[int]] = None,
        connectors: t.Optional[t.Dict[str, str]] = None,
        auto_sync: t.Optional[bool] = None,
        extras: t.Optional[t.Dict[str, t.Any]] = None,
    ):
        attributes = self.apply_attrs(
            self.metadata.slash_command_attrs,
            name=name,
            description=description,
            dm_permission=dm_permission,
            default_member_permissions=default_member_permissions,
            guild_ids=guild_ids,
            connectors=connectors,
            auto_sync=auto_sync,
            extras=extras,
        )

        def decorator(callback: t.Callable[..., Coro[t.Any]]) -> commands.InvokableSlashCommand:
            if not asyncio.iscoroutinefunction(callback):
                raise TypeError(f"<{callback.__qualname__}> must be a coroutine function")
            
            command = commands.InvokableSlashCommand(callback, **attributes)
            self.slash_commands[command.qualified_name] = command

            return command
        return decorator

    def listener(self, event: t.Optional[str] = None):

        def decorator(callback: t.Callable[..., Coro[t.Any]]) -> t.Callable[..., Coro[t.Any]]:
            key = callback.__name__ if event is None else event
            self.listeners.setdefault(key, []).append(callback)
            return callback

        return decorator
            

    async def load(self, bot: commands.Bot) -> None:
        await asyncio.gather(hook() for hook in self._pre_load_hooks)

        for command in self.commands.values():
            bot.add_command(command)

        for command in self.slash_commands.values():
            bot.add_slash_command(command)

        for event, listeners in self.listeners.items():
            for listener in listeners:
                bot.add_listener(listener, event)

        await asyncio.gather(hook() for hook in self._post_load_hooks)
        LOGGER.info(f"Successfully loaded plugin `{self.metadata.name}`")

    async def unload(self, bot: commands.Bot) -> None:
        for command in self.commands.keys():
            bot.remove_command(command)

        for command in self.slash_commands.keys():
            bot.remove_slash_command(command)

        for event, listeners in self.listeners.items():
            for listener in listeners:
                bot.remove_listener(listener, event)

        LOGGER.info(f"Successfully unloaded plugin `{self.metadata.name}`")

    def load_hook(self, post: bool = False) -> t.Callable[[EmptyAsync], EmptyAsync]:
        hooks = self._post_load_hooks if post else self._pre_load_hooks

        def wrapper(callback: t.Callable[[], Coro[None]]) -> EmptyAsync:
            hooks.append(callback)
            return callback

        return wrapper

    def create_extension_handlers(self) -> t.Tuple[
        t.Callable[[commands.Bot], None],
        t.Callable[[commands.Bot], None],
    ]:
        def setup(bot: commands.Bot) -> None:
            asyncio.create_task(self.load(bot))

        def teardown(bot: commands.Bot) -> None:
            asyncio.create_task(self.unload(bot))

        return setup, teardown


# def with_metadata(
#     *,
#     name: t.Optional[str] = None,
#     category: t.Optional[str] = None,
#     command_attrs: CommandParams = CommandParams(),
#     slash_command_attrs: SlashCommandParams = SlashCommandParams(),
#     message_command_attrs: AppCommandParams = AppCommandParams(),
#     user_command_attrs: AppCommandParams = AppCommandParams(),
# ) -> Plugin:
#     return Plugin(PluginMetadata(
#         name=name or _get_source_module_name(),
#         category=category,
#         command_attrs=command_attrs,
#         slash_command_attrs=slash_command_attrs,
#         message_command_attrs=message_command_attrs,
#         user_command_attrs=user_command_attrs, 
#     ))