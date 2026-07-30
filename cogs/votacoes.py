import asyncio
import discord
from discord.ext import commands
from discord import app_commands, ui
from datetime import timedelta
from collections import defaultdict
from typing import Optional
from config import FAMILIAS, CARGOS_ELEGIVEIS
from bot import bot

poll_groups = {}
message_to_group = {}

def contar_elegiveis(guild: discord.Guild) -> int:
    elegiveis = set()
    for role_name in CARGOS_ELEGIVEIS:
        role = discord.utils.get(guild.roles, name=role_name)
        if role:
            elegiveis.update(role.members)
    return len(elegiveis)

def build_resultado_futurista_embed(grupo: dict, guild: discord.Guild, final: bool = False) -> discord.Embed:
    total_votos = sum(grupo["votos"].values())
    elegiveis = contar_elegiveis(guild)
    taxa_adesao = (total_votos / elegiveis * 100) if elegiveis else 0
    
    status_titulo = "⚡ [ SISTEMA CÚPULA ] // RELATÓRIO FINAL" if final else "📡 [ SISTEMA CÚPULA ] // ACOMPANHAMENTO EM TEMPO REAL"
    cor = discord.Color.from_rgb(0, 240, 255) if final else discord.Color.gold()
    
    embed = discord.Embed(
        title=status_titulo,
        description=f"```yaml\nSESSÃO: #{grupo.get('id', 'SYS-88')}\nPERGUNTA: {grupo['pergunta']}\nSTATUS: {'FINALIZADO & ENCRIPTADO' if final else 'EM PROCESSAMENTO'}\n```",
        color=cor,
        timestamp=discord.utils.utcnow()
    )

    # Se for o relatório final e houver votos, destaca a opção vencedora
    if final and total_votos > 0:
        top_idx = max(grupo["votos"], key=grupo["votos"].get)
        vencedor_txt = grupo["opcoes"][top_idx]
        votos_vencedor = grupo["votos"][top_idx]
        embed.add_field(
            name="🏆 DECISÃO VENCEDORA",
            value=f"```fix\n> {vencedor_txt.upper()} ({votos_vencedor} votos)\n```",
            inline=False
        )
    elif final and total_votos == 0:
        embed.add_field(
            name="⚠️ DECISÃO CANCELADA",
            value="```diff\n- Sem quórum ou votos registados.\n```",
            inline=False
        )

    # Barras de Progresso Tecnológicas
    linhas_progresso = []
    for idx, opcao in enumerate(grupo["opcoes"]):
        votos = grupo["votos"].get(idx, 0)
        pct = (votos / total_votos * 100) if total_votos else 0
        barra_len = int(pct / 10)  # 10 blocos de precisão
        barra = "▓" * barra_len + "░" * (10 - barra_len)
        linhas_progresso.append(f"`[{barra}]` **{pct:.1f}%** ── **{opcao}** `({votos}v)`")

    embed.add_field(
        name="📊 PROCESSAMENTO DE DADOS",
        value="\n".join(linhas_progresso) if linhas_progresso else "Nenhum dado.",
        inline=False
    )

    # Painel de Métricas de Tráfego
    metricas = (
        f"```ini\n"
        f"[Votos Registados] : {total_votos}\n"
        f"[Membros Elegíveis]: {elegiveis}\n"
        f"[Taxa de Adesão]   : {taxa_adesao:.1f}%\n"
        f"
