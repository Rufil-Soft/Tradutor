import asyncio
import discord
from discord import app_commands
from discord.ext import commands, tasks
from datetime import timedelta
from deep_translator import GoogleTranslator

# Cache de traduções para os títulos dos embeds
_t_cache = {}

async def translate(key: str, target: str) -> str:
    if target == "pt":
        return key
    cache_key = (key, target)
    if cache_key in _t_cache:
        return _t_cache[cache_key]
    try:
        res = await asyncio.to_thread(
            GoogleTranslator(source='auto', target=target).translate, key
        )
        _t_cache[cache_key] = res
        return res
    except Exception:
        return key


poll_data = {}
NUM_EMOJIS = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]


async def build_embed_async(pergunta, opcoes, contagem, total_votos,
                            end_time, final, lang):
    """Constrói o embed da votação (inicial ou final)."""
    if final:
        titulo = await translate("📊 Poll · Result", lang)
        cor = discord.Color.from_rgb(0, 200, 255)
    else:
        titulo = await translate("📡 Poll · Vote Now", lang)
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
        embed.add_field(
            name="🏆 " + await translate("Winner", lang),
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
            name="⚠️ " + await translate("No votes", lang),
            value=await translate("No votes were cast.", lang),
            inline=False
        )

    return embed


class VotacaoView(discord.ui.View):
    def __init__(self, poll_id: int, opcoes: list, criador_id: int, lang: str = "en"):
        super().__init__(timeout=None)
        self.poll_id = poll_id
        self.opcoes = opcoes
        self.criador_id = criador_id
        self.lang = lang

        for i, opcao in enumerate(opcoes):
            emoji = NUM_EMOJIS[i] if i < len(NUM_EMOJIS) else "🔹"
            btn = discord.ui.Button(
                label=opcao[:80],
                style=discord.ButtonStyle.secondary,
                emoji=emoji,
                custom_id=f"voto_{poll_id}_{i}",
                row=i // 5
            )
            btn.callback = self.voto_callback
            self.add_item(btn)

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
        user_locale = str(interaction.locale or "en").split("-")[0]

        dados = poll_data.get(poll_id)
        if not dados:
            await interaction.response.send_message(
                await translate("⛔ This poll has closed.", user_locale),
                ephemeral=True
            )
            return

        custom_id = interaction.data["custom_id"]
        opcao_idx = int(custom_id.split("_")[-1])

        if user_id in dados["votos"]:
            antigo = dados["votos"][user_id]
            if antigo == opcao_idx:
                msg = await translate("ℹ️ You already voted for {}.", user_locale)
                await interaction.response.send_message(
                    msg.format(self.opcoes[opcao_idx]), ephemeral=True
                )
                return
            else:
                dados["votos"][user_id] = opcao_idx
                msg = await translate("🔄 Vote changed from {} to {}.", user_locale)
                await interaction.response.send_message(
                    msg.format(self.opcoes[antigo], self.opcoes[opcao_idx]),
                    ephemeral=True
                )
        else:
            dados["votos"][user_id] = opcao_idx
            msg = await translate("✅ Vote registered for {}.", user_locale)
            await interaction.response.send_message(
                msg.format(self.opcoes[opcao_idx]), ephemeral=True
            )

    async def cancel_callback(self, interaction: discord.Interaction):
        """Apenas administradores podem cancelar."""
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "🛑 Only administrators can cancel a poll.",
                ephemeral=True
            )
            return

        dados = poll_data.get(self.poll_id)
        if not dados:
            await interaction.response.send_message(
                "⛔ This poll is no longer active.", ephemeral=True
            )
            return

        # Apaga a mensagem da votação
        for channel_id, message_id in dados["mensagens"]:
            try:
                canal = interaction.client.get_channel(channel_id)
                if canal:
                    msg = await canal.fetch_message(message_id)
                    await msg.delete()
            except Exception as e:
                print(f"[VOTACOES] Erro ao apagar mensagem {message_id}: {e}")

        poll_data.pop(self.poll_id, None)
        await interaction.response.send_message(
            "🛑 Poll cancelled.", ephemeral=True
        )


class VotacaoModal(discord.ui.Modal, title="New Poll"):
    pergunta = discord.ui.TextInput(
        label="Question",
        placeholder="Ex.: Which class is the best?",
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=256
    )
    opcoes = discord.ui.TextInput(
        label="Options (separated by comma)",
        placeholder="Ex.: Gladiator, Sorcerer, Cleric",
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=512
    )
    duracao = discord.ui.TextInput(
        label="Duration (hours)",
        placeholder="Ex.: 1.5 for 1h30m. Default 1h",
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
            await interaction.response.send_message(
                "⚠️ You need at least 2 options.", ephemeral=True
            )
            return

        try:
            duracao = float(duracao_str.replace(",", "."))
            if duracao <= 0:
                raise ValueError
        except ValueError:
            await interaction.response.send_message(
                "⚠️ Invalid duration. Use a positive number (e.g. 1.5).",
                ephemeral=True
            )
            return

        await self.cog.criar_votacao(interaction, pergunta, lista_opcoes, duracao)


class Votacoes(commands.Cog):
    """Sistema de votações simples, apenas no canal onde o comando é usado."""

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
        agora = discord.utils.utcnow()
        expiradas = [
            poll_id for poll_id, dados in poll_data.items()
            if dados.get("end_time") and dados["end_time"] <= agora
        ]
        for poll_id in expiradas:
            await self._finalizar_votacao(poll_id)

    async def _finalizar_votacao(self, poll_id: int):
        dados = poll_data.get(poll_id)
        if not dados:
            return

        contagem = {i: 0 for i in range(len(dados["opcoes"]))}
        for v in dados["votos"].values():
            if v in contagem:
                contagem[v] += 1
        total_votos = len(dados["votos"])
        lang = dados.get("lang", "en")

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
            except Exception as e:
                print(f"[VOTACOES] Erro ao editar mensagem {message_id}: {e}")

        del poll_data[poll_id]
        print(f"[VOTACOES] Poll #{poll_id} finalizada e removida.")

    @app_commands.command(name="votacao", description="Create a poll in this channel")
    @app_commands.checks.has_permissions(administrator=True)
    async def abrir_modal_votacao(self, interaction: discord.Interaction):
        modal = VotacaoModal(self)
        await interaction.response.send_modal(modal)

    async def criar_votacao(self, interaction: discord.Interaction,
                            pergunta: str, opcoes: list, duracao: float):
        criador_locale = str(interaction.locale or "en").split("-")[0]
        guild = interaction.guild
        end_time = discord.utils.utcnow() + timedelta(hours=duracao)

        poll_id = len(poll_data) + 1
        poll_data[poll_id] = {
            "pergunta": pergunta,
            "opcoes": opcoes,
            "duracao": duracao,
            "end_time": end_time,
            "votos": {},
            "mensagens": [],
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

        view = VotacaoView(poll_id, opcoes, criador_id=interaction.user.id,
                           lang=criador_locale)
        msg = await interaction.channel.send(embed=embed_inicial, view=view)
        poll_data[poll_id]["mensagens"].append((interaction.channel_id, msg.id))
        self.bot.add_view(view)

        await interaction.response.send_message(
            f"✅ Poll #{poll_id} created in this channel. Ends in {duracao}h.",
            ephemeral=True
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(Votacoes(bot))
