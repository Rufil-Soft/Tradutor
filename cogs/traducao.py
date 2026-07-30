import asyncio
import discord
from discord.ext import commands
from deep_translator import GoogleTranslator

translation_cache = {}

class Traducao(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        print("[TRADUÇÃO] Cog carregado. Sistema por reação ativo.")

    # 1. Adiciona o emoji 🔀 automaticamente a todas as novas mensagens
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.content:
            return
        if message.content.startswith(self.bot.command_prefix):
            return
        if message.channel.name == "🎯-capos-message":
            return

        try:
            await message.add_reaction("🔀")
        except discord.Forbidden:
            pass
        except Exception as e:
            print(f"[TRADUÇÃO] Erro ao adicionar reação: {e}")

    # 2. Quando alguém clica na reação 🔀
    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        # Ignora reações do próprio bot
        if payload.user_id == self.bot.user.id:
            return

        # Verifica se o emoji é 🔀
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

        # Procura o utilizador de forma assíncrona (garante que encontra mesmo fora da cache)
        try:
            user = await self.bot.fetch_user(payload.user_id)
        except Exception:
            user = self.bot.get_user(payload.user_id)

        if not user or user.bot:
            return

        # REMOVE a reação do utilizador para a contagem voltar ao normal (1) e o botão ficar limpo
        try:
            await message.remove_reaction(payload.emoji, user)
        except Exception:
            pass

        texto_para_traduzir = message.content
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
                print(f"[TRADUTOR] Erro na tradução: {e}")
                return

        if not translated:
            return

        # Envia a tradução por Mensagem Privada
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
            try:
                await channel.send(f"{user.mention} ⚠️ Abre as tuas DMs/Mensagens Privadas para receber a tradução!", delete_after=8)
            except Exception:
                pass


async def setup(bot: commands.Bot):
    await bot.add_cog(Traducao(bot))
