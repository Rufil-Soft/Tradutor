import os
import json
import asyncio
import discord
from discord.ext import commands
from deep_translator import GoogleTranslator

# Configuração de Intents
intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# Ficheiro para guardar as configurações dos canais
CONFIG_FILE = "channels_config.json"

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    return {}

def save_config(config):
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=4)

active_channels = load_config()
DEFAULT_TARGET = os.getenv("DEFAULT_TARGET", "pt")

@bot.event
async def on_ready():
    print(f"Bot tradutor ligado como {bot.user}")

@bot.command(name="enable")
async def enable_translation(ctx, target_lang: str = DEFAULT_TARGET):
    """Ativa a tradução automática no canal atual. Ex: !enable pt ou !enable en"""
    active_channels[str(ctx.channel.id)] = target_lang.lower()
    save_config(active_channels)
    await ctx.send(f"✅ Tradução automática ativada neste canal para o idioma **{target_lang.upper()}**!")

@bot.command(name="disable")
async def disable_translation(ctx):
    """Desativa a tradução automática no canal atual."""
    channel_id = str(ctx.channel.id)
    if channel_id in active_channels:
        del active_channels[channel_id]
        save_config(active_channels)
        await ctx.send("❌ Tradução automática desativada neste canal.")
    else:
        await ctx.send("A tradução automática já não estava ativa neste canal.")

@bot.event
async def on_message(message):
    # Ignora mensagens de outros bots ou do próprio bot
    if message.author.bot:
        return

    # Processa comandos (!enable, !disable) antes de tentar traduzir
    await bot.process_commands(message)

    channel_id = str(message.channel.id)
    
    # Se o canal estiver na lista de canais ativos
    if channel_id in active_channels and message.content:
        # Se for uma mensagem de comando (começa com !), ignora a tradução
        if message.content.startswith(bot.command_prefix):
            return

        target_lang = active_channels[channel_id]

        try:
            # Executa a tradução sem travar o bot
            translated = await asyncio.to_thread(
                GoogleTranslator(source='auto', target=target_lang).translate,
                message.content
            )

            # Só responde se a tradução for diferente do texto original
            if translated and translated.strip().lower() != message.content.strip().lower():
                await message.reply(f"🔠 **Tradução ({target_lang.upper()}):** {translated}", mention_author=False)

        except Exception as e:
            print(f"Erro ao traduzir mensagem: {e}")

# Inicia o bot
token = os.getenv("DISCORD_TOKEN")
if token:
    bot.run(token)
else:
    print("ERRO: A variável DISCORD_TOKEN não foi encontrada!")
