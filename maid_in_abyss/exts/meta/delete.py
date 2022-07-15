import typing as t

import disnake
from disnake.ext import components

import utilities

plugin = utilities.Plugin.with_metadata(
    name="delete_button_handler",
    category="meta",
)


@plugin.listener(components.ListenerType.BUTTON)
@components.match_component(
    component_type=disnake.ComponentType.button,
    style=disnake.ButtonStyle.red,
    emoji="<:cross_mark:904873627466477678>",
)
async def delete_button_listener(
    inter: disnake.MessageInteraction,
    *,
    user_id: int,
    permissions: t.Optional[disnake.Permissions],
):
    if (
        inter.author.id != user_id
        and permissions
        and permissions.is_strict_superset(inter.permissions)
    ):
        await inter.response.send_message(
            "Sorry, captain. You are not authorized to operate this button.",
            ephemeral=True,
        )
        return

    await inter.response.defer()
    await inter.delete_original_message()


setup, teardown = plugin.create_extension_handlers()
