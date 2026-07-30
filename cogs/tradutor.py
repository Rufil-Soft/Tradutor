import discord
from discord.ext import commands
from deep_translator import GoogleTranslator
import asyncio

class TradutorReacao(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.emoji_traducao = "🔀"

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # Ignora mensagens do próprio bot ou mensagens sem texto
        if message.author.bot or not message.content:
            return

        # Adiciona automaticamente o ícone 🔀 por baixo da mensagem do jogador
        try:
            await message.add_reaction(self.emoji_traducao)
        except Exception:
            pass

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        # Ignora se for o próprio bot a reagir
        if payload.user_id == self.bot.user.id:
            return

        # Verifica se o ícone clicado foi o 🔀
        if str(payload.emoji) == self.emoji_traducao:
            channel = self.bot.get_channel(payload.channel_id)
            if not channel:
                return

            try:
                message = await channel.fetch_message(payload.message_id)
                user = self.bot.get_user(payload.user_id) or await self.bot.fetch_user(payload.user_id)

                if not message.content:
                    return

                # Traduz a mensagem para o idioma do utilizador (ou padrão 'pt')
                translated = await asyncio.to_thread(
                    GoogleTranslator(source='auto', target='pt').translate,
                    message.content
                )

                embed = discord.Embed(
                    description=f"💬 **Tradução da Mensagem:**\n{translated}",
                    color=discord.Color.blue()
                )
                embed.set_author(name=message.author.display_name, icon_url=message.author.display_avatar.url)
                embed.set_footer(text=f"Enviado por: {message.author.display_name}")

                # Envia no privado de quem clicou na reação
                await user.send(embed=embed)

            except Exception as e:
                print(f"[TRADUTOR REAÇÃO] Erro: {e}")


async def setup(bot: commands.Bot):
    await bot.add_cog(TradutorReacao(bot))
