import discord
from discord.ext import commands, tasks
import json
from datetime import datetime, timedelta
from config import FAMILIAS
from utils.logs import enviar_log_mafia

# ---------- ESTRUTURA DE DADOS ----------
economia = {"familias": {}, "jogadores": {}}
CANAL_BACKUP_NOME = "💾-mafia-backend"

# ---------- FUNÇÕES DE PERSISTÊNCIA ----------
async def carregar_dados(bot: commands.Bot):
    global economia
    for guild in bot.guilds:
        canal = discord.utils.get(guild.text_channels, name=CANAL_BACKUP_NOME)
        if not canal:
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(read_messages=False),
                guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
            }
            canal = await guild.create_text_channel(CANAL_BACKUP_NOME, overwrites=overwrites, topic="Backup automático da economia. Não apagar.")
            await canal.send("```json\n{}```")
            print("[ECONOMIA] Canal de backup criado.")
            return

        async for msg in canal.history(limit=1):
            try:
                conteudo = msg.content.strip()
                if conteudo.startswith("```json") and conteudo.endswith("```"):
                    json_str = conteudo[7:-3].strip()
                elif conteudo.startswith("```") and conteudo.endswith("```"):
                    json_str = conteudo[3:-3].strip()
                else:
                    json_str = conteudo
                economia = json.loads(json_str)
                print("[ECONOMIA] Dados carregados do backup.")
            except Exception as e:
                print(f"[ECONOMIA] Erro ao carregar backup: {e}")
            break

async def salvar_dados(bot: commands.Bot):
    for guild in bot.guilds:
        canal = discord.utils.get(guild.text_channels, name=CANAL_BACKUP_NOME)
        if not canal:
            print("[ECONOMIA] Canal de backup não encontrado.")
            return
        async for msg in canal.history(limit=1):
            try:
                novo_conteudo = "```json\n" + json.dumps(economia, indent=4, default=str) + "```"
                await msg.edit(content=novo_conteudo)
                print("[ECONOMIA] Dados salvos.")
            except Exception as e:
                print(f"[ECONOMIA] Erro ao salvar backup: {e}")
            break

# ---------- FUNÇÕES AUXILIARES ----------
def obter_familia_jogador(member: discord.Member) -> str | None:
    for nome_familia in FAMILIAS.values():
        if discord.utils.get(member.roles, name=nome_familia):
            return nome_familia
    return None

def inicializar_familia(nome_familia: str):
    if nome_familia not in economia["familias"]:
        economia["familias"][nome_familia] = {
            "dinheiro": 1000,
            "balas": 50,
            "licor": 20,
            "apartamentos": 0,
            "casinos": 0,
            "lojas_licor": 0,
            "fabrica_balas": 0
        }

def adicionar_dinheiro(nome_familia: str, quantia: int):
    inicializar_familia(nome_familia)
    economia["familias"][nome_familia]["dinheiro"] += quantia

def adicionar_balas(nome_familia: str, quantia: int):
    inicializar_familia(nome_familia)
    economia["familias"][nome_familia]["balas"] += quantia

def adicionar_licor(nome_familia: str, quantia: int):
    inicializar_familia(nome_familia)
    economia["familias"][nome_familia]["licor"] += quantia

def adicionar_edificio(nome_familia: str, tipo: str, quantidade: int = 1):
    inicializar_familia(nome_familia)
    economia["familias"][nome_familia][tipo] += quantidade

# ---------- LOOP DE RENDIMENTOS (A CADA HORA) ----------
class Economia(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.rendimentos_loop.start()

    @tasks.loop(hours=1)
    async def rendimentos_loop(self):
        for nome_familia, dados in economia["familias"].items():
            dinheiro_gerado = dados["apartamentos"] * 100
            dinheiro_gerado += dados["casinos"] * 200
            licor_gerado = dados["lojas_licor"] * 5
            balas_geradas = dados["fabrica_balas"] * 2

            adicionar_dinheiro(nome_familia, dinheiro_gerado)
            adicionar_licor(nome_familia, licor_gerado)
            adicionar_balas(nome_familia, balas_geradas)

            if dinheiro_gerado > 0 or licor_gerado > 0 or balas_geradas > 0:
                await enviar_log_mafia(
                    self.bot.guilds[0],
                    f"💰 Rendimentos Horários - {nome_familia}",
                    f"Dinheiro: +{dinheiro_gerado}\nLicor: +{licor_gerado}\nBalas: +{balas_geradas}",
                    discord.Color.green()
                )

        await salvar_dados(self.bot)

    @rendimentos_loop.before_loop
    async def antes_do_loop(self):
        await self.bot.wait_until_ready()
        await carregar_dados(self.bot)

    def cog_unload(self):
        self.rendimentos_loop.cancel()

async def setup(bot: commands.Bot):
    await bot.add_cog(Economia(bot))
