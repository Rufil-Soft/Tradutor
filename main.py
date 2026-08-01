import os
import asyncio
import traceback
import discord
from discord import app_commands
from bot import bot
from servidor_dummy import start_dummy_server

# Lista de cogs a carregar (nomes dos módulos dentro da pasta cogs)
COGS = [
    "cogs.traducao",
    "cogs.votacoes",
    "cogs.paineis",
    "cogs.comandos_setup",
    "cogs.admin",
    "cogs.frases",    
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

@bot.tree.command(name="restart", description="Reinicia a sessão do bot (Apenas Administradores).")
@app_commands.checks.has_permissions(administrator=True)
async def reiniciar(interaction: discord.Interaction):
    await interaction.response.send_message("🔄 [SISTEMA OMERTA] Reiniciando subsistemas...", ephemeral=True)
    await bot.close()

@bot.event
async def on_ready():
    print(f"Bot ligado como {bot.user} (ID: {bot.user.id})")
    try:
        for guild in bot.guilds:
            await bot.tree.sync(guild=guild)
            print(f"Comandos sincronizados para o servidor: {guild.name}")
    except Exception as e:
        print(f"Erro ao sincronizar comandos: {e}")

async def main():
    await load_extensions()
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        print("ERRO CRÍTICO: Variável de ambiente DISCORD_TOKEN não definida.")
        return
    await start_dummy_server()
    await bot.start(token)

if __name__ == "__main__":
    asyncio.run(main())
