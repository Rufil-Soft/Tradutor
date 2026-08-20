import asyncio
import discord
from discord import app_commands
from discord.ext import commands, tasks
from datetime import timedelta, datetime
from deep_translator import GoogleTranslator
from config import FAMILIAS, CARGOS_ELEGIVEIS
from utils.logs import enviar_log_mafia

# Cache de traduções
_t_cache = {}

async def translate(key: str, target: str) -> str:
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
        return key


poll_data = {}
NUM_EMOJIS = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]


async def build_embed_async(pergunta: str, opcoes: list, contagem: dict,
                            total_votos: int, end_time, final: bool,
                            lang: str) -> discord.Embed:
    """Embed moderno, limpo, apenas com a data de término e (no final) resultados."""

    if final:
        titulo = await translate("🏛️ Council · Final Result", lang)
        cor = discord.Color.from_rgb(0, 200, 255)
    else:
        titulo = await translate("📡 Council · Vote Now", lang)
        cor = discord.Color.from_rgb(255, 200, 0)

    embed = discord.Embed(
        title=titulo,
        description=f"**{await translate('Question', lang)}:** {pergunta}",
        color=cor,
        timestamp=discord.utils.utcnow()
    )

    unix = int(end_time.timestamp())
    if not final:
        embed.add_field(
            name="🗓️ " + await translate("Ends", lang),
            value=f"<t:{unix}:F>  (<t:{unix}:R>)",
            inline=False
        )
    else:
        embed.add_field(
            name="🗓️ " + await translate("Ended", lang),
            value=f"<t:{unix}:F>",
            inline=False
        )

    if final and total_votos > 0:
        vencedor_idx = max(contagem, key=contagem.get)
        vencedor_txt = opcoes[vencedor_idx]
        vencedor_label = await translate("🏆 Decision", lang)
        embed.add_field(
            name=vencedor_label,
            value=f"**{vencedor_txt.upper()}** ({contagem[vencedor_idx]} {await translate('votes', lang)})",
            inline=False
        )

        linhas = []
        for idx, opcao in enumerate(opcoes):
            v = contagem.get(idx, 0)
            pct = (v / total_votos * 100) if total_votos else 0
            linhas.append(f"**{opcao}:** `{pct:.0f}%` ({v}v)")
        embed.add_field(
            name="📊 " + await translate("Results", lang),
            value="\n".join(linhas),
            inline=False
        )
    elif final and total_votos == 0:
        embed.add_field(
            name="⚠️ " + await translate("No quorum", lang),
            value="Nenhum voto registado.",
            inline=False
        )

    embed.set_footer(text="Omertà · Council System")
    return embed


class VotacaoView(discord.ui.View):
    def __init__(self, poll_id: int, opcoes: list, criador_id: int, lang: str = "pt"):
        super().__init__(timeout=None)
        self.poll_id = poll_id
        self.opcoes = opcoes
        self.criador_id = criador_id
        self.lang = lang

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

        cancel_btn = discord.ui.Button(
            label="Cancel",
            style=discord.ButtonStyle.danger,
            emoji="🛑",
            custom_id=f"cancel_poll_{poll_id}",
            row=2
        )
        cancel_btn.callback = self.cancel_callback
        self.add_item(cancel_btn)

    async def voto_callback(self, interaction: discord.Interaction):
        poll_id = self.poll_id
        user_id = interaction.user.id
        user_locale = str(interaction.locale).split("-")[0] or "pt"

        dados = poll_data.get(poll_id)
        if not dados:
            await interaction.response.send_message(await translate("⛔ This poll has closed.", user_locale), ephemeral=True)
            return

        custom_id = interaction.data["custom_id"]
        opcao_idx = int(custom_id.split("_")[-1])

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

    async def cancel_callback(self, interaction: discord.Interaction):
        """Apenas o Don (ou administrador) pode cancelar a votação."""
        user = interaction.user
        dados = poll_data.get(self.poll_id)
        if not dados:
            await interaction.response.send_message("⛔ This poll is no longer active.", ephemeral=True)
            return

        is_don = discord.utils.get(user.roles, name="Don") is not None
        if not (is_don or user.guild_permissions.administrator):
            await interaction.response.send_message("🛑 Apenas o Don pode cancelar uma votação.", ephemeral=True)
            return

        for channel_id, message_id in dados.get("mensagens", []):
            try:
                canal = interaction.client.get_channel(channel_id)
                if canal:
                    msg = await canal.fetch_message(message_id)
                    await msg.delete()
            except Exception as e:
                print(f"Erro ao apagar mensagem {message_id} no cancelamento: {e}")

        guild = interaction.guild
        await enviar_log_mafia(
            guild,
            f"🛑 Votação #{self.poll_id} Cancelada",
            f"Pergunta: **{dados['pergunta']}**\nCancelado por: {user.mention}",
            discord.Color.red()
        )

        poll_data.pop(self.poll_id, None)
        await interaction.response.send_message("🛑 Votação cancelada com sucesso. Todas as mensagens foram removidas.", ephemeral=True)


class VotacaoModal(discord.ui.Modal, title="Nova Votação da Cúpula"):
    pergunta = discord.ui.TextInput(
        label="Pergunta",
        placeholder="Ex.: Devemos declarar guerra?",
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=256
    )
    opcoes = discord.ui.TextInput(
        label="Opções (separadas por vírgula)",
        placeholder="Ex.: Sim, Não, Abstenção",
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=512
    )
    duracao = discord.ui.TextInput(
        label="Duração (horas)",
        placeholder="Ex.: 1.5 para 1h30min. Padrão 1h",
        style=discord.TextStyle.short,
        required=False,
        default="1"
    )

    def __init__(self, cog: "Votacoes"):
        super().__init__()
        self.cog = cog

    async def on_submit(self, interaction: discord.Interaction):
        pergunta = self.pergunta.value.strip()
        opcoes_str = self.opcoes.value.strip()
        duracao_str = self.duracao.value.strip() or "1"

        lista_opcoes = [op.strip() for op in opcoes_str.split(",") if op.strip()]
        if len(lista_opcoes) < 2:
            await interaction.response.send_message("⚠️ Precisas de pelo menos 2 opções.", ephemeral=True)
            return

        try:
            duracao = float(duracao_str.replace(",", "."))
            if duracao <= 0:
                raise ValueError
        except ValueError:
            await interaction.response.send_message("⚠️ Duração inválida. Insira um número positivo (ex.: 1.5).", ephemeral=True)
            return

        await self.cog.criar_votacao_modal(interaction, pergunta, lista_opcoes, duracao)


class Votacoes(commands.Cog):
    """Sistema de votações da Cúpula."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.loop_iniciado = False

    @commands.Cog.listener()
    async def on_ready(self):
        if not self.loop_iniciado:
            self.verificar_votacoes.start()
            self.loop_iniciado = True
            print("[VOTACOES] Loop de verificação iniciado.")

    def cog_unload(self):
        self.verificar_votacoes.cancel()

    @tasks.loop(seconds=30)
    async def verificar_votacoes(self):
        """Verifica periodicamente se há votações cujo prazo expirou e finaliza-as."""
        agora = discord.utils.utcnow()       
        polls_a_finalizar = []
        for poll_id, dados in poll_data.items():
            if "end_time" in dados:
                print(f"[VOTACOES]   Poll #{poll_id}: end_time={dados['end_time']} (agora={agora})")
                if dados["end_time"] <= agora:
                    polls_a_finalizar.append(poll_id)
                    print(f"[VOTACOES]   -> Poll #{poll_id} deve ser encerrada!")
        for poll_id in polls_a_finalizar:
            print(f"[VOTACOES] Chamando _finalizar_votacao para #{poll_id}")
            await self._finalizar_votacao(poll_id)

    async def _finalizar_votacao(self, poll_id: int):
        dados = poll_data.get(poll_id)
        if not dados:
            print(f"[VOTACOES] _finalizar_votacao: poll #{poll_id} não encontrada (já removida?)")
            return
        print(f"[VOTACOES] _finalizar_votacao: processando #{poll_id}...")

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
            end_time=dados["end_time"],
            final=True,
            lang=lang
        )

        for channel_id, message_id in dados["mensagens"]:
            try:
                canal = self.bot.get_channel(channel_id)
                if canal:
                    msg = await canal.fetch_message(message_id)
                    await msg.edit(embed=embed_final, view=None)
                    print(f"[VOTACOES]   Mensagem {message_id} editada com sucesso.")
            except Exception as e:
                print(f"[VOTACOES]   Erro ao editar mensagem {message_id}: {e}")

        guild = self.bot.get_guild(dados["guild_id"])
        if guild:
            await enviar_log_mafia(
                guild,
                f"🗳️ Votação #{poll_id} Encerrada",
                f"**{dados['pergunta']}**\nVotos: {total_votos}",
                discord.Color.blue()
            )

        del poll_data[poll_id]
        print(f"[VOTACOES]   Poll #{poll_id} removida da memória.")

    @app_commands.command(name="votacao", description="Abrir formulário para criar uma votação (Capos e Don)")
    async def abrir_modal_votacao(self, interaction: discord.Interaction):
        user = interaction.user
        is_capo = discord.utils.get(user.roles, name="Capo") is not None
        is_don = discord.utils.get(user.roles, name="Don") is not None
        if not (is_capo or is_don or user.guild_permissions.administrator):
            await interaction.response.send_message(
                "❌ Apenas **Capos** ou o **Don** podem criar votações.", ephemeral=True
            )
            return

        modal = VotacaoModal(self)
        await interaction.response.send_modal(modal)

    async def criar_votacao_modal(self, interaction: discord.Interaction, pergunta: str, opcoes: list, duracao: float):
        criador_locale = str(interaction.locale).split("-")[0] or "pt"
        guild = interaction.guild

        elegiveis_ids = set()
        for role_name in CARGOS_ELEGIVEIS:
            role = discord.utils.get(guild.roles, name=role_name)
            if role:
                elegiveis_ids.update(m.id for m in role.members)
        total_elegiveis = len(elegiveis_ids)

        end_time = discord.utils.utcnow() + timedelta(hours=duracao)

        poll_id = len(poll_data) + 1
        poll_data[poll_id] = {
            "pergunta": pergunta,
            "opcoes": opcoes,
            "duracao": duracao,
            "end_time": end_time,
            "votos": {},
            "mensagens": [],
            "elegiveis_ids": elegiveis_ids,
            "total_elegiveis": total_elegiveis,
            "criador": interaction.user.id,
            "guild_id": guild.id,
            "lang": criador_locale
        }

        embed_inicial = await build_embed_async(
            pergunta=pergunta,
            opcoes=opcoes,
            contagem={i: 0 for i in range(len(opcoes))},
            total_votos=0,
            end_time=end_time,
            final=False,
            lang=criador_locale
        )

        # Mensagem original
        view_original = VotacaoView(poll_id, opcoes, criador_id=interaction.user.id, lang=criador_locale)
        msg_original = await interaction.channel.send(embed=embed_inicial, view=view_original)
        poll_data[poll_id]["mensagens"].append((interaction.channel_id, msg_original.id))
        self.bot.add_view(view_original)

        # Propagação
        for familia_key, nome_familia in FAMILIAS.items():
            nome_cat = f"🍷 {nome_familia.upper()}"
            categoria = discord.utils.get(guild.categories, name=nome_cat)
            if categoria:
                canal_votacoes = discord.utils.get(categoria.text_channels, name="🗳️-votações")
                if canal_votacoes:
                    try:
                        view_fam = VotacaoView(poll_id, opcoes, criador_id=interaction.user.id, lang=criador_locale)
                        msg_fam = await canal_votacoes.send(embed=embed_inicial, view=view_fam)
                        poll_data[poll_id]["mensagens"].append((canal_votacoes.id, msg_fam.id))
                        self.bot.add_view(view_fam)
                    except Exception as e:
                        print(f"Erro ao propagar para {nome_familia}: {e}")

        confirm_msg = await translate("✅ Poll #{} started.\n📢 Propagated to {} families.\n⏳ Ends in {} hour(s).", criador_locale)
        await interaction.response.send_message(
            confirm_msg.format(poll_id, len(poll_data[poll_id]["mensagens"]) - 1, duracao),
            ephemeral=True
        )

        await enviar_log_mafia(
            guild,
            f"🗳️ Votação #{poll_id} Criada",
            f"**Criador:** {interaction.user.mention}\n"
            f"**Pergunta:** {pergunta}\n"
            f"**Duração:** {duracao} h\n"
            f"**Opções:** {', '.join(opcoes)}",
            discord.Color.blue()
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(Votacoes(bot))
