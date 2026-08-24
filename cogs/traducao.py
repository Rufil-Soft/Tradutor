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
mensagens_processadas = {}
PROCESS_EXPIRY = 60

def registar_mensagem(message_id: int, base: str, original: str):
    mensagens_dados[message_id] = {
        "base": base,
        "original": original,
        "traducoes": {},
        "ordem_insercao": []
    }

def detectar_idioma(texto: str) -> str:
    try:
        return detect(texto)
    except LangDetectException:
        return "en"

# Padrões que indicam que o "texto traduzido" é, na verdade, uma mensagem de
# erro devolvida pela API (Google ou MyMemory) e não deve ser mostrada ao
# utilizador como se fosse uma tradução válida.
_PADROES_ERRO = (
    "error",
    "erro",
    "invalid source language",
    "invalid target language",
    "no support for",
    "please select on",
    "query length limit",
    "must translate",
    "amount of translation",
    "is an invalid",
)

def e_traducao_valida(texto: str) -> bool:
    """Verifica se o texto não é uma página/mensagem de erro da API de tradução."""
    if not texto:
        return False
    t = texto.strip().lower()
    if not t:
        return False
    return not any(padrao in t for padrao in _PADROES_ERRO)

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

        locale_str = str(interaction.locale or "pt-PT")
        user_locale_short = locale_str.split("-")[0].lower()
        user_locale_full = locale_str

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

                    # Deteta o idioma de origem uma única vez — é reutilizado
                    # pelo MyMemory, que (ao contrário do Google) não aceita 'auto'.
                    source_lang = None

                    # 1ª tentativa: Google
                    try:
                        translated = await asyncio.to_thread(
                            GoogleTranslator(source='auto', target=user_locale_short).translate,
                            dados["original"]
                        )
                        print(f"[TRADUTOR] Google retornou: {translated!r}")
                        if not e_traducao_valida(translated):
                            print("[TRADUTOR] Google devolveu erro, a tentar MyMemory...")
                            translated = None
                    except Exception as e:
                        print(f"[TRADUTOR] Google falhou: {e}")
                        translated = None

                    # 2ª tentativa: MyMemory (precisa de um código de idioma real, não 'auto')
                    if not translated:
                        try:
                            source_lang = detectar_idioma(dados["original"])
                            translated = await asyncio.to_thread(
                                MyMemoryTranslator(source=source_lang, target=user_locale_full).translate,
                                dados["original"]
                            )
                            print(f"[TRADUTOR] MyMemory retornou: {translated!r}")
                            if not e_traducao_valida(translated):
                                print("[TRADUTOR] MyMemory devolveu erro, a tentar Google novamente...")
                                translated = None
                        except Exception as e:
                            print(f"[TRADUTOR] MyMemory falhou: {e}")
                            translated = None

                    # 3ª tentativa: Google (retry)
                    if not translated:
                        try:
                            translated = await asyncio.to_thread(
                                GoogleTranslator(source='auto', target=user_locale_short).translate,
                                dados["original"]
                            )
                            print(f"[TRADUTOR] Google (retry) retornou: {translated!r}")
                            if not e_traducao_valida(translated):
                                translated = None
                        except Exception as e:
                            print(f"[TRADUTOR] Google (retry) falhou: {e}")
                            translated = None

                    # 4ª tentativa: MyMemory (retry), caso o idioma detetado à primeira
                    # tenha sido a causa da falha (raro, mas mais barato que desistir).
                    if not translated:
                        try:
                            if source_lang is None:
                                source_lang = detectar_idioma(dados["original"])
                            translated = await asyncio.to_thread(
                                MyMemoryTranslator(source=source_lang, target=user_locale_full).translate,
                                dados["original"]
                            )
                            print(f"[TRADUTOR] MyMemory (retry) retornou: {translated!r}")
                            if not e_traducao_valida(translated):
                                translated = None
                        except Exception as e:
                            print(f"[TRADUTOR] MyMemory (retry) falhou: {e}")
                            translated = None

                    if translated and e_traducao_valida(translated):
                        translation_cache[cache_key] = translated
                    else:
                        translated = None

                if not translated:
                    try:
                        await interaction.followup.send(
                            "❌ Não consegui traduzir agora. Tenta novamente mais tarde.",
                            ephemeral=True
                        )
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
        print("[TRADUÇÃO] Cog carregado — com validação robusta de erros de tradução e fix MyMemory 'auto'.")

    async def apagar_com_retry(self, message: discord.Message, tentativas: int = 3) -> bool:
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
        if message.author.bot or not message.content:
            return
        if message.attachments:
            return
        if message.content.startswith(self.bot.command_prefix):
            return
        if message.channel.name == "🎯-capos-message":
            return
        if self.bot.user in message.mentions:
            return

        agora = time.time()
        ultimo = mensagens_processadas.get(message.id)
        if ultimo and (agora - ultimo) < PROCESS_EXPIRY:
            return
        mensagens_processadas[message.id] = agora

        conteudo_formatado = f"<@{message.author.id}>: {message.content}"
        texto_original = message.content

        try:
            msg_enviada = await message.channel.send(
                content=conteudo_formatado,
                view=TranslateView(),
                allowed_mentions=discord.AllowedMentions(users=False)
            )
        except Exception as e:
            print(f"[TRADUÇÃO] Erro ao enviar republicação: {e}")
            mensagens_processadas.pop(message.id, None)
            return

        sucesso = await self.apagar_com_retry(message)
        if not sucesso:
            try:
                await msg_enviada.delete()
            except Exception as e:
                print(f"[TRADUÇÃO] Erro ao apagar republicação: {e}")
            mensagens_processadas.pop(message.id, None)
            return

        registar_mensagem(msg_enviada.id, conteudo_formatado, texto_original)

        if len(mensagens_processadas) > 1000:
            chaves_expirar = [k for k, v in mensagens_processadas.items() if v < agora - PROCESS_EXPIRY * 2]
            for k in chaves_expirar:
                mensagens_processadas.pop(k, None)

async def setup(bot: commands.Bot):
    bot.add_view(TranslateView())
    await bot.add_cog(Traducao(bot))
