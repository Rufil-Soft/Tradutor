import discord
from discord import app_commands
from discord.ext import commands
from deep_translator import GoogleTranslator
import asyncio

class TradutorProfissional(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # Regista o comando no menu do botão direito do Discord
        self.ctx_menu = app_commands.ContextMenu(
            name='Traduzir Mensagem',
            callback=self.traduzir_mensagem,
        )
        self.bot.tree.add_command(self.ctx_menu)

    async def cog_unload(self):
        self.bot.tree.remove_command(self.ctx_menu.name, type=self.ctx_menu.type)

    async def traduzir_mensagem(self, interaction: discord.Interaction, message: discord.Message):
        if not message.content:
            await interaction.response.send_message("❌ Esta mensagem não contém texto para traduzir.", ephemeral=True)
            return

        # Resposta privada em segundo plano
        await interaction.response.defer(ephemeral=True)

        # Deteta automaticamente o idioma da aplicação do utilizador (ex: pt, en, es, fr)
        user_locale = str(interaction.locale).split("-")[0] or "pt"

        try:
            # Executa a tradução sem bloquear o bot
            translated = await asyncio.to_thread(
                GoogleTranslator(source='auto', target=user_locale).translate,
                message.content
            )

            embed = discord.Embed(
                description=f"💬 **Tradução:**\n{translated}",
                color=discord.Color.blue()
            )
            embed.set_author(name=message.author.display_name, icon_url=message.author.display_avatar.url)
            embed.set_footer(text=f"Idioma detetado para a tua conta: {user_locale.upper()}")

            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            print(f"[TRADUTOR CHAT] Erro ao traduzir: {e}")
            await interaction.followup.send("❌ Não foi possível traduzir esta mensagem no momento.", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(TradutorProfissional(bot))
