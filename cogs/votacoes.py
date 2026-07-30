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

def build_resultado_embed(grupo: dict, guild: discord.Guild) -> discord.Embed:
    total = sum(grupo["votos"].values())
    elegiveis = contar_elegiveis(guild)
    faltam = max(elegiveis - total, 0)
    embed = discord.Embed(title=f"📊 Resultado Agregado — {grupo['pergunta']}", color=discord.Color.dark_gold(), timestamp=discord.utils.utcnow())
    for idx, opcao in enumerate(grupo["opcoes"]):
        votos = grupo["votos"].get(idx, 0)
        pct = (votos / total * 100) if total else 0
        barra_len = int(pct / 5)
        barra = "█" * barra_len + "░" * (20 - barra_len)
        embed.add_field(name=opcao, value=f"`{barra}` **{votos}** votos ({pct:.1f}%)", inline=False)
    familias_txt = ", ".join(v["familia"] for v in grupo["member_polls"].values()) or "Nenhuma"
    embed.add_field(name="🗳️ Participação", value=f"Votaram: **{total}**\nElegíveis: **{elegiveis}**\nFaltam: **{faltam}**", inline=False)
    embed.set_footer(text=f"Famílias: {familias_txt}")
    return embed

async def atualizar_embed_central(group_id: str):
    grupo = poll_groups.get(group_id)
    if not grupo or not grupo.get("embed_message_id"):
        return
    canal = bot.get_channel(grupo["canal_central_id"])
    guild = canal.guild if canal else None
    if not guild:
        return
    try:
        msg = await canal.fetch_message(grupo["embed_message_id"])
        await msg.edit(embed=build_resultado_embed(grupo, guild))
    except (discord.NotFound, discord.Forbidden, discord.HTTPException) as e:
        print(f"[VOTACAO] Erro ao atualizar embed central: {e}")

def limpar_grupo(group_id: str):
    grupo = poll_groups.pop(group_id, None)
    if not grupo:
        return
    for message_id in grupo["member_polls"].keys():
        message_to_group.pop(message_id, None)

class DeleteResultView(discord.ui.View):
    def __init__(self, group_id: str):
        super().__init__(timeout=None)
        self.group_id = group_id
    @discord.ui.button(label="Delete", style=discord.ButtonStyle.danger, emoji="🗑️")
    async def delete_result(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("Only administrators can delete the result.", ephemeral=True)
            return
        await interaction.message.delete()
        limpar_grupo(self.group_id)

class DonPollModal(ui.Modal, title="Criar Votação Oficial da Cúpula"):
    pergunta = ui.TextInput(label="Pergunta da Votação", placeholder="Ex: A que horas atacamos?", style=discord.TextStyle.short, required=True)
    opcoes = ui.TextInput(label="Opções (separadas por vírgula)", placeholder="Ex: 14h, 16h, 20h", style=discord.TextStyle.paragraph, required=True)
    duracao = ui.TextInput(label="Duração (horas)", placeholder="Ex: 24", style=discord.TextStyle.short, required=True)

    async def _delete_later(self, message: discord.Message, hours: float, group_id: Optional[str] = None):
        await asyncio.sleep(hours * 3600)
        try:
            await message.delete()
        except:
            pass
        if group_id:
            limpar_grupo(group_id)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            pergunta_texto = self.pergunta.value
            raw_opcoes = [o.strip() for o in self.opcoes.value.split(",") if o.strip()]
            if len(raw_opcoes) < 2:
                await interaction.followup.send("❌ Tens de fornecer pelo menos 2 opções.", ephemeral=True)
                return
            if len(raw_opcoes) > 10:
                await interaction.followup.send("❌ Máximo de 10 opções.", ephemeral=True)
                return
            try:
                horas = float(self.duracao.value)
                if horas <= 0:
                    raise ValueError
            except ValueError:
                await interaction.followup.send("❌ Duração inválida (ex: 24).", ephemeral=True)
                return

            guild = interaction.guild
            cargo_capo = discord.utils.get(guild.roles, name="Capo")
            group_id = f"{interaction.id}"
            poll_groups[group_id] = {
                "pergunta": pergunta_texto,
                "opcoes": raw_opcoes,
                "votos": defaultdict(int),
                "canal_central_id": None,
                "embed_message_id": None,
                "member_polls": {}
            }
            grupo = poll_groups[group_id]
            resultado = {}

            for familia_key, nome_familia in FAMILIAS.items():
                nome_familia_role = discord.utils.get(guild.roles, name=nome_familia)
                if not nome_familia_role:
                    continue
                tem_capo = any(cargo_capo in m.roles for m in nome_familia_role.members)
                if not tem_capo:
                    resultado[nome_familia] = "❌ Sem Capo ativo"
                    continue
                nome_cat = f"🍷 {nome_familia.upper()}"
                categoria = discord.utils.get(guild.categories, name=nome_cat)
                if not categoria:
                    resultado[nome_familia] = "❌ Categoria não encontrada (QG não criado)"
                    continue
                canal = discord.utils.get(categoria.text_channels, name="🗳️-votações")
                if not canal:
                    resultado[nome_familia] = "❌ Canal 🗳️-votações não encontrado"
                    continue
                perms = canal.permissions_for(guild.me)
                if not perms.send_messages:
                    resultado[nome_familia] = "❌ Sem permissão 'Send Messages'"
                    continue

                try:
                    poll = discord.Poll(question=pergunta_texto, duration=timedelta(hours=horas))
                    for opt in raw_opcoes:
                        poll.add_answer(text=opt)
                    msg = await canal.send(
                        content=f"🗳️ **VOTAÇÃO DA CÚPULA** (Aberta por {interaction.user.mention})",
                        poll=poll
                    )
                    resultado[nome_familia] = "✅ Sucesso"
                    answer_map = {}
                    if msg.poll:
                        for idx, answer in enumerate(msg.poll.answers):
                            answer_map[answer.id] = idx
                    grupo["member_polls"][msg.id] = {"familia": nome_familia, "answer_map": answer_map}
                    message_to_group[msg.id] = group_id
                    asyncio.create_task(self._delete_later(msg, horas))
                except Exception:
                    try:
                        emojis = ["1️⃣","2️⃣","3️⃣","4️⃣","5️⃣","6️⃣","7️⃣","8️⃣","9️⃣","🔟"]
                        descricao = "\n".join([f"{emojis[i]} {op}" for i, op in enumerate(raw_opcoes)])
                        embed = discord.Embed(
                            title=f"🗳️ {pergunta_texto}",
                            description=f"**VOTAÇÃO DA CÚPULA**\n\n{descricao}\n*Duração: {horas}h*",
                            color=discord.Color.gold()
                        )
                        msg = await canal.send(embed=embed)
                        for i in range(len(raw_opcoes)):
                            await msg.add_reaction(emojis[i])
                        resultado[nome_familia] = "✅ Sucesso (reações)"
                        asyncio.create_task(self._delete_later(msg, horas))
                    except Exception as e:
                        resultado[nome_familia] = f"❌ Falhou: {str(e)[:60]}"
                await asyncio.sleep(1)

            # Canal central (vote‑command)
            canal_origem = interaction.channel
            if canal_origem and canal_origem.permissions_for(guild.me).send_messages:
                grupo["canal_central_id"] = canal_origem.id
                try:
                    poll_origem = discord.Poll(question=pergunta_texto, duration=timedelta(hours=horas))
                    for opt in raw_opcoes:
                        poll_origem.add_answer(text=opt)
                    central_msg = await canal_origem.send(
                        content=f"🗳️ **VOTAÇÃO OFICIAL DA CÚPULA** (Criada por {interaction.user.mention})",
                        poll=poll_origem
                    )
                    asyncio.create_task(self._delete_later(central_msg, horas))
                except:
                    pass
                if grupo["member_polls"]:
                    try:
                        embed_msg = await canal_origem.send(
                            embed=build_resultado_embed(grupo, guild),
                            view=DeleteResultView(group_id)
                        )
                        grupo["embed_message_id"] = embed_msg.id
                        asyncio.create_task(self._delete_later_group_only(horas, group_id))
                        await canal_origem.send("━━━━━━━━━━━━━━━━━━")
                    except Exception as e:
                        print(f"[VOTACAO] Erro ao enviar embed agregado: {e}")

            sucessos = [f for f, r in resultado.items() if "Sucesso" in r]
            falhas = {f: r for f, r in resultado.items() if "Sucesso" not in r}
            resposta = ""
            if sucessos:
                resposta += f"✅ Propagada para: **{', '.join(sucessos)}**.\n"
            if falhas:
                resposta += "\n⚠️ **Problemas:**\n"
                for fam, motivo in falhas.items():
                    resposta += f"• **{fam}**: {motivo}\n"
            if not sucessos and not falhas:
                resposta = "⚠️ Nenhuma família processada."
            resposta += f"\n⏳ As polls das famílias e a poll central serão apagadas após **{horas}** horas."
            if grupo["member_polls"]:
                resposta += "\n📊 O resultado agregado ficará visível com botão de eliminar."
            await interaction.followup.send(resposta, ephemeral=True)
        except Exception as erro:
            try:
                await interaction.followup.send(f"❌ Erro inesperado: {str(erro)[:200]}", ephemeral=True)
            except:
                pass

    async def _delete_later_group_only(self, hours: float, group_id: str):
        await asyncio.sleep(hours * 3600)
        limpar_grupo(group_id)


class Votacoes(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="votacao", description="Abre o formulário para o Don criar uma votação global.")
    @commands.has_permissions(administrator=True)
    async def votacao_slash(self, interaction: discord.Interaction):
        await interaction.response.send_modal(DonPollModal())

    @commands.Cog.listener()
    async def on_raw_poll_vote_add(self, payload):
        group_id = message_to_group.get(payload.message_id)
        if not group_id:
            return
        grupo = poll_groups.get(group_id)
        if not grupo:
            return
        poll_info = grupo["member_polls"].get(payload.message_id)
        if not poll_info:
            return
        idx = poll_info["answer_map"].get(payload.answer_id)
        if idx is None:
            return
        grupo["votos"][idx] += 1
        await atualizar_embed_central(group_id)

    @commands.Cog.listener()
    async def on_raw_poll_vote_remove(self, payload):
        group_id = message_to_group.get(payload.message_id)
        if not group_id:
            return
        grupo = poll_groups.get(group_id)
        if not grupo:
            return
        poll_info = grupo["member_polls"].get(payload.message_id)
        if not poll_info:
            return
        idx = poll_info["answer_map"].get(payload.answer_id)
        if idx is None:
            return
        grupo["votos"][idx] = max(0, grupo["votos"][idx] - 1)
        await atualizar_embed_central(group_id)


async def setup(bot: commands.Bot):
    await bot.add_cog(Votacoes(bot))
