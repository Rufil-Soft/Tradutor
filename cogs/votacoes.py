import asyncio
import discord
from discord import app_commands
from discord.ext import commands
from deep_translator import GoogleTranslator
from config import FAMILIAS, CARGOS_ELEGIVEIS
from cogs.logs import enviar_log_mafia

# Cache de traduções (texto, idioma) -> texto traduzido
_t_cache = {}

async def translate(key: str, target: str) -> str:
    """Traduz 'key' para 'target' (código de 2 letras). Cache interno."""
    if target == "pt":
        return key
    cache_key = (key, target)
    if cache_key in _t_cache:
        return _t_cache[cache_key]
    try:
        res = await asyncio.to_thread(GoogleTranslator(source='auto', target=target).translate, key)
        _t_cache[cache_key] = res
        return res
    except Exception:
        return key  # fallback


# Estrutura de dados das votações ativas
poll_data = {}
NUM_EMOJIS = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]


async def build_embed_async(pergunta: str, opcoes: list, contagem: dict,
                            total_votos: int, duracao: int, final: bool,
                            elegiveis: int, lang: str) -> discord.Embed:
    """Cria o embed de votação com design profissional e tradução."""

    # Textos traduzíveis
    titulo = await translate("🏛️ SYSTEM COUNCIL // FINAL RESULT" if final else "📡 SYSTEM COUNCIL // LIVE VOTE", lang)
    cor = discord.Color.from_rgb(0, 240, 255) if final else discord.Color.gold()
    status = await translate("CLOSED" if final else "ACTIVE", lang)
    pergunta_label = await translate("QUESTION:", lang)
    duracao_label = await translate("DURATION:", lang)
    status_label = await translate("STATUS:", lang)

    descricao = f"```yaml\n{pergunta_label} {pergunta}\n{duracao_label} {duracao} min\n{status_label} {status}\n```"

    embed = discord.Embed(title=titulo, description=descricao, color=cor, timestamp=discord.utils.utcnow())

    # Vencedor (se final e com votos)
    if final and total_votos > 0:
        vencedor_idx = max(contagem, key=contagem.get)
        vencedor_txt = opcoes[vencedor_idx]
        campo_vencedor = await translate("🏆 WINNING DECISION", lang)
        embed.add_field(
            name=campo_vencedor,
            value=f"```fix\n{vencedor_txt.upper()} ({contagem[vencedor_idx]} {await translate('votes', lang)})\n```",
            inline=False
        )
    elif final and total_votos == 0:
        campo_sem_quorum = await translate("⚠️ NO QUORUM", lang)
        embed.add_field(name=campo_sem_quorum, value="```diff\n- Nenhum voto registado.\n```", inline=False)

    # Distribuição de votos
    dist_label = await translate("📊 VOTE DISTRIBUTION", lang)
    linhas = []
    for idx, opcao in enumerate(opcoes):
        v = contagem.get(idx, 0)
        pct = (v / total_votos * 100) if total_votos else 0
        barra = "▓" * int(pct / 10) + "░" * (10 - int(pct / 10))
        linhas.append(f"`{barra}` **{pct:.1f}%** ── **{opcao}** `({v}v)`")
    embed.add_field(name=dist_label, value="\n".join(linhas) if linhas else await translate("No votes yet.", lang), inline=False)

    # Métricas de quórum
    if elegiveis > 0:
        taxa = (total_votos / elegiveis * 100) if elegiveis else 0
        metricas_label = await translate("⚙️ QUORUM METRICS", lang)
        reg_votes = await translate("Registered Votes", lang)
        elig_members = await translate("Eligible Members", lang)
        turnout = await translate("Turnout", lang)
        metricas = f"```ini\n[{reg_votes}] : {total_votos}\n[{elig_members}] : {elegiveis}\n[{turnout}]   : {taxa:.1f}%\n```"
        embed.add_field(name=metricas_label, value=metricas, inline=False)

    embed.set_footer(text="Omertà • Council System")
    return embed


class VotacaoView(discord.ui.View):
    """View persistente com um botão por opção."""
    def __init__(self, poll_id: int, opcoes: list, lang: str = "pt"):
        super().__init__(timeout=None)
        self.poll_id = poll_id
        self.opcoes = opcoes
        self.lang = lang  # idioma base (para fallback, não afeta botões)

        for i, opcao in enumerate(opcoes):
            emoji = NUM_EMOJIS[i] if i < len(NUM_EMOJIS) else "🔹"
            botao = discord.ui.Button(
                label=opcao[:80],
                style=discord.ButtonStyle.secondary,
                emoji=emoji,
                custom_id=f"voto_{poll_id}_{i}",
                row=i // 5
            )
            botao.callback = self.voto_callback
            self.add_item(botao)

    async def voto_callback(self, interaction: discord.Interaction):
        """Processa o voto, com resposta no idioma do utilizador."""
        poll_id = self.poll_id
        user_id = interaction.user.id
        user_locale = str(interaction.locale).split("-")[0] or "pt"

        dados = poll_data.get(poll_id)
        if not dados:
            await interaction.response.send_message(await translate("⛔ This poll has closed.", user_locale), ephemeral=True)
            return

        # Extrair índice da opção
        custom_id = interaction.data["custom_id"]
        opcao_idx = int(custom_id.split("_")[-1])

        # Elegibilidade
        if user_id not in dados.get("elegiveis_ids", set()):
            await interaction.response.send_message(await translate("🔒 You are not eligible to vote.", user_locale), ephemeral=True)
            return

        if user_id in dados["votos"]:
            antigo = dados["votos"][user_id]
            if antigo == opcao_idx:
                msg = await translate("ℹ️ You already voted for {}.", user_locale)
                await interaction.response.send_message(msg.format(self.opcoes[opcao_idx]), ephemeral=True)
                return
            else:
                dados["votos"][user_id] = opcao_idx
                msg = await translate("🔄 Vote changed from {} to {}.", user_locale)
                await interaction.response.send_message(msg.format(self.opcoes[antigo], self.opcoes[opcao_idx]), ephemeral=True)
        else:
            dados["votos"][user_id] = opcao_idx
            msg = await translate("✅ Vote registered for {}. The Council thanks your loyalty.", user_locale)
            await interaction.response.send_message(msg.format(self.opcoes[opcao_idx]), ephemeral=True)


class Votacoes(commands.Cog):
    """Sistema de votações da Cúpula com propagação e tradução."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="votacao", description="Convoca uma votação oficial da Cúpula")
    @app_commands.default_permissions(administrator=True)
    async def criar_votacao(self, interaction: discord.Interaction, pergunta: str, opcoes: str, duracao: int = 10):
        await interaction.response.defer(ephemeral=True)

        criador_locale = str(interaction.locale).split("-")[0] or "pt"
        lista_opcoes = [op.strip() for op in opcoes.split(",") if op.strip()]

        if len(lista_opcoes) < 2:
            await interaction.followup.send(await translate("⚠️ Need at least 2 options.", criador_locale), ephemeral=True)
            return
        if duracao < 1:
            await interaction.followup.send(await translate("⚠️ Minimum duration is 1 minute.", criador_locale), ephemeral=True)
            return

        poll_id = len(poll_data) + 1
        guild = interaction.guild

        # Membros elegíveis (baseado nos cargos da config)
        elegiveis_ids = set()
        for role_name in CARGOS_ELEGIVEIS:
            role = discord.utils.get(guild.roles, name=role_name)
            if role:
                elegiveis_ids.update(m.id for m in role.members)
        total_elegiveis = len(elegiveis_ids)

        poll_data[poll_id] = {
            "pergunta": pergunta,
            "opcoes": lista_opcoes,
            "duracao": duracao,
            "votos": {},
            "mensagens": [],
            "elegiveis_ids": elegiveis_ids,
            "total_elegiveis": total_elegiveis,
            "criador": interaction.user.id,
            "guild_id": guild.id,
            "lang": criador_locale
        }

        # Embed inicial traduzido
        embed_inicial = await build_embed_async(
            pergunta=pergunta,
            opcoes=lista_opcoes,
            contagem={i: 0 for i in range(len(lista_opcoes))},
            total_votos=0,
            duracao=duracao,
            final=False,
            elegiveis=total_elegiveis,
            lang=criador_locale
        )

        # Mensagem original (canal de comando)
        view_original = VotacaoView(poll_id, lista_opcoes, lang=criador_locale)
        msg_original = await interaction.channel.send(embed=embed_inicial, view=view_original)
        poll_data[poll_id]["mensagens"].append((interaction.channel_id, msg_original.id))

        # Propagação para 🗳️-votações das famílias
        for familia_key, nome_familia in FAMILIAS.items():
            nome_cat = f"🍷 {nome_familia.upper()}"
            categoria = discord.utils.get(guild.categories, name=nome_cat)
            if categoria:
                canal_votacoes = discord.utils.get(categoria.text_channels, name="🗳️-votações")
                if canal_votacoes:
                    try:
                        view_fam = VotacaoView(poll_id, lista_opcoes, lang=criador_locale)
                        msg_fam = await canal_votacoes.send(embed=embed_inicial, view=view_fam)
                        poll_data[poll_id]["mensagens"].append((canal_votacoes.id, msg_fam.id))
                    except Exception as e:
                        print(f"Erro ao propagar para {nome_familia}: {e}")

        # Confirmação ao criador
        confirm_msg = await translate("✅ Poll #{} started.\n📢 Propagated to {} families.\n⏳ Ends in {} min(s).", criador_locale)
        await interaction.followup.send(
            confirm_msg.format(poll_id, len(poll_data[poll_id]["mensagens"]) - 1, duracao),
            ephemeral=True
        )

        # Agendar fim da votação
        asyncio.create_task(self.finalizar_votacao(poll_id, duracao * 60))

    async def finalizar_votacao(self, poll_id: int, delay: int):
        await asyncio.sleep(delay)
        dados = poll_data.get(poll_id)
        if not dados:
            return

        # Calcula contagem
        contagem = {i: 0 for i in range(len(dados["opcoes"]))}
        for v in dados["votos"].values():
            if v in contagem:
                contagem[v] += 1
        total_votos = len(dados["votos"])
        lang = dados.get("lang", "pt")

        embed_final = await build_embed_async(
            pergunta=dados["pergunta"],
            opcoes=dados["opcoes"],
            contagem=contagem,
            total_votos=total_votos,
            duracao=dados["duracao"],
            final=True,
            elegiveis=dados.get("total_elegiveis", 0),
            lang=lang
        )

        # Substitui todas as mensagens
        for channel_id, message_id in dados["mensagens"]:
            try:
                canal = self.bot.get_channel(channel_id)
                if canal:
                    msg = await canal.fetch_message(message_id)
                    await msg.edit(embed=embed_final, view=None)
            except Exception as e:
                print(f"Erro ao finalizar mensagem {message_id}: {e}")

        # Regista no log
        guild = self.bot.get_guild(dados["guild_id"])
        if guild:
            await enviar_log_mafia(
                guild,
                f"🗳️ Votação #{poll_id} Encerrada",
                f"**{dados['pergunta']}**\nVotos: {total_votos}",
                discord.Color.blue()
            )

        del poll_data[poll_id]


async def setup(bot: commands.Bot):
    await bot.add_cog(Votacoes(bot))
