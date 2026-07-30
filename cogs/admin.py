import discord
from discord import app_commands
from discord.ext import commands

class Admin(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        print("[ADMIN] Cog de administração carregado.")

    @app_commands.command(name="clear", description="Limpa mensagens do chat atual (Apenas Administradores)")
    @app_commands.describe(quantidade="Número de mensagens a apagar (deixa em branco para apagar as 100 mais recentes)")
    @app_commands.checks.has_permissions(administrator=True)
    async def clear(self, interaction: discord.Interaction, quantidade: int = 100):
        await interaction.response.defer(ephemeral=True)

        if quantidade < 1:
            await interaction.followup.send("⚠️ Indica um número válido de mensagens para apagar.", ephemeral=True)
            return

        try:
            # Apaga as mensagens recentes no canal atual
            deleted = await interaction.channel.purge(limit=quantidade)
            await interaction.followup.send(f"🧹 **{len(deleted)}** mensagens foram apagadas com sucesso.", ephemeral=True)
        except discord.Forbidden:
            await interaction.followup.send("❌ O bot não tem permissões para gerir e apagar mensagens neste canal.", ephemeral=True)
        except Exception as e:
            print(f"[ADMIN] Erro ao limpar chat: {e}")
            await interaction.followup.send("❌ Ocorreu um erro ao tentar limpar o chat.", ephemeral=True)

    @clear.error
    async def clear_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingPermissions):
            if interaction.response.is_done():
                await interaction.followup.send("❌ Não tens permissões de **Administrador** para usar este comando.", ephemeral=True)
            else:
                await interaction.response.send_message("❌ Não tens permissões de **Administrador** para usar este comando.", ephemeral=True)
        else:
            if not interaction.response.is_done():
                await interaction.response.send_message("❌ Ocorreu um erro inesperado.", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(Admin(bot))
