from typing import Union

import discord


async def channel_perms_change(
    user: Union[discord.Member, discord.Role],
    channel: Union[discord.TextChannel, discord.VoiceChannel],
    perms_change: bool,
):
    await channel.set_permissions(
        user,
        send_messages=perms_change,
        read_messages=perms_change,
        view_channel=perms_change,
    )
