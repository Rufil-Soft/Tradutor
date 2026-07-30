import asyncio
import discord
from discord.ext import commands
from deep_translator import GoogleTranslator
from bot import bot

translation_cache = {}

class TranslateView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Traduzir", style=discord.ButtonStyle.secondary, emoji="🌐", custom_id="translate_button")
    async def translate_button_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)

        message_text = interaction.message.content
        if not message_text:
            await interaction.followup.send("Não há texto para traduzir.", ephemeral=True)
            return

        if ":" in message_text:
            texto_para_traduzir = message_text.split(":", 1)[1].strip()
        else:
            texto_para_traduzir = message_text

        user_locale = (str(interaction.locale).split("-")[0] or "pt")[:2]

        cache_key = (texto_para_traduzir, user_locale)
        if cache_key in translation_cache:
            translated = translation_cache[cache_key]
        else:
            try:
                translated = await asyncio.to_thread(
                    GoogleTranslator(source='auto', target=user_locale).translate,
                    texto_para_traduzir
                )
                if translated:
                    translation_cache[cache_key] = translated
            except Exception as e:
                print(f"[TRADUTOR] Erro na tradução: {e}")
                await interaction.followup.send("Erro ao traduzir. Tenta novamente.", ephemeral=True)
                return

        if not translated:
            await interaction.followup.send("Não foi possível traduzir o texto.", ephemeral=True)
            return

        await interaction.followup.send(
            f"🔠 **Tradução ({user_locale.upper()}):**\n{translated}",
            ephemeral=True
        )


class Traducao(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        print("[TRADUÇÃO] Cog carregado. Sistema de botões ativo.")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.content:
            return
        if message.content.startswith(bot.command_prefix):
            return
        if message.channel.name == "🎯-capos-message":
            return

        try:
            await message.channel.send(
                content=f"**{message.author.display_name}**: {message.content}",
                view=TranslateView()
            )
            await message.delete()
        except discord.Forbidden:
            pass
        except Exception as e:
            print(f"[TRADUÇÃO] Erro ao processar mensagem: {e}")


async def setup(bot: commands.Bot):
    await bot.add_cog(Traducao(bot))
