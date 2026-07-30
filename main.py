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
    # As views persistentes são registadas automaticamente porque os cogs já as criam.
    # Mas se quiseres garantir, podes adicionar bot.add_view(...) aqui com as instâncias.
    print(f"Bot ligado como {bot.user}")
    await start_dummy_server()

async def main():
    await load_extensions()
    token = os.getenv("DISCORD_TOKEN")
    if token:
        await bot.start(token)

asyncio.run(main())
