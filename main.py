import os
import asyncio
import traceback
import time
import os.path
import discord
from discord import app_commands
from bot import bot
from servidor_dummy import start_dummy_server

# ---------- ANTI‑RATE‑LIMIT ----------
LAST_LOGIN_FILE = "last_login.txt"
MIN_LOGIN_INTERVAL = 60          # segundos entre arranques
MAX_LOGIN_ATTEMPTS = 3           # nº máximo de tentativas de login
RETRY_DELAY = 15 * 60            # 15 minutos entre tentativas após 429

def wait_for_login_cooldown():
    """Espera se a última tentativa de login foi há menos de MIN_LOGIN_INTERVAL."""
    if os.path.exists(LAST_LOGIN_FILE):
        try:
            with open(LAST_LOGIN_FILE, "r") as f:
                last_timestamp = float(f.read().strip())
            elapsed = time.time() - last_timestamp
            if elapsed < MIN_LOGIN_INTERVAL:
                wait_time = MIN_LOGIN_INTERVAL - elapsed
                print(f"[ANTI-RATE] Última tentativa há {elapsed:.0f}s. Aguardando {wait_time:.0f}s...")
                time.sleep(wait_time)
        except Exception as e:
            print(f"[ANTI-RATE] Erro ao ler ficheiro de login: {e}")

def update_last_login():
    """Guarda o timestamp actual da tentativa de login."""
    with open(LAST_LOGIN_FILE, "w") as f:
        f.write(str(time.time()))
# ------------------------------------

# Lista de cogs a carregar
COGS = [
    "cogs.traducao",
    "cogs.votacoes",
    "cogs.paineis",
    "cogs.comandos_setup",
    "cogs.admin",
    "cogs.frases",
    "cogs.audio",
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

async def start_bot_with_retry(token: str):
    """Tenta iniciar o bot até MAX_LOGIN_ATTEMPTS vezes, esperando RETRY_DELAY entre tentativas em caso de 429."""
    for attempt in range(1, MAX_LOGIN_ATTEMPTS + 1):
        update_last_login()  # regista a hora desta tentativa
        print(f"[LOGIN] Tentativa {attempt} de {MAX_LOGIN_ATTEMPTS}...")
        try:
            await bot.start(token)
            return  # sucesso! O bot permanece em execução
        except discord.HTTPException as e:
            if e.status == 429 and attempt < MAX_LOGIN_ATTEMPTS:
                print(f"[LOGIN] Erro 429 Too Many Requests. Aguardando {RETRY_DELAY // 60} minutos antes da próxima tentativa...")
                await asyncio.sleep(RETRY_DELAY)
            else:
                print(f"[LOGIN] Falha final: {e}")
                raise
        except Exception as e:
            print(f"[LOGIN] Erro inesperado: {e}")
            raise

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
    wait_for_login_cooldown()   # espera mínima entre arranques
    await start_bot_with_retry(token)

if __name__ == "__main__":
    asyncio.run(main())
