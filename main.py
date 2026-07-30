import os
import asyncio
import discord
from discord.ext import commands
from deep_translator import GoogleTranslator

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# Classe do Botão Interativo com as setas opostas ⇄
class TranslateView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None) # O botão continua ativo mesmo após reiniciar

    @discord.ui.button(label="Traduzir", style=discord.ButtonStyle.secondary, emoji="⇄", custom_id="translate_button")
    async def translate_button_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Pega a mensagem original
        message_text = interaction.message.content

        if not message_text:
            await interaction.response.send_message("Não há texto para traduzir nesta mensagem.", ephemeral=True)
            return

        # Pega o idioma do cliente Discord da pessoa que clicou (ex: 'pt-PT' vira 'pt')
        user_locale = str(interaction.locale).split("-")[0]

        try:
            # Traduz para o idioma do utilizador
            translated = await asyncio.to_thread(
                GoogleTranslator(source='auto', target=user_locale).translate,
                message_text
            )

            # Responde APENAS para a pessoa que clicou (mensagem invisível para os outros)
            await interaction.response.send_message(
                f"🔠 **Tradução ({user_locale.upper()}):**\n{translated}", 
                ephemeral=True
            )
        except Exception as e:
            print(f"Erro ao traduzir: {e}")
            await interaction.response.send_message("Ocorreu um erro ao tentar traduzir esta mensagem.", ephemeral=True)

@bot.event
async def on_ready():
    bot.add_view(TranslateView())
    print(f"Bot tradutor interativo ligado como {bot.user}")

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    await bot.process_commands(message)

    # Quando alguém envia mensagem, o bot substitui a mensagem anexando o botão ⇄
    if message.content and not message.content.startswith(bot.command_prefix):
        await message.channel.send(content=f"**{message.author.display_name}**: {message.content}", view=TranslateView())
        try:
            await message.delete()
        except Exception:
            pass

token = os.getenv("DISCORD_TOKEN")
if token:
    bot.run(token)
else:
    print("ERRO: A variável DISCORD_TOKEN não foi encontrada!")
