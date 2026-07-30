import os
import asyncio
from bot import bot
from servidor_dummy import start_dummy_server

async def load_extensions():
    extensions = [
        "cogs.traducao",
        "cogs.votacoes",
        "cogs.paineis",
        "cogs.comandos_setup",
    ]
    for ext in extensions:
        await bot.load_extension(ext)

@bot.event
async def on_ready():
    print(f"Bot ligado como {bot.user}")
    await start_dummy_server()

async def main():
    await load_extensions()
    token = os.getenv("DISCORD_TOKEN")
    if token:
        await bot.start(token)

asyncio.run(main())
