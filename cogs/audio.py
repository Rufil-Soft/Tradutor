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

        # Garantir que a extensão é reconhecida
        if not filename.lower().endswith((".ogg", ".mp3", ".wav", ".mp4", ".m4a", ".webm", ".flac")):
            filename += ".ogg"

        # Criar um objeto BytesIO e posicionar no início
        audio_file = io.BytesIO(audio_bytes)
        audio_file.seek(0)
        audio_file.name = filename

        print(f"[AUDIO] Processando áudio: {filename} ({len(audio_bytes)} bytes)")

        try:
            transcription = await self.groq_client.audio.transcriptions.create(
                model="whisper-large-v3-turbo",
                file=audio_file,
                response_format="text"
            )
            # Se a transcrição for uma string ou tiver .text
            texto = transcription if isinstance(transcription, str) else transcription.text
            texto = texto.strip()
            print(f"[AUDIO] Transcrição recebida: {texto!r}")
            return texto
        except Exception as e:
            print(f"[AUDIO] Erro na transcrição: {e}")
            return None

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        if not message.attachments:
            return

        attachment = message.attachments[0]
        content_type = attachment.content_type or ""
        if not content_type.startswith("audio/"):
            # Verifica também pela extensão do ficheiro
            if not attachment.filename.lower().endswith((".ogg", ".mp3", ".wav", ".mp4", ".m4a", ".webm", ".flac")):
                return

        print(f"[AUDIO] Mensagem de voz detectada: {attachment.filename} ({attachment.size} bytes, tipo: {content_type})")

        # Limite de tamanho (10 MB)
        if attachment.size > 10 * 1024 * 1024:
            await message.channel.send("❌ O áudio é muito grande para transcrição.", delete_after=10)
            return

        # Baixar o áudio
        try:
            audio_bytes = await attachment.read()
            print(f"[AUDIO] Áudio baixado: {len(audio_bytes)} bytes")
        except Exception as e:
            print(f"[AUDIO] Erro ao baixar áudio: {e}")
            return

        # Transcrever
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
            print(f"[AUDIO] Mensagem de voz transcrita e republicada para {message.author.display_name}.")
        except Exception as e:
            print(f"[AUDIO] Erro ao republicar transcrição: {e}")

async def setup(bot: commands.Bot):
    await bot.add_cog(Audio(bot))
