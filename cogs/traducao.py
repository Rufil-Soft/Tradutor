import asyncio
import discord
from discord.ext import commands
from deep_translator import GoogleTranslator

translation_cache = {}

# Tempo máximo (segundos) que esperamos pela tradução antes de responder sem defer.
# Tem de ficar claramente abaixo dos 3s que o Discord dá para reconhecer a interação.
TRADUCAO_TIMEOUT_RAPIDO = 2.2


class TranslateView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(style=discord.ButtonStyle.secondary, emoji="🌍", custom_id="persistent_translate_button")
    async def translate_button_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        message = interaction.message
        message_text = message.content
        if not message_text:
            await interaction.response.send_message("Não há texto para traduzir.", ephemeral=True)
            return

        # Extrai o texto real removendo a menção inicial (ex: "<@123456>: Olá" -> "Olá")
        if ":" in message_text:
            partes = message_text.split(":", 1)
            texto_para_traduzir = partes[1].strip() if len(partes) > 1 else message_text
        else:
            texto_para_traduzir = message_text

        user_locale = (str(interaction.locale).split("-")[0] or "pt")[:2]
        cache_key = (texto_para_traduzir, user_locale)

        # Já em cache -> resposta instantânea, SEM defer, fica colada à mensagem original.
        if cache_key in translation_cache:
            await interaction.response.send_message(f"🌍: {translation_cache[cache_key]}", ephemeral=True)
            return

        try:
            # Tenta traduzir dentro da janela dos 3s do Discord, para poder responder sem defer.
            translated = await asyncio.wait_for(
                asyncio.to_thread(
                    GoogleTranslator(source='auto', target=user_locale).translate,
                    texto_para_traduzir
                ),
                timeout=TRADUCAO_TIMEOUT_RAPIDO
            )
            if not translated:
                await interaction.response.send_message("Não foi possível traduzir o texto.", ephemeral=True)
                return
            translation_cache[cache_key] = translated
            # Resposta direta (sem defer) -> fica ancorada à mensagem/botão clicado.
            await interaction.response.send_message(f"🌍: {translated}", ephemeral=True)

        except asyncio.TimeoutError:
            # Demorou demasiado para caber nos 3s -> defer como rede de segurança.
            # Perde-se o posicionamento colado à mensagem, mas evita que a interação falhe.
            await interaction.response.defer(ephemeral=True)
            try:
                translated = await asyncio.to_thread(
                    GoogleTranslator(source='auto', target=user_locale).translate,
                    texto_para_traduzir
                )
                if not translated:
                    await interaction.followup.send("Não foi possível traduzir o texto.", ephemeral=True)
                    return
                translation_cache[cache_key] = translated
                await interaction.followup.send(f"🌍: {translated}", ephemeral=True)
            except Exception as e:
                print(f"[TRADUTOR] Erro na tradução (fallback): {e}")
                await interaction.followup.send("Erro ao traduzir. Tenta novamente.", ephemeral=True)

        except Exception as e:
            print(f"[TRADUTOR] Erro na tradução: {e}")
            try:
                await interaction.response.send_message("Erro ao traduzir. Tenta novamente.", ephemeral=True)
            except discord.InteractionResponded:
                await interaction.followup.send("Erro ao traduzir. Tenta novamente.", ephemeral=True)


class Traducao(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        print("[TRADUÇÃO] Cog carregado com resposta direta (sem defer) ancorada à mensagem.")

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
            files = [await a.to_file() for a in message.attachments]
            await message.delete()
            await message.channel.send(
                content=conteudo_formatado,
                files=files,
                view=TranslateView(),
                allowed_mentions=discord.AllowedMentions(users=False)
            )
        except discord.Forbidden:
            pass
        except Exception as e:
            print(f"[TRADUÇÃO] Erro ao processar mensagem limpa: {e}")


async def setup(bot: commands.Bot):
    bot.add_view(TranslateView())
    await bot.add_cog(Traducao(bot))
