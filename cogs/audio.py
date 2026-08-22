import asyncio
import io
import os
import discord
from discord.ext import commands
from groq import AsyncGroq
from cogs.traducao import TranslateView, registar_mensagem

class Audio(commands.Cog):
    """Transcreve mensagens de voz e integra com o sistema de tradução."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.groq_client = None
        self._init_groq()

    def _init_groq(self):
        api_key = os.getenv("GROQ_API_KEY")
        if api_key:
            self.groq_client = AsyncGroq(api_key=api_key)
            print("[AUDIO] Cliente Groq inicializado para transcrição.")
        else:
            print("[AUDIO] ⚠️ GROQ_API_KEY não definida. Transcrição indisponível.")

    async def transcrever_audio(self, audio_bytes: bytes, filename: str) -> str:
        """Envia o áudio para a Groq Whisper e devolve o texto transcrito."""
        if not self.groq_client:
            return None

        audio_file = io.BytesIO(audio_bytes)
        audio_file.name = filename  # importante para a API reconhecer o formato

        try:
            transcription = await self.groq_client.audio.transcriptions.create(
                model="whisper-large-v3-turbo",   # rápido e preciso
                file=audio_file,
                response_format="text"
            )
            return transcription.strip()
        except Exception as e:
            print(f"[AUDIO] Erro na transcrição: {e}")
            return None

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        # Verifica se a mensagem contém algum anexo de áudio
        if not message.attachments:
            return

        attachment = message.attachments[0]
        if not (attachment.content_type or "").startswith("audio/"):
            return

        # Limite de tamanho (opcional, evita abusos)
        if attachment.size > 10 * 1024 * 1024:
            await message.channel.send("❌ O áudio é muito grande para transcrição.", delete_after=10)
            return

        # Descarrega o áudio
        try:
            audio_bytes = await attachment.read()
        except Exception as e:
            print(f"[AUDIO] Erro ao baixar áudio: {e}")
            return

        # Transcreve
        transcricao = await self.transcrever_audio(audio_bytes, attachment.filename)
        if not transcricao:
            await message.channel.send("❌ Não foi possível transcrever o áudio.", delete_after=10)
            return

        # Tenta apagar a mensagem original
        try:
            await message.delete()
        except discord.Forbidden:
            pass

        # Republica a transcrição no formato usado pelo traducao.py
        conteudo_formatado = f"<@{message.author.id}>: {transcricao}"
        try:
            msg_enviada = await message.channel.send(
                content=conteudo_formatado,
                view=TranslateView(),
                allowed_mentions=discord.AllowedMentions(users=False)
            )
            registar_mensagem(msg_enviada.id, conteudo_formatado, transcricao)
        except Exception as e:
            print(f"[AUDIO] Erro ao republicar transcrição: {e}")

async def setup(bot: commands.Bot):
    await bot.add_cog(Audio(bot))
