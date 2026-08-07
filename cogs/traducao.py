import asyncio
import discord
from discord.ext import commands
from deep_translator import GoogleTranslator

translation_cache = {}
mensagens_dados = {}
mensagens_locks = {}

MAX_TRADUCOES_VISIVEIS = 4  # limite de traduções mostradas na mensagem

def registar_mensagem(message_id: int, base: str, original: str):
    mensagens_dados[message_id] = {"base": base, "original": original, "traducoes": {}}

class TranslateView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(style=discord.ButtonStyle.secondary, emoji="🌍", custom_id="persistent_translate_button")
    async def translate_button_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        message = interaction.message
        dados = mensagens_dados.get(message.id)

        if not dados:
            texto_atual = message.content
            # fallback simples
            dados = {"base": texto_atual, "original": texto_atual, "traducoes": {}}
            mensagens_dados[message.id] = dados

        if not dados["original"]:
            await interaction.response.send_message("Não há texto para traduzir.", ephemeral=True)
            return

        user_locale = (str(interaction.locale).split("-")[0] or "pt")[:2]

        lock = mensagens_locks.setdefault(message.id, asyncio.Lock())
        async with lock:
            if user_locale in dados["traducoes"]:
                await interaction.response.defer()
                return

            await interaction.response.defer()

            cache_key = (dados["original"], user_locale)
            if cache_key in translation_cache:
                translated = translation_cache[cache_key]
            else:
                try:
                    translated = await asyncio.to_thread(
                        GoogleTranslator(source='auto', target=user_locale).translate,
                        dados["original"]
                    )
                    if translated:
                        translation_cache[cache_key] = translated
                except Exception as e:
                    print(f"[TRADUTOR] Erro na tradução: {e}")
                    translated = None

            if not translated:
                try:
                    await interaction.followup.send("Erro ao traduzir. Tenta novamente.", ephemeral=True)
                except discord.HTTPException:
                    pass
                return

            dados["traducoes"][user_locale] = translated

            # Manter apenas as últimas MAX_TRADUCOES_VISIVEIS (remover as mais antigas)
            while len(dados["traducoes"]) > MAX_TRADUCOES_VISIVEIS:
                oldest_key = next(iter(dados["traducoes"]))
                del dados["traducoes"][oldest_key]

            linhas_traducao = "\n".join(
                f"🌍 {lang.upper()}: {txt}" for lang, txt in dados["traducoes"].items()
            )
            novo_conteudo = f"{dados['base']}\n{linhas_traducao}"
            try:
                await message.edit(content=novo_conteudo)
            except discord.HTTPException as e:
                print(f"[TRADUTOR] Erro ao editar mensagem: {e}")


class Traducao(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        print("[TRADUÇÃO] Cog carregado — traduções limitadas a 3 por mensagem.")

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

            # Tenta apagar a mensagem original
            await message.delete()
            # Pequeno atraso para o Discord processar a eliminação
            await asyncio.sleep(0.3)

            msg_enviada = await message.channel.send(
                content=conteudo_formatado,
                files=files,
                view=TranslateView(),
                allowed_mentions=discord.AllowedMentions(users=False)
            )
            registar_mensagem(msg_enviada.id, conteudo_formatado, texto_original)
        except discord.Forbidden:
            # Se não pode apagar, não faz nada para evitar duplicação
            pass
        except Exception as e:
            print(f"[TRADUÇÃO] Erro ao processar mensagem limpa: {e}")


async def setup(bot: commands.Bot):
    bot.add_view(TranslateView())
    await bot.add_cog(Traducao(bot))
