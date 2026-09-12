import asyncio
import discord
from discord import app_commands
from discord.ext import commands, tasks
from datetime import timedelta
from deep_translator import GoogleTranslator

# Cache de traduções
_t_cache = {}

async def translate(key: str, target: str) -> str:
    """Traduz um texto para o idioma de destino. Cache em memória."""
    if not key or not target or target == "pt":
        return key
    cache_key = (key, target)
    if cache_key in _t_cache:
        return _t_cache[cache_key]
    try:
        res = await asyncio.to_thread(
            GoogleTranslator(source='auto', target=target).translate, key
        )
        if res:
            _t_cache[cache_key] = res
            return res
        return key
    except Exception:
        return key


poll_data = {}
NUM_EMOJIS = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]


async def build_embed_async(pergunta, opcoes, contagem, total_votos,
                            end_time, final):
    """Constrói o embed da votação (inicial ou final)."""
    cor = discord.Color.from_rgb(0, 200, 255) if final else discord.Color.from_rgb(255, 200, 0)

    embed = discord.Embed(
        description=f"## Pergunta: {pergunta}",
        color=cor
    )

    # Lista de opções com contagem de votos
    linhas = []
    for i, op in enumerate(opcoes):
        emoji = NUM_EMOJIS[i] if i < len(NUM_EMOJIS) else "🔹"
        v = contagem.get(i, 0)
        if total_votos > 0:
            pct = (v / total_votos * 100)
            linhas.append(f"{emoji} **{op}** — `{v} voto(s)` ({pct:.0f}%)")
        else:
            linhas.append(f"{emoji} **{op}** — `0 votos`")

    titulo_opcoes = "📊 Resultados" if final else "📋 Opções"
    embed.add_field(name=titulo_opcoes, value="\n".join(linhas), inline=False)

    # Tempo relativo
    unix = int(end_time.timestamp())
    if final:
        embed.add_field(name="🗓️ Terminou", value=f"<t:{unix}:R>", inline=False)
    else:
        embed.add_field(name="🗓️ Termina em", value=f"<t:{unix}:R>", inline=False)

    # Total de votos no footer
    embed.set_footer(text=f"Total de votos: {total_votos}")

    return embed


async def build_translated_embed(pergunta: str, opcoes: list, end_time, lang: str):
    """Embed traduzida para mostrar em ephemeral ao utilizador."""
    pergunta_trad = await translate(pergunta, lang)
    cor = discord.Color.from_rgb(255, 200, 0)

    embed = discord.Embed(
        description=f"## {await translate('Question', lang)}: {pergunta_trad}",
        color=cor
    )

    unix = int(end_time.timestamp())
    embed.add_field(
        name="🗓️ " + await translate("Ends in", lang),
        value=f"<t:{unix}:R>",
        inline=False
    )

    linhas = []
    for i, opcao in enumerate(opcoes):
        opcao_trad = await translate(opcao, lang)
        emoji = NUM_EMOJIS[i] if i < len(NUM_EMOJIS) else "🔹"
        linhas.append(f"{emoji} {opcao_trad}")
    embed.add_field(
        name="📋 " + await translate("Options", lang),
        value="\n".join(linhas),
        inline=False
    )

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
            btn = discord.ui.Button(
                label=opcao[:80],
                style=discord.ButtonStyle.secondary,
                emoji=emoji,
                custom_id=f"voto_{poll_id}_{i}",
                row=i // 5
            )
            btn.callback = self.voto_callback
            self.add_item(btn)

        translate_btn = discord.ui.Button(
            label="Translate",
            style=discord.ButtonStyle.primary,
            emoji="🌍",
            custom_id=f"traduzir_poll_{poll_id}",
            row=2
        )
        translate_btn.callback = self.translate_callback
        self.add_item(translate_btn)

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

        dados = poll_data.get(poll_id)
        if not dados:
            await interaction.response.send_message(
                "⛔ Esta votação já fechou.", ephemeral=True
            )
            return

        custom_id = interaction.data["custom_id"]
        opcao_idx = int(custom_id.split("_")[-1])

        if user_id in dados["votos"]:
            antigo = dados["votos"][user_id]
            if antigo == opcao_idx:
                await interaction.response.send_message(
                    f"ℹ️ Já votaste em **{self.opcoes[opcao_idx]}**.", ephemeral=True
                )
                return
            else:
                dados["votos"][user_id] = opcao_idx
                await interaction.response.send_message(
                    f"🔄 Voto alterado de **{self.opcoes[antigo]}** para **{self.opcoes[opcao_idx]}**.",
                    ephemeral=True
                )
        else:
            dados["votos"][user_id] = opcao_idx
            await interaction.response.send_message(
                f"✅ Voto registado em **{self.opcoes[opcao_idx]}**.",
                ephemeral=True
            )

        # Atualiza a embed com a contagem atualizada
        contagem = {i: 0 for i in range(len(dados["opcoes"]))}
        for v in dados["votos"].values():
            if v in contagem:
                contagem[v] += 1
        total = len(dados["votos"])

        novo_embed = await build_embed_async(
            pergunta=dados["pergunta"],
            opcoes=dados["opcoes"],
            contagem=contagem,
            total_votos=total,
            end_time=dados["end_time"],
            final=False
        )

        try:
            await interaction.message.edit(embed=novo_embed)
        except Exception as e:
            print(f"[VOTACOES] Erro ao editar embed apos voto: {e}")

    async def translate_callback(self, interaction: discord.Interaction):
        """Mostra ao utilizador uma versão traduzida da votação (só ele vê)."""
        poll_id = self.poll_id
        dados = poll_data.get(poll_id)
        if not dados:
            await interaction.response.send_message(
                "⛔ Esta votação já fechou.", ephemeral=True
            )
            return

        user_locale = str(interaction.locale or "en").split("-")[0]

        # Se o idioma for PT, não vale a pena traduzir
        if user_locale == "pt":
            await interaction.response.send_message(
                "ℹ️ A votação já está em português.",
                ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        embed_trad = await build_translated_embed(
            pergunta=dados["pergunta"],
            opcoes=dados["opcoes"],
            end_time=dados["end_time"],
            lang=user_locale
        )

        await interaction.followup.send(
            content="🌍 Here's the poll translated for you:",
            embed=embed_trad,
            ephemeral=True
        )

    async def cancel_callback(self, interaction: discord.Interaction):
        """Apenas administradores podem cancelar."""
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "🛑 Apenas administradores podem cancelar uma votação.",
                ephemeral=True
            )
            return

        dados = poll_data.get(self.poll_id)
        if not dados:
            await interaction.response.send_message(
                "⛔ Esta votação já não está ativa.", ephemeral=True
            )
            return

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
            "🛑 Votação cancelada.", ephemeral=True
        )


class VotacaoModal(discord.ui.Modal, title="Nova Votação"):
    pergunta = discord.ui.TextInput(
        label="Pergunta",
        placeholder="Ex.: Qual é a melhor classe?",
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=256
    )
    opcoes = discord.ui.TextInput(
        label="Opções (separadas por vírgula)",
        placeholder="Ex.: Gladiator, Sorcerer, Cleric",
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
            await interaction.response.send_message(
                "⚠️ Precisas de pelo menos 2 opções.", ephemeral=True
            )
            return

        try:
            duracao = float(duracao_str.replace(",", "."))
            if duracao <= 0:
                raise ValueError
        except ValueError:
            await interaction.response.send_message(
                "⚠️ Duração inválida. Usa um número positivo (ex.: 1.5).",
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

        embed_final = await build_embed_async(
            pergunta=dados["pergunta"],
            opcoes=dados["opcoes"],
            contagem=contagem,
            total_votos=total_votos,
            end_time=dados["end_time"],
            final=True
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

    @app_commands.command(name="votacao", description="Criar uma votação neste canal (Apenas Administradores)")
    @app_commands.checks.has_permissions(administrator=True)
    async def abrir_modal_votacao(self, interaction: discord.Interaction):
        modal = VotacaoModal(self)
        await interaction.response.send_modal(modal)

    async def criar_votacao(self, interaction: discord.Interaction,
                            pergunta: str, opcoes: list, duracao: float):
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
        }

        embed_inicial = await build_embed_async(
            pergunta=pergunta,
            opcoes=opcoes,
            contagem={i: 0 for i in range(len(opcoes))},
            total_votos=0,
            end_time=end_time,
            final=False
        )

        view = VotacaoView(poll_id, opcoes, criador_id=interaction.user.id)
        msg = await interaction.channel.send(embed=embed_inicial, view=view)
        poll_data[poll_id]["mensagens"].append((interaction.channel_id, msg.id))
        self.bot.add_view(view)

        await interaction.response.send_message(
            f"✅ Votação #{poll_id} criada neste canal. Termina em {duracao}h.",
            ephemeral=True
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(Votacoes(bot))
