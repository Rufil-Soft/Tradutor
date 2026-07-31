import asyncio
import discord
from discord import app_commands
from discord.ext import commands
from datetime import timedelta
from config import FAMILIAS, CARGOS_ELEGIVEIS
from cogs.logs import enviar_log_mafia

# Estrutura para guardar os dados de cada votação ativa
poll_data = {}

def build_resultado_futurista_embed(pergunta: str, opcoes: list, votos: dict, total_votos: int, duracao: int, final: bool = True) -> discord.Embed:
    # Reaproveita a tua função existente, mas adaptada para a nova estrutura
    # 'votos' é um dicionário user_id -> índice da opção
    # Vamos reescrever de forma simples
    contagem = {i: 0 for i in range(len(opcoes))}
    for v in votos.values():
        if v in contagem:
            contagem[v] += 1

    embed = discord.Embed(
        title="🗳️ RESULTADO FINAL" if final else "📡 VOTAÇÃO EM CURSO",
        description=f"**{pergunta}**\n\nTempo: {duracao} min",
        color=discord.Color.gold() if not final else discord.Color.from_rgb(0, 240, 255),
        timestamp=discord.utils.utcnow()
    )

    if final and total_votos > 0:
        vencedor_idx = max(contagem, key=contagem.get)
        vencedor_txt = opcoes[vencedor_idx]
        embed.add_field(name="🏆 Opção Vencedora", value=f"**{vencedor_txt}** ({contagem[vencedor_idx]} votos)", inline=False)

    for idx, opcao in enumerate(opcoes):
        votos_op = contagem[idx]
        pct = (votos_op / total_votos * 100) if total_votos else 0
        barra = "▓" * int(pct / 10) + "░" * (10 - int(pct / 10))
        embed.add_field(
            name=f"{idx+1}. {opcao}",
            value=f"`{barra}` {pct:.1f}% ({votos_op} votos)",
            inline=False
        )

    elegiveis = "N/A"  # Podes calcular se quiseres, mas não temos o guild facilmente
    embed.set_footer(text=f"Votos totais: {total_votos} | Duração: {duracao} min")
    return embed


class VotacaoView(discord.ui.View):
    def __init__(self, poll_id: int, opcoes: list):
        super().__init__(timeout=None)
        self.poll_id = poll_id
        self.opcoes = opcoes
        # Criar um botão para cada opção
        for i, opcao in enumerate(opcoes):
            # Usa emojis numéricos para ser mais bonito
            emoji = f"{i+1}\u20e3"  # 1️⃣, 2️⃣, etc.
            botao = discord.ui.Button(label=opcao[:80], style=discord.ButtonStyle.primary, emoji=emoji, custom_id=f"voto_{poll_id}_{i}")
            botao.callback = self.voto_callback
            self.add_item(botao)

    async def voto_callback(self, interaction: discord.Interaction):
        poll_id = self.poll_id
        user_id = interaction.user.id

        # Obter dados da votação
        dados = poll_data.get(poll_id)
        if not dados:
            await interaction.response.send_message("Esta votação já terminou.", ephemeral=True)
            return

        # Determinar opção escolhida
        custom_id = interaction.data["custom_id"]
        opcao_idx = int(custom_id.split("_")[-1])

        # Registar voto
        if user_id in dados["votos"]:
            antigo = dados["votos"][user_id]
            if antigo == opcao_idx:
                await interaction.response.send_message(f"Já votaste em **{self.opcoes[opcao_idx]}**.", ephemeral=True)
                return
            else:
                await interaction.response.send_message(f"Voto alterado de **{self.opcoes[antigo]}** para **{self.opcoes[opcao_idx]}**.", ephemeral=True)
        else:
            await interaction.response.send_message(f"Votaste em **{self.opcoes[opcao_idx]}**.", ephemeral=True)

        dados["votos"][user_id] = opcao_idx


class Votacoes(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="votacao", description="Cria uma votação e propaga para as famílias")
    @app_commands.default_permissions(administrator=True)
    async def criar_votacao(self, interaction: discord.Interaction, pergunta: str, opcoes: str, duracao: int):
        """
        pergunta: a questão
        opcoes: separadas por vírgula (ex.: "Sim, Não, Abstenção")
        duracao: em minutos
        """
        await interaction.response.defer(ephemeral=True)

        lista_opcoes = [op.strip() for op in opcoes.split(",") if op.strip()]
        if len(lista_opcoes) < 2:
            await interaction.followup.send("Precisas de pelo menos 2 opções.", ephemeral=True)
            return
        if duracao < 1:
            await interaction.followup.send("Duração mínima de 1 minuto.", ephemeral=True)
            return

        # Criar ID único
        poll_id = len(poll_data) + 1
        poll_data[poll_id] = {
            "pergunta": pergunta,
            "opcoes": lista_opcoes,
            "duracao": duracao,
            "votos": {},
            "mensagens": [],  # lista de (channel_id, message_id)
            "criador": interaction.user.id
        }

        guild = interaction.guild

        # --- Enviar mensagem original no canal atual ---
        embed_inicial = discord.Embed(
            title="🗳️ VOTAÇÃO ATIVA",
            description=f"**{pergunta}**\n\nDuração: {duracao} minutos\nVota clicando numa das opções abaixo.",
            color=discord.Color.gold()
        )
        view = VotacaoView(poll_id, lista_opcoes)
        msg_original = await interaction.channel.send(embed=embed_inicial, view=view)
        poll_data[poll_id]["mensagens"].append((interaction.channel_id, msg_original.id))

        # --- Propagar para os canais 🗳️-votações das famílias ---
        for familia_key, nome_familia in FAMILIAS.items():
            nome_cat = f"🍷 {nome_familia.upper()}"
            categoria = discord.utils.get(guild.categories, name=nome_cat)
            if categoria:
                canal_votacoes = discord.utils.get(categoria.text_channels, name="🗳️-votações")
                if canal_votacoes:
                    try:
                        view_fam = VotacaoView(poll_id, lista_opcoes)  # nova view para esta mensagem
                        msg_fam = await canal_votacoes.send(embed=embed_inicial, view=view_fam)
                        poll_data[poll_id]["mensagens"].append((canal_votacoes.id, msg_fam.id))
                    except Exception as e:
                        print(f"Erro ao propagar votação para {nome_familia}: {e}")

        # Confirmar ao criador
        await interaction.followup.send(f"✅ Votação criada com ID #{poll_id}. Irá terminar em {duracao} minuto(s).", ephemeral=True)

        # Agendar fim da votação
        asyncio.create_task(self.finalizar_votacao(poll_id, duracao * 60))

    async def finalizar_votacao(self, poll_id: int, delay: int):
        await asyncio.sleep(delay)

        dados = poll_data.get(poll_id)
        if not dados:
            return  # já removida

        total_votos = len(dados["votos"])

        # Criar embed final
        embed_final = build_resultado_futurista_embed(
            pergunta=dados["pergunta"],
            opcoes=dados["opcoes"],
            votos=dados["votos"],
            total_votos=total_votos,
            duracao=dados["duracao"],
            final=True
        )

        # Percorrer todas as mensagens registadas e desativá-las
        for channel_id, message_id in dados["mensagens"]:
            try:
                canal = self.bot.get_channel(channel_id)
                if canal:
                    msg = await canal.fetch_message(message_id)
                    # Desativar a view: editar a mensagem com o embed final e sem view
                    await msg.edit(embed=embed_final, view=None)
            except Exception as e:
                print(f"Erro ao finalizar votação #{poll_id} na mensagem {message_id}: {e}")

        # Enviar log
        guild = self.bot.guilds[0]  # cuidado, mas o bot normalmente está em apenas um servidor
        await enviar_log_mafia(guild, f"🗳️ Votação #{poll_id} Finalizada", f"Pergunta: **{dados['pergunta']}**\nVotos totais: {total_votos}", discord.Color.blue())

        # Limpar dados
        del poll_data[poll_id]


async def setup(bot: commands.Bot):
    await bot.add_cog(Votacoes(bot))
