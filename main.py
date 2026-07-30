import os
import asyncio
import discord
from discord.ext import commands
from deep_translator import GoogleTranslator
from aiohttp import web
from datetime import timedelta

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

FAMILIAS = {
    "corleone": "Família Corleone",
    "gambino": "Família Gambino",
    "genovese": "Família Genovese",
    "lucchese": "Família Lucchese",
    "bonanno": "Família Bonanno"
}
LIMITE_SOLDIERS = 20


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


# --- TRADUÇÃO VIA MENU DE CONTEXTO (CLIQUE DIREITO NA MENSAGEM) ---
@bot.tree.context_menu(name="Traduzir Mensagem")
async def traduzir_context(interaction: discord.Interaction, message: discord.Message):
    await interaction.response.defer(ephemeral=True)
    
    if not message.content:
        await interaction.followup.send("Esta mensagem não tem texto para traduzir.", ephemeral=True)
        return

    user_locale = str(interaction.locale).split("-")[0]

    try:
        translated = await asyncio.to_thread(
            GoogleTranslator(source='auto', target=user_locale).translate,
            message.content
        )
        await interaction.followup.send(
            f"🔠 **Tradução ({user_locale.upper()}):**\n{translated}", 
            ephemeral=True
        )
    except Exception:
        await interaction.followup.send("Erro ao traduzir mensagem.", ephemeral=True)


# --- SISTEMA DE LOGS E AUDITORIA DA MÁFIA ---
async def enviar_log_mafia(guild: discord.Guild, titulo: str, descricao: str, cor: discord.Color):
    try:
        canal_log = discord.utils.get(guild.text_channels, name="🕶️-mafia-logs")
        if canal_log:
            embed = discord.Embed(
                title=titulo,
                description=descricao,
                color=cor,
                timestamp=discord.utils.utcnow()
            )
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
            translated = await asyncio.to_thread(
                GoogleTranslator(source='auto', target=user_locale).translate,
                ranks_texto
            )
            await interaction.followup.send(translated, ephemeral=True)
        except Exception:
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
            translated = await asyncio.to_thread(
                GoogleTranslator(source='auto', target=user_locale).translate,
                pacto_texto
            )
            await interaction.followup.send(translated, ephemeral=True)
        except Exception:
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
                await guild.create_text_channel(
                    "📜-capo-announcements", 
                    category=categoria, 
                    overwrites=overwrites_announcements, 
                    topic=f"Official announcements for {nome_familia}."
                )

            # Canal Warnings
            canal_warnings = discord.utils.get(categoria.text_channels, name="🚨-warnings")
            overwrites_warnings = {
                guild.default_role: discord.PermissionOverwrite(read_messages=False),
                cargo_familia: discord.PermissionOverwrite(read_messages=False),
                member: discord.PermissionOverwrite(read_messages=True, send_messages=False, read_message_history=True)
            }
            if not canal_warnings:
                await guild.create_text_channel(
                    "🚨-warnings", 
                    category=categoria, 
                    overwrites=overwrites_warnings, 
                    topic=f"Canal de warnings vindos da Cúpula exclusivo para o Capo da {nome_familia}."
                )
            else:
                await canal_warnings.set_permissions(member, read_messages=True, send_messages=False, read_message_history=True)

            # Canal Votações da Família
            canal_votacoes = discord.utils.get(categoria.text_channels, name="🗳️-votações")
            if not canal_votacoes:
                overwrites_votacoes = {
                    guild.default_role: discord.PermissionOverwrite(read_messages=False),
                    cargo_familia: discord.PermissionOverwrite(read_messages=True, send_messages=True, read_message_history=True)
                }
                await guild.create_text_channel(
                    "🗳️-votações", 
                    category=categoria, 
                    overwrites=overwrites_votacoes, 
                    topic=f"Canal de votações oficiais para a {nome_familia}."
                )

            # Chat Geral
            canal_chat = discord.utils.get(categoria.text_channels, name="💬-general-chat")
            if not canal_chat:
                await guild.create_text_channel(
                    "💬-general-chat", 
                    category=categoria, 
                    topic=f"Secret HQ text chat for {nome_familia}."
                )

            # Sala de Voz
            canal_voz = discord.utils.get(categoria.voice_channels, name="📢-meeting-room")
            if not canal_voz:
                await guild.create_voice_channel(
                    "📢-meeting-room", 
                    category=categoria
                )

            await interaction.followup.send(
                f"🍷 **Honra e Lealdade!** Assumiste o comando da **{nome_familia}**!\n"
                f"📂 QG configurado com sucesso (`📜-capo-announcements`, `🚨-warnings`, `🗳️-votações`, `💬-general-chat`, `📢-meeting-room`)!", 
                ephemeral=True
            )

            await enviar_log_mafia(
                guild, 
                "🍷 NOVO CAPO & QG CRIADO", 
                f"{member.mention} assumiu a liderança da **{nome_familia}** e ativou o QG privado da Família!", 
                discord.Color.gold()
            )

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
            translated = await asyncio.to_thread(
                GoogleTranslator(source='auto', target=user_locale).translate,
                pacto_texto
            )
            await interaction.followup.send(translated, ephemeral=True)
        except Exception:
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
            await interaction.response.send_message(f"🚫 A **{nome_familia}** ainda não tem um Capo nomeado. Escolhe uma Família com liderança ativa!", ephemeral=True)
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
            await enviar_log_mafia(
                guild, 
                "🗡️ NOVO SOLDADO ALISTADO", 
                f"{member.mention} juntou-se à **{nome_familia}**!", 
                discord.Color.blue()
            )
        except discord.Forbidden:
            await interaction.followup.send("❌ O bot não tem permissão para alterar cargos. Ajusta a hierarquia de cargos no Discord.", ephemeral=True)

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
# VERSÃO MELHORADA COM FEEDBACK POR FAMÍLIA
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

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        pergunta_texto = self.pergunta.value
        raw_opcoes = [o.strip() for o in self.opcoes.value.split(",") if o.strip()]

        if len(raw_opcoes) < 2:
            await interaction.followup.send("❌ Tens de fornecer pelo menos 2 opções válidas separadas por vírgula.", ephemeral=True)
            return
        if len(raw_opcoes) > 10:
            await interaction.followup.send("❌ O Discord permite no máximo 10 opções por votação.", ephemeral=True)
            return

        guild = interaction.guild
        # Dicionário para guardar o resultado de cada família
        resultado = {}

        for familia_key, nome_familia in FAMILIAS.items():
            nome_cat = f"🍷 {nome_familia.upper()}"
            categoria = discord.utils.get(guild.categories, name=nome_cat)
            if not categoria:
                resultado[nome_familia] = "❌ Categoria não encontrada (sem QG)"
                continue

            canal_votacoes = discord.utils.get(categoria.text_channels, name="🗳️-votações")
            if not canal_votacoes:
                resultado[nome_familia] = "❌ Canal 🗳️-votações não encontrado"
                continue

            # Verificar permissões do bot no canal
            perms = canal_votacoes.permissions_for(guild.me)
            if not perms.send_messages:
                resultado[nome_familia] = "❌ Bot sem permissão 'Send Messages'"
                continue
            if not perms.create_polls:
                resultado[nome_familia] = "❌ Bot sem permissão 'Create Polls' (adiciona esta permissão no canal!)"
                continue

            # Criar poll
            poll = discord.Poll(question=pergunta_texto, duration=timedelta(hours=24))
            for opt in raw_opcoes:
                poll.add_answer(text=opt)

            # Tentar enviar com até 2 tentativas (para rate limit)
            for tentativa in range(2):
                try:
                    await canal_votacoes.send(
                        content=f"🗳️ **VOTAÇÃO DA CÚPULA** (Aberta por {interaction.user.mention})",
                        poll=poll
                    )
                    resultado[nome_familia] = "✅ Sucesso"
                    await asyncio.sleep(1)  # pausa entre famílias
                    break
                except discord.Forbidden:
                    resultado[nome_familia] = "❌ Bot sem permissão para enviar polls (403 Forbidden). Verifica 'Create Polls' no canal."
                    break
                except discord.HTTPException as e:
                    if e.status == 429:
                        retry_after = getattr(e, 'retry_after', 5)
                        print(f"Rate limit para {nome_familia}, aguardando {retry_after}s...")
                        await asyncio.sleep(retry_after)
                        continue
                    else:
                        resultado[nome_familia] = f"❌ Erro HTTP {e.status}"
                        break
                except Exception as e:
                    resultado[nome_familia] = f"❌ Erro: {str(e)[:50]}"
                    break
            else:
                # Se o loop esgotar as tentativas sem sucesso
                resultado[nome_familia] = "❌ Falha após retentativa de rate limit"

        # Construir resposta final
        sucessos = [f for f, r in resultado.items() if r == "✅ Sucesso"]
        falhas = {f: r for f, r in resultado.items() if r != "✅ Sucesso"}

        resposta = ""
        if sucessos:
            resposta += f"✅ Votação propagada com sucesso para: **{', '.join(sucessos)}**.\n"
        if falhas:
            resposta += "\n⚠️ **Problemas encontrados:**\n"
            for fam, motivo in falhas.items():
                resposta += f"• **{fam}**: {motivo}\n"

        if not sucessos and not falhas:
            resposta = "⚠️ Nenhuma família foi processada."

        await interaction.followup.send(resposta, ephemeral=True)


@bot.tree.command(name="votacao", description="Abre um formulário para o Don criar uma votação global nas Famílias.")
@commands.has_permissions(administrator=True)
async def votacao_slash(interaction: discord.Interaction):
    await interaction.response.send_modal(DonPollModal())


# --- COMANDO SYNC PARA REGISTAR COMANDOS INSTANTANEAMENTE ---
@bot.command(name="sync")
@commands.has_permissions(administrator=True)
async def sync_commands(ctx):
    """Sincroniza os comandos de barra instantaneamente no servidor atual."""
    try:
        bot.tree.copy_global_to(guild=ctx.guild)
        synced = await bot.tree.sync(guild=ctx.guild)
        await ctx.send(f"✅ Sincronizados **{len(synced)}** comandos de barra instantaneamente neste servidor!")
    except Exception as e:
        await ctx.send(f"❌ Erro ao sincronizar comandos: {e}")


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

    canal = await guild.create_text_channel(
        name=nome_canal,
        overwrites=overwrites,
        topic="Registo oficial de movimentações e lealdade das Famílias."
    )
    await ctx.send(f"✅ Canal de logs criado com sucesso: {canal.mention}")


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

    canal = await guild.create_text_channel(
        name=nome_canal,
        overwrites=overwrites,
        topic="Tudo o que for colocado aqui será propagado automaticamente para o canal 🚨-warnings de todas as Famílias."
    )
    await ctx.send(f"✅ Canal central criado com sucesso: {canal.mention}")


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

    canal = await guild.create_text_channel(
        name=nome_canal,
        overwrites=overwrites,
        topic="Canal central para a Cúpula. Usa o comando de barra /votacao para abrir o formulário interativo de votação."
    )
    await ctx.send(f"✅ Canal central de votações criado com sucesso: {canal.mention}")


@bot.command(name="status_familias")
@commands.has_permissions(administrator=True)
async def status_familias(ctx):
    guild = ctx.guild
    cargo_capo = discord.utils.get(guild.roles, name="Capo")
    cargo_soldier = discord.utils.get(guild.roles, name="Soldier")

    embed = discord.Embed(
        title="📊 RELATÓRIO DE PODER DAS FAMÍLIAS",
        color=discord.Color.dark_red(),
        timestamp=discord.utils.utcnow()
    )

    for key, nome_familia in FAMILIAS.items():
        cargo_fam = discord.utils.get(guild.roles, name=nome_familia)
        if not cargo_fam:
            continue

        capos = [m.mention for m in cargo_fam.members if cargo_capo and cargo_capo in m.roles]
        capo_str = capos[0] if capos else "*Sem Capo Nomeado*"
        
        qtd_soldados = sum(1 for m in cargo_fam.members if cargo_soldier and cargo_soldier in m.roles)
        
        embed.add_field(
            name=f"🍷 {nome_familia}",
            value=f"**Capo:** {capo_str}\n**Soldados:** `{qtd_soldados}/{LIMITE_SOLDIERS}`",
            inline=False
        )

    await ctx.send(embed=embed)


@bot.command(name="setup_ranks")
@commands.has_permissions(administrator=True)
async def setup_ranks(ctx):
    await ctx.message.delete()
    
    embed = discord.Embed(
        title="🏛️ ORGANIZATION & HIERARCHY — COSA NOSTRA",
        description=(
            "*\"In our family, there is no room for freelancers. Every man has his place, "
            "his duty, and his weight on the scales of power.\"*\n\n"
            "---"
        ),
        color=discord.Color.dark_red(),
        timestamp=discord.utils.utcnow()
    )
    
    embed.add_field(
        name="🎩 1. THE DON (The Boss)",
        value="The top of the pyramid. The Don commands the destiny of all Families, arbitrates territorial disputes, and maintains peace or declares war.",
        inline=False
    )
    
    embed.add_field(
        name="🍷 2. CAPOREGIME / CAPO (The Regime Leader)",
        value="The commander of each Family (`Corleone`, `Gambino`, `Genovese`, `Lucchese`, `Bonanno`). \n"
              "• Only **1 Capo per Family**.\n"
              "• Leads their own private HQ and commands up to 20 Soldiers.\n"
              "• Responsible for discipline and territory strategy.",
        inline=False
    )
    
    embed.add_field(
        name="🗡️ 3. SOLDIER (The Man of Honor)",
        value="The armed and loyal arm of the Family.\n"
              "• Strict limit of **20 Soldiers per Family**.\n"
              "• Can only enlist in Families that already have an active Capo.\n"
              "• Responds exclusively to their Capo's chain of command.",
        inline=False
    )
    
    embed.add_field(
        name="🕶️ 4. STAFF / AUDITORS",
        value="The guardians of the system and neutrality. They ensure Omertà rules are followed and audit operations through `#🕶️-mafia-logs`.",
        inline=False
    )
    
    embed.add_field(
        name="📜 THE CODE OF CONDUCT (OMERTÀ)",
        value="• **Absolute Loyalty:** A given word is a blood contract.\n"
              "• **Silence:** Family business never leaves the walls of the HQ.\n"
              "• **Hierarchical Respect:** The subordinate obeys, the leader decides.",
        inline=False
    )
    
    embed.set_footer(text="Cosa Nostra System • Order is Your Survival")
    
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
        "1. **Absolute Loyalty:** As tuas ordens vêm do Don e dos Capodecinas. A tua palavra é a lei para os teus 20 Soldados.\n"
        "2. **Protection:** És a espada e o escudo dos teus homens. Se um cai, a Família responde.\n"
        "3. **Silence:** O que é falado na administração da Família morre na tumba. Traidores não têm segunda oportunidade.\n\n"
        "---\n"
        "⚠️ **Reivindica a tua Família abaixo.** Ao clicar, assume a liderança e ativa o QG Privado da Família."
    )
    await ctx.send(content=texto, view=CapoRegistryView())


@bot.command(name="setup_soldier")
@commands.has_permissions(administrator=True)
async def setup_soldier(ctx):
    await ctx.message.delete()
    texto = (
        "# 🗡️ SOLDIER ENLISTMENT & OMERTA\n"
        "*\"Ajoelha-te como um homem livre, levanta-te como um Homem de Honra.\"*\n\n"
        "---\n\n"
        "### 📜 THE OMERTA CODE (Pacto de Sangue)\n"
        "1. **Silence (Omertà):** Nunca fales com autoridades nem com Famílias rivais. A língua solta encomenda o teu próprio caixão.\n"
        "2. **Chain of Command:** Tu **só respondes ao teu Capo**. Não pules a hierarquia.\n"
        "3. **Family First:** A Família vem antes do teu sangue, dos teus amigos e da tua própria vida.\n\n"
        "---\n"
        "⚠️ **Junta-te a um Regime abaixo.**\n"
        "*Nota: Apenas podes entrar em Famílias que **já tenham um Capo ativo**. Limite estrito de 20 Soldados por Família.*"
    )
    await ctx.send(content=texto, view=SoldierEnlistView())


@bot.event
async def on_ready():
    bot.add_view(RanksView())
    bot.add_view(CapoRegistryView())
    bot.add_view(SoldierEnlistView())
    
    try:
        await bot.tree.sync()
        print("Comandos de barra/contexto sincronizados com sucesso.")
    except Exception as e:
        print(f"Erro ao sincronizar árvore de comandos: {e}")

    await start_dummy_server()
    print(f"Bot Máfia & Tradutor ligado como {bot.user}")


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
                        embed = discord.Embed(
                            title="🚨 COMUNICADO OFICIAL DA CÚPULA",
                            description=message.content,
                            color=discord.Color.dark_red(),
                            timestamp=discord.utils.utcnow()
                        )
                        embed.set_author(
                            name=message.author.display_name, 
                            icon_url=message.author.display_avatar.url if message.author.display_avatar else None
                        )
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
