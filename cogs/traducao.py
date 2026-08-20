import asyncio
import discord
from discord.ext import commands
from deep_translator import GoogleTranslator, MyMemoryTranslator

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

        user_locale = (str(interaction.locale).split("-")[0] or "pt")[:2]

        lock = mensagens_locks.setdefault(message.id, asyncio.Lock())
        async with lock:
            # Se já existir, apenas move para o fim da ordem
            if user_locale in dados["traducoes"]:
                if user_locale in dados["ordem_insercao"]:
                    dados["ordem_insercao"].remove(user_locale)
                dados["ordem_insercao"].append(user_locale)
                await interaction.response.defer()
            else:
                await interaction.response.defer()

                cache_key = (dados["original"], user_locale)
                if cache_key in translation_cache:
                    translated = translation_cache[cache_key]
                else:
                    # --- Tenta Google, com retry e fallback para MyMemory ---
                    translated = None

                    # 1ª tentativa: Google
                    try:
                        translated = await asyncio.to_thread(
                            GoogleTranslator(source='auto', target=user_locale).translate,
                            dados["original"]
                        )
                    except Exception:
                        translated = None

                    # Se veio com erro, tenta uma 2ª vez após 1s
                    if translated and ("Error" in translated or "error" in translated.lower()):
                        print(f"[TRADUTOR] Google devolveu erro, tentando novamente...")
                        await asyncio.sleep(1)
                        try:
                            translated = await asyncio.to_thread(
                                GoogleTranslator(source='auto', target=user_locale).translate,
                                dados["original"]
                            )
                        except Exception:
                            translated = None

                    # Fallback para MyMemory se Google falhar
                    if not translated or "Error" in translated or "error" in translated.lower():
                        print("[TRADUTOR] Google indisponível, a usar MyMemory...")
                        try:
                            translated = await asyncio.to_thread(
                                MyMemoryTranslator(source='auto', target=user_locale).translate,
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

                dados["traducoes"][user_locale] = translated
                dados["ordem_insercao"].append(user_locale)

            # Limita número de traduções visíveis
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
