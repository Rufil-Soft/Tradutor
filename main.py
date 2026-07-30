import os
import asyncio
import traceback
from bot import bot
from servidor_dummy import start_dummy_server

# Lista de cogs a carregar (nomes dos módulos dentro da pasta cogs)
COGS = [
    "cogs.logs",             # carrega primeiro, outros dependem dele
   
]

async def load_extensions():
    """Carrega cada cog individualmente, mostrando erros sem parar o bot."""
    for ext in COGS:
        try:
            await bot.load_extension(ext)
            print(f"[OK] Extensão '{ext}' carregada.")
        except Exception as e:
            print(f"[ERRO] Falha ao carregar '{ext}': {type(e).__name__}: {e}")
            traceback.print_exc()

@bot.event
async def on_ready():
    print(f"Bot ligado como {bot.user} (ID: {bot.user.id})")

    # Sincroniza a árvore de comandos (comandos de barra e menus de contexto)
    # para o servidor atual. Podes forçar uma sincronização global se preferires.
    try:
        for guild in bot.guilds:
            await bot.tree.sync(guild=guild)
            print(f"Comandos sincronizados para o servidor: {guild.name}")
    except Exception as e:
        print(f"Erro ao sincronizar comandos: {e}")

    # Inicia o servidor dummy para o Render não adormecer
    await start_dummy_server()
    print("Servidor dummy iniciado.")

async def main():
    await load_extensions()
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        print("ERRO CRÍTICO: Variável de ambiente DISCORD_TOKEN não definida.")
        return
    await bot.start(token)

# Ponto de entrada
if __name__ == "__main__":
    asyncio.run(main())
