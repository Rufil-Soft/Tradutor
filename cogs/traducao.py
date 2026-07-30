import asyncio
import discord
from discord.ext import commands
from deep_translator import GoogleTranslator

translation_cache = {}

class Traducao(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        print("[TRADUÇÃO] Cog carregado. Sistema por reação (🔀) ativo.")

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        # Ignora reações do próprio bot
        if payload.user_id == self.bot.user.id:
            return

        # Verifica se o emoji é a seta de tradução 🔀
        if str(payload.emoji) != "🔀":
            return

        channel = self.bot.get_channel(payload.channel_id)
        if not channel:
            return

        try:
            message = await channel.fetch_message(payload.message_id)
        except Exception:
            return

        if not message.content:
            return

        # Obtém o utilizador que reagiu
        user = self.bot.get_user(payload.user_id)
        if not user or user.bot:
            return

        texto_para_traduzir = message.content

        # Tenta detetar o idioma do utilizador (padrão 'pt')
        target_lang = "pt"

        cache_key = (texto_para_traduzir, target_lang)
        if cache_key in translation_cache:
            translated = translation_cache[cache_key]
        else:
            try:
                translated = await asyncio.to_thread(
                    GoogleTranslator(source='auto', target=target_lang).translate,
                    texto_para_traduzir
                )
                if translated:
                    translation_cache[cache_key] = translated
            except Exception as e:
                print(f"[TRADUTOR] Erro ao traduzir por reação: {e}")
                return

        if not translated:
            return

        # Envia a tradução por mensagem privada (DM) para preservar a estética dos chats
        embed = discord.Embed(
            title="🌐 Tradução Omertà",
            description=translated,
            color=discord.Color.blue(),
            timestamp=message.created_at
        )
        embed.set_author(
            name=message.author.display_name,
            icon_url=message.author.display_avatar.url if message.author.display_avatar else None
        )
        embed.set_footer(text="Cosa Nostra System • Tradução Privada")

        try:
            await user.send(embed=embed)
        except discord.Forbidden:
            # Caso o utilizador tenha as DMs fechadas, tenta enviar uma mensagem temporária no canal
            try:
                await channel.send(f"{user.mention} ⚠️ Não consegui enviar a tradução por MP (as tuas DMs estão fechadas).", delete_after=10)
            except Exception:
                pass


async def setup(bot: commands.Bot):
    await bot.add_cog(Traducao(bot))
