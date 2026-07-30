import os
import asyncio
import discord
from discord.ext import commands
from deep_translator import GoogleTranslator
from aiohttp import web
from datetime import timedelta
from collections import defaultdict

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.polls = True  # necessário para on_raw_poll_vote_add / on_raw_poll_vote_remove

bot = commands.Bot(command_prefix="!", intents=intents)

FAMILIAS = {
    "corleone": "Família Corleone",
    "gambino": "Família Gambino",
    "genovese": "Família Genovese",
    "lucchese": "Família Lucchese",
    "bonanno": "Família Bonanno"
}
LIMITE_SOLDIERS = 20

# --- REGISTO DE VOTAÇÕES ATIVAS (AGREGAÇÃO ENTRE FAMÍLIAS) ---
# poll_groups[group_id] = {
#     "pergunta": str,
#     "opcoes": [str, ...],
#     "votos": {indice_opcao: contagem},
#     "canal_central_id": int,
#     "embed_message_id": int | None,
#     "member_polls": {message_id: {"familia": str, "answer_map": {answer_id: indice_opcao}}}
# }
poll_groups = {}
message_to_group = {}  # message_id (de qualquer poll de família) -> group_id


def build_resultado_embed(grupo: dict) -> discord.Embed:
    total = sum(grupo["votos"].values())
    embed = discord.Embed(
        title=f"📊 Resultado Agregado — {grupo['pergunta']}",
        color=discord.Color.dark_gold(),
        timestamp=discord.utils.utcnow()
    )
    for idx, opcao in enumerate(grupo["opcoes"]):
        votos = grupo["votos"].get(idx, 0)
        pct = (votos / total * 100) if total else 0
        barra_len = int(pct / 5)
        barra = "█" * barra_len + "░" * (20 - barra_len)
        embed.add_field(name=opcao, value=f"`{barra}` **{votos}** votos ({pct:.1f}%)", inline=False)
    familias_txt = ", ".join(
        v["familia"] for v in grupo["member_polls"].values()
    ) or "Nenhuma"
    embed.set_footer(text=f"Total de votos: {total} • Famílias: {familias_txt}")
    return embed


async def atualizar_embed_central(group_id: str):
    grupo = poll_groups.get(group_id)
    if not grupo or not grupo.get("embed_message_id"):
        return
    canal = bot.get_channel(grupo["canal_central_id"])
    if not canal:
        return
    try:
        msg = await canal.fetch_message(grupo["embed_message_id"])
        await msg.edit(embed=build_resultado_embed(grupo))
    except (discord.NotFound, discord.Forbidden, discord.HTTPException) as e:
        print(f"[VOTACAO] Erro ao atualizar embed central: {e}")


def limpar_grupo(group_id: str):
    grupo = poll_groups.pop(group_id, None)
    if not grupo:
        return
    for message_id in grupo["member_polls"].keys():
        message_to_group.pop(message_id, None)


# --- SERVIDOR WEB DUMMY PARA O RENDER NÃO DAR TIMEOUT DE PORTA ---
async def handle_ping(request):
    return web.Response(text="Bot Máfia Online!")

async def start_dummy_server():
    app = web.Application()
    app.router.add_get("/", handle_ping)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.getenv("PORT", 10000))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    print(f"Servidor Web ativo na porta {port} (Render Keep-Alive)")


# --- TRADUÇÃO VIA MENU DE CONTEXTO ---
@bot.tree.context_menu(name="Traduzir Mensagem")
async def traduzir_context(interaction: discord.Interaction, message: discord.Message):
    await interaction.response.defer(ephemeral=True)
    if not message.content:
        await interaction.followup.send("Esta mensagem não tem texto para traduzir.", ephemeral=True)
        return
    user_locale = str(interaction.locale).split("-")[0]
    print(f"[TRADUTOR] A traduzir para locale='{user_locale}' (original interaction.locale='{interaction.locale}')")
    try:
        translated = await asyncio.to_thread(
            GoogleTranslator(source='auto', target=user_locale).translate,
            message.content
        )
        if not translated:
            print("[TRADUTOR] GoogleTranslator devolveu resultado vazio.")
            await interaction.followup.send("Não foi possível obter tradução (resultado vazio).", ephemeral=True)
            return
        await interaction.followup.send(f"🔠 **Tradução ({user_locale.upper()}):**\n{translated}", ephemeral=True)
    except Exception as e:
        print(f"[TRADUTOR] Erro ao traduzir: {type(e).__name__}: {e}")
        await interaction.followup.send(f"Erro ao traduzir mensagem: `{type(e).__name__}`", ephemeral=True)


# --- LOGS DA MÁFIA ---
async def enviar_log_mafia(guild: discord.Guild, titulo: str, descricao: str, cor: discord.Color):
    try:
        canal_log = discord.utils.get(guild.text_channels, name="🕶️-mafia-logs")
        if canal_log:
            embed = discord.Embed(title=titulo, description=descricao, color=cor, timestamp=discord.utils.utcnow())
            embed.set_footer(text="Máfia System • Registro de Lealdade")
            await canal_log.send(embed=embed)
    except Exception as e:
        print(f"Erro ao enviar log da máfia: {e}")


# --- PAINEL DOS RANKS (#setup_ranks) ---
class RanksView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Read Ranks in my language", style=discord.ButtonStyle.secondary, emoji="🌐", custom_id="translate_ranks", row=0)
    async def translate_ranks(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        user_locale = str(interaction.locale).split("-")[0]
        ranks_texto = (
            "🏛️ **ORGANIZATION & HIERARCHY — COSA NOSTRA**\n\n"
            "\"In our family, there is no room for freelancers. Every man has his place, his duty, and his weight on the scales of power.\"\n\n"
            "🎩 **1. THE DON (The Boss)**\n"
            "The top of the pyramid. The Don commands the destiny of all Families, arbitrates territorial disputes, and maintains peace or declares war.\n\n"
            "🍷 **2. CAPOREGIME / CAPO (The Regime Leader)**\n"
            "The commander of each Family (Corleone, Gambino, Genovese, Lucchese, Bonanno).\n"
            "• Only 1 Capo per Family.\n"
            "• Leads their own private HQ and commands up to 20 Soldiers.\n"
            "• Responsible for discipline and territory strategy.\n\n"
            "🗡️ **3. SOLDIER (The Man of Honor)**\n"
            "The armed and loyal arm of the Family.\n"
            "• Strict limit of 20 Soldiers per Family.\n"
            "• Can only enlist in Families that already have an active Capo.\n"
            "• Responds exclusively to their Capo's chain of command.\n\n"
            "🕶️ **4. STAFF / AUDITORS**\n"
            "The guardians of the system and neutrality. They ensure Omertà rules are followed and audit operations.\n\n"
            "📜 **THE CODE OF CONDUCT (OMERTÀ)**\n"
            "• Absolute Loyalty: A given word is a blood contract.\n"
            "• Silence: Family business never leaves the walls of the HQ.\n"
            "• Hierarchical Respect: The subordinate obeys, the leader decides."
        )
        try:
            translated = await asyncio.to_thread(GoogleTranslator(source='auto', target=user_locale).translate, ranks_texto)
            await interaction.followup.send(translated, ephemeral=True)
        except Exception as e:
            print(f"[TRADUTOR] Erro no painel de ranks: {type(e).__name__}: {e}")
            await interaction.followup.send(ranks_texto, ephemeral=True)


# --- PAINEL DOS CAPOS (#capo-registry) ---
class CapoRegistryView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Read Omertà in my language", style=discord.ButtonStyle.secondary, emoji="🌐", custom_id="translate_omerta_capo", row=0)
    async def translate_omerta(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        user_locale = str(interaction.locale).split("-")[0]
        pacto_texto = (
            "📜 **O PACTO DE OMERTÀ DOS CAPOS**\n\n"
            "1. **Lealdade Absoluta:** As tuas ordens vêm do Don e dos Capodecinas. A tua palavra é a lei para os teus 20 Soldados.\n"
            "2. **Proteção:** És a espada e o escudo dos teus homens. Se um cai, a Família responde.\n"
            "3. **Silêncio:** O que é falado na administração da Família morre na tumba. Traidores não têm segunda oportunidade.\n\n"
            "⚠️ *Reivindica a tua Família abaixo. Apenas 1 Capo por Família.*"
        )
        try:
            translated = await asyncio.to_thread(GoogleTranslator(source='auto', target=user_locale).translate, pacto_texto)
            await interaction.followup.send(translated, ephemeral=True)
        except Exception as e:
            print(f"[TRADUTOR] Erro no painel de capos: {type(e).__name__}: {e}")
            await interaction.followup.send(pacto_texto, ephemeral=True)

    async def handle_capo_claim(self, interaction: discord.Interaction, familia_key: str):
        guild = interaction.guild
        member = interaction.user
        cargo_capo = discord.utils.get(guild.roles, name="Capo")
        if cargo_capo not in member.roles:
            await interaction.response.send_message("❌ Apenas membros com a patente de **Capo** podem reivindicar uma Família!", ephemeral=True)
            return
        nome_familia = FAMILIAS[familia_key]
        cargo_familia = discord.utils.get(guild.roles, name=nome_familia)
        if not cargo_familia:
            await interaction.response.send_message(f"❌ O cargo **{nome_familia}** não existe no servidor. Cria-o nas configurações do Discord.", ephemeral=True)
            return
        for m in list(cargo_familia.members):
            if cargo_capo not in m.roles:
                try:
                    await m.remove_roles(cargo_familia)
                except Exception:
                    pass
        capos_na_familia = [m for m in cargo_familia.members if cargo_capo in m.roles]
        if len(capos_na_familia) > 0:
            await interaction.response.send_message(f"⚠️ A **{nome_familia}** já tem um Capo ativo a liderá-la ({capos_na_familia[0].display_name})!", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        try:
            await member.add_roles(cargo_familia)
            nome_cat = f"🍷 {nome_familia.upper()}"
            categoria = discord.utils.get(guild.categories, name=nome_cat)
            overwrites_base = {
                guild.default_role: discord.PermissionOverwrite(read_messages=False),
                cargo_familia: discord.PermissionOverwrite(read_messages=True, send_messages=True, read_message_history=True, connect=True)
            }
            if not categoria:
                categoria = await guild.create_category(nome_cat, overwrites=overwrites_base)
            # Canal Anúncios
            canal_anuncios = discord.utils.get(categoria.text_channels, name="📜-capo-announcements")
            if not canal_anuncios:
                overwrites_announcements = {
                    guild.default_role: discord.PermissionOverwrite(read_messages=False),
                    cargo_familia: discord.PermissionOverwrite(read_messages=True, send_messages=False),
                    cargo_capo: discord.PermissionOverwrite(read_messages=True, send_messages=True)
                }
                await guild.create_text_channel("📜-capo-announcements", category=categoria, overwrites=overwrites_announcements, topic=f"Official announcements for {nome_familia}.")
            # Canal Warnings
            canal_warnings = discord.utils.get(categoria.text_channels, name="🚨-warnings")
            overwrites_warnings = {
                guild.default_role: discord.PermissionOverwrite(read_messages=False),
                cargo_familia: discord.PermissionOverwrite(read_messages=False),
                member: discord.PermissionOverwrite(read_messages=True, send_messages=False, read_message_history=True)
            }
            if not canal_warnings:
                await guild.create_text_channel("🚨-warnings", category=categoria, overwrites=overwrites_warnings, topic=f"Canal de warnings vindos da Cúpula exclusivo para o Capo da {nome_familia}.")
            else:
                await canal_warnings.set_permissions(member, read_messages=True, send_messages=False, read_message_history=True)
            # Canal Votações
            canal_votacoes = discord.utils.get(categoria.text_channels, name="🗳️-votações")
            if not canal_votacoes:
                overwrites_votacoes = {
                    guild.default_role: discord.PermissionOverwrite(read_messages=False),
                    cargo_familia: discord.PermissionOverwrite(read_messages=True, send_messages=True, read_message_history=True)
                }
                await guild.create_text_channel("🗳️-votações", category=categoria, overwrites=overwrites_votacoes, topic=f"Canal de votações oficiais para a {nome_familia}.")
            # Chat Geral
            canal_chat = discord.utils.get(categoria.text_channels, name="💬-general-chat")
            if not canal_chat:
                await guild.create_text_channel("💬-general-chat", category=categoria, topic=f"Secret HQ text chat for {nome_familia}.")
            # Sala de Voz
            canal_voz = discord.utils.get(categoria.voice_channels, name="📢-meeting-room")
            if not canal_voz:
                await guild.create_voice_channel("📢-meeting-room", category=categoria)
            await interaction.followup.send(
                f"🍷 **Honra e Lealdade!** Assumiste o comando da **{nome_familia}**!\n📂 QG configurado com sucesso!", ephemeral=True
            )
            await enviar_log_mafia(guild, "🍷 NOVO CAPO & QG CRIADO", f"{member.mention} assumiu a liderança da **{nome_familia}** e ativou o QG privado da Família!", discord.Color.gold())
        except discord.Forbidden:
            await interaction.followup.send("❌ O bot não tem permissões para gerenciar cargos/canais. Garante que o bot tem a permissão de Administrador.", ephemeral=True)

    @discord.ui.button(label="Corleone", style=discord.ButtonStyle.primary, emoji="🍷", custom_id="capo_corleone", row=1)
    async def capo_corleone(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_capo_claim(interaction, "corleone")
    @discord.ui.button(label="Gambino", style=discord.ButtonStyle.primary, emoji="🍷", custom_id="capo_gambino", row=1)
    async def capo_gambino(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_capo_claim(interaction, "gambino")
    @discord.ui.button(label="Genovese", style=discord.ButtonStyle.primary, emoji="🍷", custom_id="capo_genovese", row=1)
    async def capo_genovese(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_capo_claim(interaction, "genovese")
    @discord.ui.button(label="Lucchese", style=discord.ButtonStyle.primary, emoji="🍷", custom_id="capo_lucchese", row=2)
    async def capo_lucchese(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_capo_claim(interaction, "lucchese")
    @discord.ui.button(label="Bonanno", style=discord.ButtonStyle.primary, emoji="🍷", custom_id="capo_bonanno", row=2)
    async def capo_bonanno(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_capo_claim(interaction, "bonanno")


# --- PAINEL DOS SOLDIERS (#soldier-enlistment) ---
class SoldierEnlistView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Read Omertà in my language", style=discord.ButtonStyle.secondary, emoji="🌐", custom_id="translate_omerta_soldier", row=0)
    async def translate_omerta(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        user_locale = str(interaction.locale).split("-")[0]
        pacto_texto = (
            "📜 **O PACTO DE OMERTÀ DOS SOLDADOS**\n\n"
            "1. **Silêncio Absoluto (Omertà):** Nunca fales sobre negócios da Família com autoridades ou rivais. A língua solta encomenda o teu caixão.\n"
            "2. **Cadeia de Comando:** Tu só respondes ao Capo da tua Família.\n"
            "3. **A Família Primeiro:** A lealdade vem antes do teu sangue, dos teus amigos e da tua própria vida.\n\n"
            "⚠️ *Junta-te a um Regime abaixo. Apenas podes entrar em Famílias que já tenham Capo (Máx. 20 soldados).* "
        )
        try:
            translated = await asyncio.to_thread(GoogleTranslator(source='auto', target=user_locale).translate, pacto_texto)
            await interaction.followup.send(translated, ephemeral=True)
        except Exception as e:
            print(f"[TRADUTOR] Erro no painel de soldiers: {type(e).__name__}: {e}")
            await interaction.followup.send(pacto_texto, ephemeral=True)

    async def handle_soldier_join(self, interaction: discord.Interaction, familia_key: str):
        guild = interaction.guild
        member = interaction.user
        cargo_soldier = discord.utils.get(guild.roles, name="Soldier")
        cargo_capo = discord.utils.get(guild.roles, name="Capo")
        if cargo_soldier not in member.roles:
            await interaction.response.send_message("❌ Precisas de ter a patente **Soldier** para entrar num Regime!", ephemeral=True)
            return
        nome_familia = FAMILIAS[familia_key]
        cargo_familia = discord.utils.get(guild.roles, name=nome_familia)
        tem_capo = any(cargo_capo in m.roles for m in cargo_familia.members)
        if not tem_capo:
            await interaction.response.send_message(f"🚫 A **{nome_familia}** ainda não tem um Capo nomeado.", ephemeral=True)
            return
        qtd_soldados = sum(1 for m in cargo_familia.members if cargo_soldier in m.roles)
        if qtd_soldados >= LIMITE_SOLDIERS:
            await interaction.response.send_message(f"⚠️ A **{nome_familia}** já está cheia ({LIMITE_SOLDIERS}/{LIMITE_SOLDIERS} Soldados)!", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        try:
            for f_nome in FAMILIAS.values():
                c_antigo = discord.utils.get(guild.roles, name=f_nome)
                if c_antigo in member.roles:
                    await member.remove_roles(c_antigo)
            await member.add_roles(cargo_familia)
            await interaction.followup.send(f"🗡️ Bem-vindo à **{nome_familia}**! Cumpre o Pacto de Omertà e obedece ao teu Capo.", ephemeral=True)
            await enviar_log_mafia(guild, "🗡️ NOVO SOLDADO ALISTADO", f"{member.mention} juntou-se à **{nome_familia}**!", discord.Color.blue())
        except discord.Forbidden:
            await interaction.followup.send("❌ O bot não tem permissão para alterar cargos.", ephemeral=True)

    @discord.ui.button(label="Corleone", style=discord.ButtonStyle.success, emoji="🗡️", custom_id="soldier_corleone", row=1)
    async def soldier_corleone(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_soldier_join(interaction, "corleone")
    @discord.ui.button(label="Gambino", style=discord.ButtonStyle.success, emoji="🗡️", custom_id="soldier_gambino", row=1)
    async def soldier_gambino(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_soldier_join(interaction, "gambino")
    @discord.ui.button(label="Genovese", style=discord.ButtonStyle.success, emoji="🗡️", custom_id="soldier_genovese", row=1)
    async def soldier_genovese(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_soldier_join(interaction, "genovese")
    @discord.ui.button(label="Lucchese", style=discord.ButtonStyle.success, emoji="🗡️", custom_id="soldier_lucchese", row=2)
    async def soldier_lucchese(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_soldier_join(interaction, "lucchese")
    @discord.ui.button(label="Bonanno", style=discord.ButtonStyle.success, emoji="🗡️", custom_id="soldier_bonanno", row=2)
    async def soldier_bonanno(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_soldier_join(interaction, "bonanno")


# --- SISTEMA DE VOTAÇÕES INTERATIVAS (MODAL + SLASH COMMAND) ---
class DonPollModal(discord.ui.Modal, title="Criar Votação Oficial da Cúpula"):
    pergunta = discord.ui.TextInput(
        label="Pergunta da Votação",
        placeholder="Ex: A que horas atacamos amanhã?",
        style=discord.TextStyle.short,
        required=True
    )
    opcoes = discord.ui.TextInput(
        label="Opções (separadas por vírgula)",
        placeholder="Ex: 14h, 16h, 20h",
        style=discord.TextStyle.paragraph,
        required=True
    )
    duracao = discord.ui.TextInput(
        label="Duração (horas)",
        placeholder="Ex: 24 (as polls das famílias somem após este tempo)",
        style=discord.TextStyle.short,
        required=True
    )

    async def _delete_later(self, message: discord.Message, hours: float, group_id: str | None = None):
        """Apaga uma mensagem após o número de horas especificado e limpa o registo de agregação."""
        await asyncio.sleep(hours * 3600)
        try:
            await message.delete()
        except Exception:
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

            # Validar duração
            try:
                horas = float(self.duracao.value)
                if horas <= 0:
                    raise ValueError
            except ValueError:
                await interaction.followup.send("❌ Duração inválida. Indica um número positivo (ex: 24).", ephemeral=True)
                return

            guild = interaction.guild

            # Cria o grupo de agregação desta votação (liga todas as polls de família)
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

            # Propagação para as famílias
            for familia_key, nome_familia in FAMILIAS.items():
                nome_cat = f"🍷 {nome_familia.upper()}"
                categoria = discord.utils.get(guild.categories, name=nome_cat)
                if not categoria:
                    resultado[nome_familia] = "❌ Categoria não encontrada (sem QG)"
                    continue

                canal = discord.utils.get(categoria.text_channels, name="🗳️-votações")
                if not canal:
                    resultado[nome_familia] = "❌ Canal 🗳️-votações não encontrado"
                    continue

                perms = canal.permissions_for(guild.me)
                if not perms.send_messages:
                    resultado[nome_familia] = "❌ Sem permissão 'Send Messages'"
                    continue

                # Tentar poll nativa com a duração definida
                try:
                    poll = discord.Poll(question=pergunta_texto, duration=timedelta(hours=horas))
                    for opt in raw_opcoes:
                        poll.add_answer(text=opt)
                    msg = await canal.send(
                        content=f"🗳️ **VOTAÇÃO DA CÚPULA** (Aberta por {interaction.user.mention})",
                        poll=poll
                    )
                    resultado[nome_familia] = "✅ Sucesso"

                    # Regista esta poll no grupo de agregação, mapeando answer_id -> índice da opção
                    answer_map = {}
                    if msg.poll:
                        for idx, answer in enumerate(msg.poll.answers):
                            answer_map[answer.id] = idx
                    grupo["member_polls"][msg.id] = {"familia": nome_familia, "answer_map": answer_map}
                    message_to_group[msg.id] = group_id

                    # Agendar apagamento após a duração
                    asyncio.create_task(self._delete_later(msg, horas, group_id=None))
                except Exception:
                    # Fallback por reações (não entra na agregação, pois não gera eventos de poll)
                    try:
                        emojis = ["1️⃣","2️⃣","3️⃣","4️⃣","5️⃣","6️⃣","7️⃣","8️⃣","9️⃣","🔟"]
                        descricao = "\n".join([f"{emojis[i]} {op}" for i, op in enumerate(raw_opcoes)])
                        embed = discord.Embed(
                            title=f"🗳️ {pergunta_texto}",
                            description=f"**VOTAÇÃO DA CÚPULA** (Aberta por {interaction.user.mention})\n\n{descricao}\n*Duração: {horas}h*",
                            color=discord.Color.gold()
                        )
                        msg = await canal.send(embed=embed)
                        for i in range(len(raw_opcoes)):
                            await msg.add_reaction(emojis[i])
                        resultado[nome_familia] = "✅ Sucesso (por reações — fora da agregação)"
                        asyncio.create_task(self._delete_later(msg, horas, group_id=None))
                    except Exception as e:
                        resultado[nome_familia] = f"❌ Falhou: {str(e)[:60]}"
                await asyncio.sleep(1)

            # Enviar também no canal onde o /votacao foi usado (NÃO apagar) + embed agregado
            canal_origem = interaction.channel
            if canal_origem:
                perms_origem = canal_origem.permissions_for(guild.me)
                if perms_origem.send_messages:
                    grupo["canal_central_id"] = canal_origem.id
                    try:
                        poll_origem = discord.Poll(question=pergunta_texto, duration=timedelta(hours=horas))
                        for opt in raw_opcoes:
                            poll_origem.add_answer(text=opt)
                        await canal_origem.send(
                            content=f"🗳️ **VOTAÇÃO OFICIAL DA CÚPULA** (Criada por {interaction.user.mention}) — Registo permanente",
                            poll=poll_origem
                        )
                    except Exception:
                        pass

                    # Embed com o resultado agregado das famílias, atualizado em tempo real
                    if grupo["member_polls"]:
                        try:
                            embed_msg = await canal_origem.send(embed=build_resultado_embed(grupo))
                            grupo["embed_message_id"] = embed_msg.id
                            # Agenda a limpeza do grupo de agregação para quando a votação expirar
                            asyncio.create_task(self._delete_later_group_only(horas, group_id))
                        except Exception as e:
                            print(f"[VOTACAO] Erro ao enviar embed agregado: {e}")

            # Resposta privada
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
            resposta += f"\n⏳ As polls das famílias serão apagadas automaticamente após **{horas}** horas."
            if grupo["member_polls"]:
                resposta += "\n📊 O resultado agregado será atualizado em tempo real no canal central."

            await interaction.followup.send(resposta, ephemeral=True)

        except Exception as erro:
            try:
                await interaction.followup.send(f"❌ Ocorreu um erro inesperado: {str(erro)[:200]}", ephemeral=True)
            except:
                pass

    async def _delete_later_group_only(self, hours: float, group_id: str):
        """Limpa o grupo de agregação (sem apagar o embed central) após a duração da votação."""
        await asyncio.sleep(hours * 3600)
        limpar_grupo(group_id)


@bot.tree.command(name="votacao", description="Abre o formulário para o Don criar uma votação global.")
@commands.has_permissions(administrator=True)
async def votacao_slash(interaction: discord.Interaction):
    await interaction.response.send_modal(DonPollModal())


# --- EVENTOS DE VOTO EM POLLS (AGREGAÇÃO ENTRE FAMÍLIAS) ---
@bot.event
async def on_raw_poll_vote_add(payload: discord.RawPollVoteActionEvent):
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


@bot.event
async def on_raw_poll_vote_remove(payload: discord.RawPollVoteActionEvent):
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


# --- COMANDO SYNC ---
@bot.command(name="sync")
@commands.has_permissions(administrator=True)
async def sync_commands(ctx):
    try:
        bot.tree.copy_global_to(guild=ctx.guild)
        synced = await bot.tree.sync(guild=ctx.guild)
        await ctx.send(f"✅ Sincronizados **{len(synced)}** comandos de barra neste servidor!")
    except Exception as e:
        await ctx.send(f"❌ Erro ao sincronizar: {e}")


# --- COMANDOS DE SETUP E RELATÓRIO ---
@bot.command(name="setup_logs")
@commands.has_permissions(administrator=True)
async def setup_logs(ctx):
    guild = ctx.guild
    nome_canal = "🕶️-mafia-logs"
    canal_existente = discord.utils.get(guild.text_channels, name=nome_canal)
    if canal_existente:
        await ctx.send(f"⚠️ O canal de logs já existe: {canal_existente.mention}")
        return
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(read_messages=False),
        guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
    }
    for role in guild.roles:
        if role.permissions.administrator:
            overwrites[role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
    canal = await guild.create_text_channel(name=nome_canal, overwrites=overwrites, topic="Registo oficial de movimentações e lealdade das Famílias.")
    await ctx.send(f"✅ Canal de logs criado: {canal.mention}")

@bot.command(name="setup_capos_message")
@commands.has_permissions(administrator=True)
async def setup_capos_message(ctx):
    guild = ctx.guild
    nome_canal = "🎯-capos-message"
    canal_existente = discord.utils.get(guild.text_channels, name=nome_canal)
    if canal_existente:
        await ctx.send(f"⚠️ O canal central já existe: {canal_existente.mention}")
        return
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(read_messages=False),
        guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
    }
    cargo_capo = discord.utils.get(guild.roles, name="Capo")
    if cargo_capo:
        overwrites[cargo_capo] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
    for role in guild.roles:
        if role.permissions.administrator:
            overwrites[role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
    canal = await guild.create_text_channel(name=nome_canal, overwrites=overwrites, topic="Propagação de comunicados para 🚨-warnings das famílias.")
    await ctx.send(f"✅ Canal criado: {canal.mention}")

@bot.command(name="setup_vota_message")
@commands.has_permissions(administrator=True)
async def setup_vota_message(ctx):
    guild = ctx.guild
    nome_canal = "🎯-don-votes"
    canal_existente = discord.utils.get(guild.text_channels, name=nome_canal)
    if canal_existente:
        await ctx.send(f"⚠️ O canal central de votações já existe: {canal_existente.mention}")
        return
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(read_messages=False),
        guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
    }
    for role in guild.roles:
        if role.permissions.administrator or role.name == "Capo":
            overwrites[role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
    canal = await guild.create_text_channel(name=nome_canal, overwrites=overwrites, topic="Usa /votacao para criar votações globais.")
    await ctx.send(f"✅ Canal criado: {canal.mention}")

@bot.command(name="status_familias")
@commands.has_permissions(administrator=True)
async def status_familias(ctx):
    guild = ctx.guild
    cargo_capo = discord.utils.get(guild.roles, name="Capo")
    cargo_soldier = discord.utils.get(guild.roles, name="Soldier")
    embed = discord.Embed(title="📊 RELATÓRIO DE PODER DAS FAMÍLIAS", color=discord.Color.dark_red())
    for key, nome_familia in FAMILIAS.items():
        cargo_fam = discord.utils.get(guild.roles, name=nome_familia)
        if not cargo_fam:
            continue
        capos = [m.mention for m in cargo_fam.members if cargo_capo and cargo_capo in m.roles]
        capo_str = capos[0] if capos else "*Sem Capo*"
        qtd_soldados = sum(1 for m in cargo_fam.members if cargo_soldier and cargo_soldier in m.roles)
        embed.add_field(name=f"🍷 {nome_familia}", value=f"**Capo:** {capo_str}\n**Soldados:** `{qtd_soldados}/{LIMITE_SOLDIERS}`", inline=False)
    await ctx.send(embed=embed)

@bot.command(name="setup_ranks")
@commands.has_permissions(administrator=True)
async def setup_ranks(ctx):
    await ctx.message.delete()
    embed = discord.Embed(
        title="🏛️ ORGANIZATION & HIERARCHY — COSA NOSTRA",
        description="*\"In our family, there is no room for freelancers...\"*\n\n---",
        color=discord.Color.dark_red()
    )
    embed.add_field(name="🎩 1. THE DON (The Boss)", value="...", inline=False)
    embed.add_field(name="🍷 2. CAPOREGIME / CAPO", value="...", inline=False)
    embed.add_field(name="🗡️ 3. SOLDIER", value="...", inline=False)
    embed.add_field(name="🕶️ 4. STAFF / AUDITORS", value="...", inline=False)
    embed.add_field(name="📜 THE CODE OF CONDUCT (OMERTÀ)", value="...", inline=False)
    await ctx.send(embed=embed, view=RanksView())

@bot.command(name="setup_capo")
@commands.has_permissions(administrator=True)
async def setup_capo(ctx):
    await ctx.message.delete()
    texto = (
        "# 🍷 THE CAPOREGIME OATH & CLAIM\n"
        "*\"Liderar não é um privilégio, é uma responsabilidade de sangue.\"*\n\n"
        "---\n\n"
        "### 📜 THE OMERTA CODE FOR CAPOS\n"
        "1. **Absolute Loyalty:** ...\n"
        "2. **Protection:** ...\n"
        "3. **Silence:** ...\n\n"
        "⚠️ **Reivindica a tua Família abaixo.**"
    )
    await ctx.send(content=texto, view=CapoRegistryView())

@bot.command(name="setup_soldier")
@commands.has_permissions(administrator=True)
async def setup_soldier(ctx):
    await ctx.message.delete()
    texto = (
        "# 🗡️ SOLDIER ENLISTMENT & OMERTA\n"
        "*\"Ajoelha-te como um homem livre...\"*\n\n"
        "---\n\n"
        "### 📜 THE OMERTA CODE (Pacto de Sangue)\n"
        "1. **Silence (Omertà):** ...\n"
        "2. **Chain of Command:** ...\n"
        "3. **Family First:** ...\n\n"
        "⚠️ **Junta-te a um Regime abaixo.**"
    )
    await ctx.send(content=texto, view=SoldierEnlistView())

@bot.event
async def on_ready():
    bot.add_view(RanksView())
    bot.add_view(CapoRegistryView())
    bot.add_view(SoldierEnlistView())
    try:
        await bot.tree.sync()
        print("Comandos sincronizados.")
    except Exception as e:
        print(f"Erro ao sincronizar: {e}")
    await start_dummy_server()
    print(f"Bot ligado como {bot.user}")

@bot.event
async def on_message(message):
    if message.author.bot:
        return
    if message.channel.name == "🎯-capos-message":
        for familia_key, nome_familia in FAMILIAS.items():
            nome_cat = f"🍷 {nome_familia.upper()}"
            categoria = discord.utils.get(message.guild.categories, name=nome_cat)
            if categoria:
                canal_warnings = discord.utils.get(categoria.text_channels, name="🚨-warnings")
                if canal_warnings:
                    try:
                        embed = discord.Embed(title="🚨 COMUNICADO OFICIAL DA CÚPULA", description=message.content, color=discord.Color.dark_red())
                        embed.set_author(name=message.author.display_name, icon_url=message.author.display_avatar.url if message.author.display_avatar else None)
                        if message.attachments:
                            embed.set_image(url=message.attachments[0].url)
                        await canal_warnings.send(embed=embed)
                    except Exception as e:
                        print(f"Erro ao propagar aviso para {nome_familia}: {e}")
        try:
            await message.add_reaction("✅")
        except discord.Forbidden:
            pass
        return
    await bot.process_commands(message)

token = os.getenv("DISCORD_TOKEN")
if token:
    bot.run(token)
