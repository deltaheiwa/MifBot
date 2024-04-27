import discord
from discord.ext import commands

from bot_util.misc import AsyncTranslator
from db_data.psql_main import DatabaseFunctions as DF


class Stats(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        print("Stats cog loaded successfully!")

    @commands.hybrid_command(
        aliases=["bstats"],
        name="bot-stats",
        description="Shows the bot usage statistics of a user",
        with_app_command=True
    )
    async def botstats(self, ctx: commands.Context, member: discord.Member = None):
        if member is None:
            member = ctx.author

        async with AsyncTranslator(DF.get_lang_code(member.id)) as at:
            at.install()
            _ = at.gettext

            if DF.check_if_member_exists(member.id) is False:
                if member == ctx.author:
                    await ctx.send(
                        _(
                            "You don't have an account yet. You can register by using command `register`"
                        )
                    )
                else:
                    await ctx.send(
                        _("{user} has no account yet").format(user=member.mention)
                    )
                return
            database_info = DF.get_user_by_id(member.id, ["nickname"])
            is_public = DF.get_user_stats_privacy(member.id)
            if not is_public:
                if member == ctx.author:
                    await ctx.defer(ephemeral=True)
                else:
                    embed = discord.Embed(
                        title=database_info["nickname"],
                        description=_(
                            "*Statistics of this user are private*"
                        ),
                        color=member.color,
                    )
                    embed.set_thumbnail(url=member.display_avatar.url)
                    await ctx.send(embed=embed)
                    return

            info = DF.get_user_stats(member.id)
            embed = discord.Embed(
                title=database_info["nickname"],
                description=_("Bot usage statistics"),
                color=member.color,
            )
            embed.set_thumbnail(url=member.display_avatar.url)
            embed.add_field(
                name=_("Total commands used"), value=info["commandsUsed"], inline=False
            )
            embed.add_field(
                name=_("Number guessing game"),
                value=_(
                    "**Wins:** \n· easy: {easy}\n· medium: {medium}\n· hard: {hard}"
                ).format(
                    easy=info["ngWins"]["easy"],
                    medium=info["ngWins"]["medium"],
                    hard=info["ngWins"]["hard"],
                ),
            )
            embed.add_field(
                name=_("Hangman game"),
                value=_(
                    "**Short Words:** {short_wins} W/{short_losses} L\n**Long Words:** {long_wins} W/{long_losses} L{legacy}"
                ).format(
                    short_wins=info["hangman"]["short"]["wins"],
                    short_losses=info["hangman"]["short"]["losses"],
                    long_wins=info["hangman"]["long"]["wins"],
                    long_losses=info["hangman"]["long"]["losses"],
                    legacy=_("\n*Legacy:* {leg_wins} W/{leg_losses} L").format(
                        leg_wins=info["hangman"]["legacy"]["wins"],
                        leg_losses=info["hangman"]["legacy"]["losses"],
                    )
                    if "legacy" in info["hangman"]
                    else "",
                ),
                inline=False,
            )
            embed.add_field(
                name=_("Bulls and Cows"),
                value=_("**Wins:** {wins} \n**Losses:** {losses}").format(
                    wins=info["bulls"]["number"]["wins"],
                    losses=info["bulls"]["number"]["losses"],
                ),
            )
            embed.add_field(
                name=_("Bagels"),
                value=_("** · Fast:** ")
                + _("{wins} Wins/{losses} Losses/{abandoned} Abandoned").format(
                    wins=info["bulls"]["pfb"]["fast"]["wins"],
                    losses=info["bulls"]["pfb"]["fast"]["losses"],
                    abandoned=info["bulls"]["pfb"]["fast"]["abandoned"],
                )
                + _("\n** · Classic:** ")
                + _("{wins} Wins/{losses} Losses/{abandoned} Abandoned").format(
                    wins=info["bulls"]["pfb"]["classic"]["wins"],
                    losses=info["bulls"]["pfb"]["classic"]["losses"],
                    abandoned=info["bulls"]["pfb"]["classic"]["abandoned"],
                )
                + _("\n** · Long:** ")
                + _("{wins} Wins/{losses} Losses/{abandoned} Abandoned").format(
                    wins=info["bulls"]["pfb"]["long"]["wins"],
                    losses=info["bulls"]["pfb"]["long"]["losses"],
                    abandoned=info["bulls"]["pfb"]["long"]["abandoned"],
                )
                + _("\n** · Hard:** ")
                + _("{wins} Wins/{losses} Losses/{abandoned} Abandoned").format(
                    wins=info["bulls"]["pfb"]["hard"]["wins"],
                    losses=info["bulls"]["pfb"]["hard"]["losses"],
                    abandoned=info["bulls"]["pfb"]["hard"]["abandoned"],
                ),
            )
            try:
                embed.add_field(
                    name=_("Rickroll"),
                    value=_(
                        "**Got rickrolled:** {themselves} \n**Rickrolled someone else:** {others}"
                    ).format(
                        themselves=info["rickroll"]["themselves"],
                        others=info["rickroll"]["others"],
                    ),
                    inline=False,
                )
            except KeyError:
                pass

            await ctx.send(embed=embed)
            DF.add_to_command_stat(ctx.author.id)


async def setup(bot):
    await bot.add_cog(Stats(bot))
