import asyncio
import discord
from discord.ext import commands
from deep_translator import GoogleTranslator

translation_cache = {}  # (texto, idioma) -> texto traduzido

# Estado por mensagem: message_id -> {"base": str, "original": str, "traducoes": {idioma: texto}}
mensagens_dados = {}
mensagens_locks = {}  # message_id -> asyncio.Lock()


class TranslateView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(style=discord.ButtonStyle.secondary, emoji="🌍", custom_id="persistent_translate_button")
    async def translate_button_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        message = interaction.message
        dados = mensagens_dados.get(message.id)

        # Fallback para mensagens enviadas antes de o bot reiniciar (sem registo em memória)
        if not dados:
            texto_atual = message.content
            if ":" in texto_atual:
                texto_original = texto_atual.split(":", 1)[1].strip()
            else:
                texto_original = texto_atual
            dados = {"base": texto_atual, "original": texto_original, "traducoes": {}}
            mensagens_dados[message.id] = dados

        if not dados["original"]:
            await interaction.response.send_message("Não há texto para traduzir.", ephemeral=True)
            return

        user_locale = (str(interaction.locale).split("-")[0] or "pt")[:2]

        lock = mensagens_locks.setdefault(message.id, asyncio.Lock())
        async with lock:
            # Já traduzido para este idioma -> já está visível na mensagem, só reconhece a interação
            if user_locale in dados["traducoes"]:
                await interaction.response.defer()
                return

            await interaction.response.defer()  # ack rápido, sem mensagem extra visível

            cache_key = (dados["original"], user_locale)
            if cache_key in translation_cache:
                translated = translation_cache[cache_key]
            else:
                try:
                    translated = await asyncio.to_thread(
                        GoogleTranslator(source='auto', target=user_locale).translate,
                        dados["original"]
                    )
                except Exception as e:
                    print(f"[TRADUTOR] Erro na tradução: {e}")
                    translated = None
                if translated:
                    translation_cache[cache_key] = translated

            if not translated:
                return  # falha silenciosa; a mensagem fica como estava

            dados["traducoes"][user_locale] = translated
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
        print("[TRADUÇÃO] Cog carregado — traduções acumuladas na própria mensagem.")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.content:
            return
        if message.content.startswith(self.bot.command_prefix):
            return
        if message.channel.name == "🎯-capos-message":
            return
        # Ignorar mensagens que mencionam o Aquiles (tratado pelo frases.py)
        if self.bot.user in message.mentions:
            return
        try:
            conteudo_formatado = f"<@{message.author.id}>: {message.content}"
            texto_original = message.content
            files = [await a.to_file() for a in message.attachments]
            await message.delete()
            msg_enviada = await message.channel.send(
                content=conteudo_formatado,
                files=files,
                view=TranslateView(),
                allowed_mentions=discord.AllowedMentions(users=False)
            )
            mensagens_dados[msg_enviada.id] = {
                "base": conteudo_formatado,
                "original": texto_original,
                "traducoes": {}
            }
        except discord.Forbidden:
            pass
        except Exception as e:
            print(f"[TRADUÇÃO] Erro ao processar mensagem limpa: {e}")


async def setup(bot: commands.Bot):
    bot.add_view(TranslateView())
    await bot.add_cog(Traducao(bot))
