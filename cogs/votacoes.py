import asyncio
import discord
from discord import app_commands
from discord.ext import commands
from deep_translator import GoogleTranslator
from config import FAMILIAS, CARGOS_ELEGIVEIS
from cogs.logs import enviar_log_mafia

poll_data = {}
NUM_EMOJIS = ["1️⃣","2️⃣","3️⃣","4️⃣","5️⃣","6️⃣","7️⃣","8️⃣","9️⃣","🔟"]

# Cache para traduções
trans_cache = {}

async def t(text: str, lang: str) -> str:
    """Traduz `text` para `lang` (código ISO de 2 letras) com cache."""
    if lang == "pt":
        return text
    key = (text, lang)
    if key in trans_cache:
        return trans_cache[key]
    try:
        res = await asyncio.to_thread(GoogleTranslator(source='auto', target=lang).translate, text)
        trans_cache[key] = res
        return res
    except:
        return text

def build_resultado_embed(pergunta: str, opcoes: list, contagem: dict, total_votos: int,
                          duracao: int, final: bool = False, elegiveis: int = 0,
                          lang: str = "pt") -> discord.Embed:
    """Embed profissional com tradução dos textos estáticos."""
    # Textos base (podem ser traduzidos)
    if final:
        titulo = asyncio.run(t("🏛️ SYSTEM COUNCIL // FINAL RESULT", lang))  # vamos mudar para async
        cor = discord.Color.from_rgb(0, 240, 255)
        status = asyncio.run(t("CLOSED", lang))
    else:
        titulo = asyncio.run(t("📡 SYSTEM COUNCIL // LIVE VOTE", lang))
        cor = discord.Color.gold()
        status = asyncio.run(t("ACTIVE", lang))
    # Nota: usar asyncio.run aqui não é ideal, mas como build_embed é chamado dentro de um async,
    # vamos converter a função para async e usar await.
    # A correção: tornar build_resultado_embed async.
    ...

# ... (vou refazer a função como async)

async def build_resultado_embed_async(pergunta: str, opcoes: list, contagem: dict, total_votos: int,
                                      duracao: int, final: bool, elegiveis: int, lang: str) -> discord.Embed:
    if final:
        titulo = await t("🏛️ SYSTEM COUNCIL // FINAL RESULT", lang)
        cor = discord.Color.from_rgb(0, 240, 255)
        status = await t("CLOSED", lang)
        status_line = f"```yaml\n{await t('QUESTION:', lang)} {pergunta}\n{await t('DURATION:', lang)} {duracao} min\n{await t('STATUS:', lang)} {status}\n```"
    else:
        titulo = await t("📡 SYSTEM COUNCIL // LIVE VOTE", lang)
        cor = discord.Color.gold()
        status = await t("ACTIVE", lang)
        status_line = f"```yaml\n{await t('QUESTION:', lang)} {pergunta}\n{await t('DURATION:', lang)} {duracao} min\n{await t('STATUS:', lang)} {status}\n```"

    embed = discord.Embed(title=titulo, description=status_line, color=cor, timestamp=discord.utils.utcnow())

    if final and total_votos > 0:
        vencedor_idx = max(contagem, key=contagem.get)
        vencedor_txt = opcoes[vencedor_idx]
        embed.add_field(name=await t("🏆 WINNING DECISION", lang),
                        value=f"```fix\n{vencedor_txt.upper()} ({contagem[vencedor_idx]} {await t('votos', lang)})\n```",
                        inline=False)
    elif final and total_votos == 0:
        embed.add_field(name=await t("⚠️ NO QUORUM", lang),
                        value="```diff\n- Nenhum voto registado.\n```", inline=False)

    linhas = []
    for idx, opcao in enumerate(opcoes):
        v = contagem.get(idx, 0)
        pct = (v / total_votos * 100) if total_votos else 0
        barra = "▓" * int(pct/10) + "░" * (10 - int(pct/10))
        linhas.append(f"`{barra}` **{pct:.1f}%** ── **{opcao}** `({v}v)`")
    embed.add_field(name=await t("📊 VOTE DISTRIBUTION", lang), value="\n".join(linhas) if linhas else await t("No votes yet.", lang), inline=False)

    if elegiveis > 0:
        taxa = (total_votos / elegiveis * 100) if elegiveis else 0
        metricas = f"```ini\n[{await t('Registered Votes', lang)}] : {total_votos}\n[{await t('Eligible Members', lang)}] : {elegiveis}\n[{await t('Turnout', lang)}]   : {taxa:.1f}%\n```"
        embed.add_field(name=await t("⚙️ QUORUM METRICS", lang), value=metricas, inline=False)

    embed.set_footer(text="Omertà • Council System")
    return embed

# A classe VotacaoView mantém-se, mas no callback usamos tradução para a resposta efémera.
class VotacaoView(discord.ui.View):
    def __init__(self, poll_id, opcoes, lang="pt"):
        super().__init__(timeout=None)
        self.poll_id = poll_id
        self.opcoes = opcoes
        self.lang = lang  # idioma do criador, para os botões (opções mantêm-se na língua original)

        for i, opcao in enumerate(opcoes):
            emoji = NUM_EMOJIS[i] if i < len(NUM_EMOJIS) else "🔹"
            botao = discord.ui.Button(
                label=opcao[:80],  # opção original, não traduzida
                style=discord.ButtonStyle.secondary,
                emoji=emoji,
                custom_id=f"voto_{poll_id}_{i}",
                row=i // 5
            )
            botao.callback = self.voto_callback
            self.add_item(botao)

    async def voto_callback(self, interaction: discord.Interaction):
        poll_id = self.poll_id
        user_id = interaction.user.id
        user_locale = str(interaction.locale).split("-")[0] or "pt"

        dados = poll_data.get(poll_id)
        if not dados:
            await interaction.response.send_message(await t("⛔ This poll has closed.", user_locale), ephemeral=True)
            return

        # Extrair opção escolhida
        _, _, idx_str = interaction.data["custom_id"].partition("_")[-1].rpartition("_")
        opcao_idx = int(idx_str)

        # Verifica elegibilidade
        if user_id not in dados.get("elegiveis_ids", set()):
            await interaction.response.send_message(await t("🔒 You are not eligible to vote.", user_locale), ephemeral=True)
            return

        if user_id in dados["votos"]:
            antigo = dados["votos"][user_id]
            if antigo == opcao_idx:
                txt = await t("ℹ️ You already voted for {}.", user_locale)
                await interaction.response.send_message(txt.format(self.opcoes[opcao_idx]), ephemeral=True)
                return
            else:
                dados["votos"][user_id] = opcao_idx
                txt = await t("🔄 Vote changed from {} to {}.", user_locale)
                await interaction.response.send_message(txt.format(self.opcoes[antigo], self.opcoes[opcao_idx]), ephemeral=True)
        else:
            dados["votos"][user_id] = opcao_idx
            txt = await t("✅ Vote registered for {}. The Council thanks your loyalty.", user_locale)
            await interaction.response.send_message(txt.format(self.opcoes[opcao_idx]), ephemeral=True)

# Comando /votacao adaptado
class Votacoes(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="votacao", description="Convoca uma votação oficial da Cúpula")
    @app_commands.default_permissions(administrator=True)
    async def criar_votacao(self, interaction: discord.Interaction, pergunta: str, opcoes: str, duracao: int = 10):
        await interaction.response.defer(ephemeral=True)

        # Define idioma base: o locale do utilizador que criou
        criador_locale = str(interaction.locale).split("-")[0] or "pt"
        lista_opcoes = [op.strip() for op in opcoes.split(",") if op.strip()]
        if len(lista_opcoes) < 2:
            await interaction.followup.send(await t("⚠️ Need at least 2 options.", criador_locale), ephemeral=True)
            return
        if duracao < 1:
            await interaction.followup.send(await t("⚠️ Minimum duration is 1 minute.", criador_locale), ephemeral=True)
            return

        poll_id = len(poll_data) + 1
        guild = interaction.guild

        # Determinar elegíveis
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
            "lang": criador_locale  # guardamos para o resultado final
        }

        # Embed inicial traduzido
        embed_inicial = await build_resultado_embed_async(
            pergunta=pergunta,
            opcoes=lista_opcoes,
            contagem={i:0 for i in range(len(lista_opcoes))},
            total_votos=0,
            duracao=duracao,
            final=False,
            elegiveis=total_elegiveis,
            lang=criador_locale
        )

        view_original = VotacaoView(poll_id, lista_opcoes, lang=criador_locale)
        msg_original = await interaction.channel.send(embed=embed_inicial, view=view_original)
        poll_data[poll_id]["mensagens"].append((interaction.channel_id, msg_original.id))

        # Propagar
        for familia_key, nome_familia in FAMILIAS.items():
            nome_cat = f"🍷 {nome_familia.upper()}"
            categoria = discord.utils.get(guild.categories, name=nome_cat)
            if categoria:
                canal = discord.utils.get(categoria.text_channels, name="🗳️-votações")
                if canal:
                    try:
                        view_fam = VotacaoView(poll_id, lista_opcoes, lang=criador_locale)
                        msg_fam = await canal.send(embed=embed_inicial, view=view_fam)
                        poll_data[poll_id]["mensagens"].append((canal.id, msg_fam.id))
                    except Exception as e:
                        print(f"Erro propagação: {e}")

        await interaction.followup.send(
            await t("✅ Poll #{} started.\n📢 Propagated to {} families.\n⏳ Ends in {} min(s).", criador_locale).format(poll_id, len(poll_data[poll_id]['mensagens'])-1, duracao),
            ephemeral=True
        )

        asyncio.create_task(self.finalizar_votacao(poll_id, duracao * 60))

    async def finalizar_votacao(self, poll_id, delay):
        await asyncio.sleep(delay)
        dados = poll_data.get(poll_id)
        if not dados:
            return
        contagem = {i:0 for i in range(len(dados["opcoes"]))}
        for v in dados["votos"].values():
            if v in contagem:
                contagem[v] += 1
        total_votos = len(dados["votos"])

        # Embed final usando o idioma do criador
        lang = dados.get("lang", "pt")
        embed_final = await build_resultado_embed_async(
            pergunta=dados["pergunta"],
            opcoes=dados["opcoes"],
            contagem=contagem,
            total_votos=total_votos,
            duracao=dados["duracao"],
            final=True,
            elegiveis=dados.get("total_elegiveis",0),
            lang=lang
        )

        for channel_id, message_id in dados["mensagens"]:
            try:
                canal = self.bot.get_channel(channel_id)
                if canal:
                    msg = await canal.fetch_message(message_id)
                    await msg.edit(embed=embed_final, view=None)
            except:
                pass

        guild = self.bot.get_guild(dados["guild_id"])
        if guild:
            await enviar_log_mafia(guild, f"🗳️ Poll #{poll_id} closed", f"Question: {dados['pergunta']}\nVotes: {total_votos}", discord.Color.blue())

        poll_data.pop(poll_id, None)

async def setup(bot):
    await bot.add_cog(Votacoes(bot))
