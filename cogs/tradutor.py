import asyncio
import discord
from discord.ext import commands
from deep_translator import GoogleTranslator

class Tradutor(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        # Ignora reações do próprio bot
        if payload.user_id == self.bot.user.id:
            return

        # Verifica se a reação é o emoji de tradução 🔀
        if str(payload.emoji) == "🔀":
            channel = self.bot.get_channel(payload.channel_id)
            if not channel:
                try:
                    channel = await self.bot.fetch_channel(payload.channel_id)
                except Exception:
                    return

            try:
                # Procura a mensagem original
                message = await channel.fetch_message(payload.message_id)
                if not message.content:
                    return

                # Executa a tradução em background para não bloquear o bot
                loop = asyncio.get_event_loop()
                texto_traduzido = await loop.run_in_executor(
                    None,
                    lambda: GoogleTranslator(source='auto', target='pt').translate(message.content)
                )

                # Monta o Embed mantendo a identidade visual do autor da mensagem original
                embed = discord.Embed(
                    description=texto_traduzido,
                    color=discord.Color.blue(),
                    timestamp=message.created_at
                )
                embed.set_author(
                    name=f"Tradução de {message.author.display_name}",
                    icon_url=message.author.display_avatar.url
                )
                embed.set_footer(text="🌐 Sistema de Tradução Omerta // Reação 🔀")

                # Envia no privado (DM) do utilizador que reagiu
                user = await self.bot.fetch_user(payload.user_id)
                await user.send(embed=embed)

            except Exception as e:
                print(f"[TRADUTOR] Erro ao processar tradução: {e}")


# Ponto de entrada obrigatório para o Discord.py carregar o cog
async def setup(bot: commands.Bot):
    await bot.add_cog(Tradutor(bot))
