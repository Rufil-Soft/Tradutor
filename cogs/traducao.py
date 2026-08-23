import asyncio
import time
import discord
from discord.ext import commands
from deep_translator import GoogleTranslator, MyMemoryTranslator
from langdetect import detect, LangDetectException

translation_cache = {}
mensagens_dados = {}
mensagens_locks = {}
MAX_VISIVEIS = 4
mensagens_processadas = {}  # {message_id: timestamp}
PROCESS_EXPIRY = 60  # segundos para considerar a mensagem já processada

def registar_mensagem(message_id: int, base: str, original: str):
    mensagens_dados[message_id] = {
        "base": base,
        "original": original,
        "traducoes": {},
        "ordem_insercao": []
    }

def detectar_idioma(texto: str) -> str:
    """Deteta o idioma do texto e devolve o código ISO (ex: 'en', 'pt', 'es')."""
    try:
        return detect(texto)
    except LangDetectException:
        return "en"

class TranslateView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(style=discord.ButtonStyle.secondary, emoji="🌍", custom_id="persistent_translate_button")
    async def translate_button_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        message = interaction.message
        dados = mensagens_dados.get(message.id)

        if not dados:
            texto_atual = message.content
            dados = {"base": texto_atual, "original": texto_atual, "traducoes": {}, "ordem_insercao": []}
            mensagens_dados[message.id] = dados

        if not dados["original"]:
            await interaction.response.send_message("Não há texto para traduzir.", ephemeral=True)
            return

        user_locale_short = (str(interaction.locale).split("-")[0] or "pt")[:2]
        user_locale_full = str(interaction.locale) or "pt-PT"

        lock = mensagens_locks.setdefault(message.id, asyncio.Lock())
        async with lock:
            if user_locale_short in dados["traducoes"]:
                if user_locale_short in dados["ordem_insercao"]:
                    dados["ordem_insercao"].remove(user_locale_short)
                dados["ordem_insercao"].append(user_locale_short)
                await interaction.response.defer()
            else:
                await interaction.response.defer()

                cache_key = (dados["original"], user_locale_short)
                if cache_key in translation_cache:
                    translated = translation_cache[cache_key]
                else:
                    translated = None
                    try:
                        translated = await asyncio.to_thread(
                            GoogleTranslator(source='auto', target=user_locale_short).translate,
                            dados["original"]
                        )
                    except Exception:
                        translated = None

                    if translated and ("Error" in translated or "error" in translated.lower()):
                        await asyncio.sleep(1)
                        try:
                            translated = await asyncio.to_thread(
                                GoogleTranslator(source='auto', target=user_locale_short).translate,
                                dados["original"]
                            )
                        except Exception:
                            translated = None

                    if not translated or "Error" in translated or "error" in translated.lower():
                        print("[TRADUTOR] Google indisponível, a usar MyMemory...")
                        try:
                            source_lang = detectar_idioma(dados["original"])
                            translated = await asyncio.to_thread(
                                MyMemoryTranslator(source=source_lang, target=user_locale_full).translate,
                                dados["original"]
                            )
                        except Exception as e:
                            print(f"[TRADUTOR] MyMemory falhou: {e}")
                            translated = None

                    if translated and ("Error" in translated or "error" in translated.lower()):
                        translated = None

                    if translated:
                        translation_cache[cache_key] = translated

                if not translated:
                    try:
                        await interaction.followup.send("Erro ao traduzir. Tenta novamente.", ephemeral=True)
                    except discord.HTTPException:
                        pass
                    return

                dados["traducoes"][user_locale_short] = translated
                dados["ordem_insercao"].append(user_locale_short)

            while len(dados["ordem_insercao"]) > MAX_VISIVEIS:
                dados["ordem_insercao"].pop(0)

            linhas_traducao = "\n".join(
                f"🌍 {lang.upper()}: {dados['traducoes'][lang]}" for lang in dados["ordem_insercao"]
            )
            novo_conteudo = f"{dados['base']}\n{linhas_traducao}"
            try:
                await message.edit(content=novo_conteudo)
            except discord.HTTPException as e:
                print(f"[TRADUTOR] Erro ao editar mensagem: {e}")

class Traducao(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.delete_lock = asyncio.Lock()
        print("[TRADUÇÃO] Cog carregado — com fallback MyMemory, retry Google e anti-duplicação.")

    async def apagar_com_retry(self, message: discord.Message, tentativas: int = 3) -> bool:
        """Tenta apagar a mensagem com backoff em caso de rate limit."""
        async with self.delete_lock:
            for i in range(tentativas):
                try:
                    await message.delete()
                    return True
                except discord.HTTPException as e:
                    if e.status == 429 and i < tentativas - 1:
                        retry_after = getattr(e, 'retry_after', 1.0)
                        print(f"[TRADUÇÃO] Rate limit ao apagar {message.id}, retry em {retry_after:.2f}s")
                        await asyncio.sleep(retry_after + 0.5)
                        continue
                    else:
                        print(f"[TRADUÇÃO] Falha ao apagar mensagem {message.id}: {e}")
                        return False
                except discord.Forbidden:
                    print(f"[TRADUÇÃO] Sem permissão para apagar {message.id}")
                    return False
            return False

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # Ignorar bots e mensagens vazias
        if message.author.bot or not message.content:
            return

        # Ignorar anexos (áudio, imagens, etc.)
        if message.attachments:
            return

        # Ignorar comandos
        if message.content.startswith(self.bot.command_prefix):
            return

        # Ignorar canal específico
        if message.channel.name == "🎯-capos-message":
            return

        # Ignorar menções ao bot (para não conflituar com frases.py)
        if self.bot.user in message.mentions:
            return

        # Proteção contra processamento duplicado da mesma mensagem
        agora = time.time()
        ultimo = mensagens_processadas.get(message.id)
        if ultimo and (agora - ultimo) < PROCESS_EXPIRY:
            print(f"[TRADUÇÃO] Mensagem {message.id} já processada recentemente, ignorando.")
            return
        mensagens_processadas[message.id] = agora

        conteudo_formatado = f"<@{message.author.id}>: {message.content}"
        texto_original = message.content

        # 1º envia a republicação
        try:
            msg_enviada = await message.channel.send(
                content=conteudo_formatado,
                view=TranslateView(),
                allowed_mentions=discord.AllowedMentions(users=False)
            )
            print(f"[TRADUÇÃO] Republicação enviada (ID: {msg_enviada.id})")
        except Exception as e:
            print(f"[TRADUÇÃO] Erro ao enviar republicação: {e}")
            mensagens_processadas.pop(message.id, None)
            return

        # 2º tenta apagar a original
        sucesso = await self.apagar_com_retry(message)
        if not sucesso:
            print(f"[TRADUÇÃO] Não consegui apagar a original {message.id}, apagando a republicação {msg_enviada.id}")
            try:
                await msg_enviada.delete()
            except Exception as e:
                print(f"[TRADUÇÃO] Erro ao apagar republicação {msg_enviada.id}: {e}")
            mensagens_processadas.pop(message.id, None)
            return

        # Sucesso: regista a republicação no dicionário de traduções
        registar_mensagem(msg_enviada.id, conteudo_formatado, texto_original)

        # Limpeza periódica do cache de processadas
        if len(mensagens_processadas) > 1000:
            limite = agora - PROCESS_EXPIRY * 2
            mensagens_processadas = {k: v for k, v in mensagens_processadas.items() if v > limite}

async def setup(bot: commands.Bot):
    bot.add_view(TranslateView())
    await bot.add_cog(Traducao(bot))
