from discord.ext import commands


class MembersOrRoles(commands.Converter):
    async def convert(self, ctx, argument):
        members = []
        for arg in argument.split():
            try:
                member = await commands.MemberConverter().convert(ctx, arg)
            except commands.BadArgument:
                member = await commands.RoleConverter().convert(ctx, arg)
            members.append(member)
        return members