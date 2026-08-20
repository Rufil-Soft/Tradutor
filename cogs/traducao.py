import asyncio
import discord
from discord.ext import commands
from deep_translator import GoogleTranslator, MyMemoryTranslator
from langdetect import detect, LangDetectException

translation_cache = {}
mensagens_dados = {}
mensagens_locks = {}
MAX_VISIVEIS = 4  # número máximo de traduções visíveis na mensagem

def registar_mensagem(message_id: int, base: str, original: str):
    mensagens_dados[message_id] = {
        "base": base,
        "original": original,
        "traducoes": {},         # {idioma: texto}
        "ordem_insercao": []     # lista de idiomas por ordem de clique (último no fim)
    }


def detectar_idioma(texto: str) -> str:
    """Deteta o idioma do texto e devolve o código ISO (ex: 'en', 'pt', 'es')."""
    try:
        return detect(texto)
    except LangDetectException:
        return "en"  # fallback para inglês


class TranslateView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(style=discord.ButtonStyle.secondary, emoji="🌍", custom_id="persistent_translate_button")
    async def translate_button_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        message = interaction.message
        dados = mensagens_dados.get(message.id)

        # Fallback para mensagens sem registo
        if not dados:
            texto_atual = message.content
            dados = {"base": texto_atual, "original": texto_atual, "traducoes": {}, "ordem_insercao": []}
            mensagens_dados[message.id] = dados

        if not dados["original"]:
            await interaction.response.send_message("Não há texto para traduzir.", ephemeral=True)
            return

        # Código de idioma de duas letras (para Google)
        user_locale_short = (str(interaction.locale).split("-")[0] or "pt")[:2]
        # Código completo com região (para MyMemory)
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
                    # 1ª tentativa: Google
                    translated = None
                    try:
                        translated = await asyncio.to_thread(
                            GoogleTranslator(source='auto', target=user_locale_short).translate,
                            dados["original"]
                        )
                    except Exception:
                        translated = None

                    # Se veio com erro, tentar novamente Google
                    if translated and ("Error" in translated or "error" in translated.lower()):
                        await asyncio.sleep(1)
                        try:
                            translated = await asyncio.to_thread(
                                GoogleTranslator(source='auto', target=user_locale_short).translate,
                                dados["original"]
                            )
                        except Exception:
                            translated = None

                    # Fallback para MyMemory com código completo e origem detetada
                    if not translated or "Error" in translated or "error" in translated.lower():
                        print("[TRADUTOR] Google indisponível, a usar MyMemory...")
                        try:
                            source_lang = detectar_idioma(dados["original"])
                            # MyMemory não aceita 'auto', portanto usamos o idioma detetado
                            translated = await asyncio.to_thread(
                                MyMemoryTranslator(source=source_lang, target=user_locale_full).translate,
                                dados["original"]
                            )
                        except Exception as e:
                            print(f"[TRADUTOR] MyMemory falhou: {e}")
                            translated = None

                    # Validação final
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
        print("[TRADUÇÃO] Cog carregado — com fallback MyMemory e retry Google.")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.content:
            return
        if message.content.startswith(self.bot.command_prefix):
            return
        if message.channel.name == "🎯-capos-message":
            return
        if self.bot.user in message.mentions:
            return

        try:
            conteudo_formatado = f"<@{message.author.id}>: {message.content}"
            texto_original = message.content
            files = [await a.to_file() for a in message.attachments]

            await message.delete()
            await asyncio.sleep(0.3)

            msg_enviada = await message.channel.send(
                content=conteudo_formatado,
                files=files,
                view=TranslateView(),
                allowed_mentions=discord.AllowedMentions(users=False)
            )
            registar_mensagem(msg_enviada.id, conteudo_formatado, texto_original)
        except discord.Forbidden:
            pass
        except Exception as e:
            print(f"[TRADUÇÃO] Erro ao processar mensagem limpa: {e}")


async def setup(bot: commands.Bot):
    bot.add_view(TranslateView())
    await bot.add_cog(Traducao(bot))
