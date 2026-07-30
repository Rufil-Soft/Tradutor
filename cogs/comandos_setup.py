import discord
from discord.ext import commands
from config import FAMILIAS, LIMITE_SOLDIERS
from cogs.logs import enviar_log_mafia
from bot import bot

class ComandosSetup(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="sync")
    @commands.has_permissions(administrator=True)
    async def sync_commands(self, ctx):
        try:
            bot.tree.copy_global_to(guild=ctx.guild)
            synced = await bot.tree.sync(guild=ctx.guild)
            await ctx.send(f"✅ Sincronizados **{len(synced)}** comandos de barra neste servidor!")
        except Exception as e:
            await ctx.send(f"❌ Erro ao sincronizar: {e}")

    @commands.command(name="setup_logs")
    @commands.has_permissions(administrator=True)
    async def setup_logs(self, ctx):
        guild = ctx.guild
        nome_canal = "🕶️-mafia-logs"
        canal_existente = discord.utils.get(guild.text_channels, name=nome_canal)
        if canal_existente:
            await ctx.send(f"⚠️ O canal de logs já existe: {canal_existente.mention}")
            return
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }
        for role in guild.roles:
            if role.permissions.administrator:
                overwrites[role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
        canal = await guild.create_text_channel(name=nome_canal, overwrites=overwrites, topic="Registo oficial de movimentações e lealdade das Famílias.")
        await ctx.send(f"✅ Canal de logs criado: {canal.mention}")

    @commands.command(name="setup_capos_message")
    @commands.has_permissions(administrator=True)
    async def setup_capos_message(self, ctx):
        # ... (igual ao original)
        pass

    @commands.command(name="setup_vota_message")
    @commands.has_permissions(administrator=True)
    async def setup_vota_message(self, ctx):
        # ... (nome atualizado para "🗳️ vote-command")
        pass

    @commands.command(name="status_familias")
    @commands.has_permissions(administrator=True)
    async def status_familias(self, ctx):
        # ... (relatório)
        pass

async def setup(bot: commands.Bot):
    await bot.add_cog(ComandosSetup(bot))
