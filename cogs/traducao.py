import asyncio
import discord
from discord.ext import commands
from deep_translator import GoogleTranslator

translation_cache = {}

class TranslateView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(style=discord.ButtonStyle.secondary, emoji="🌍", custom_id="persistent_translate_button")
    async def translate_button_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)

        message = interaction.message
        # Extrai o texto do embed da mensagem
        if message.embeds:
            message_text = message.embeds[0].description
        else:
            message_text = message.content

        if not message_text:
            await interaction.followup.send("Não há texto para traduzir.", ephemeral=True)
            return

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
            f"🌍 **Tradução ({user_locale.upper()}):**\n{translated}",
            ephemeral=True
        )


class Traducao(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        print("[TRADUÇÃO] Cog carregado com suporte a cor de role ativo.")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.content:
            return
        if message.content.startswith(self.bot.command_prefix):
            return
        if message.channel.name == "🎯-capos-message":
            return

        try:
            # Cria um embed que herda a cor do cargo (role) do utilizador
            embed = discord.Embed(
                description=message.content,
                color=message.author.color if message.author.color.value != 0 else discord.Color.default()
            )
            embed.set_author(
                name=message.author.display_name,
                icon_url=message.author.display_avatar.url if message.author.display_avatar else None
            )

            files = [await a.to_file() for a in message.attachments]

            await message.delete()
            await message.channel.send(
                embed=embed,
                files=files,
                view=TranslateView()
            )
        except discord.Forbidden:
            pass
        except Exception as e:
            print(f"[TRADUÇÃO] Erro ao processar mensagem com cor de role: {e}")


async def setup(bot: commands.Bot):
    await bot.add_cog(Traducao(bot))
