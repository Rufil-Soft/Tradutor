import os
import asyncio
import discord
from discord.ext import commands
from deep_translator import GoogleTranslator
from aiohttp import web

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
    port = int(os.getenv("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    print(f"Servidor Web ativo na porta {port} (Render Keep-Alive)")

# --- BOTÃO PARA APAGAR MENSAGENS EFÉMERAS ---
class DismissView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=180)

    @discord.ui.button(label="Fechar / Dismiss", style=discord.ButtonStyle.danger, emoji="❌")
    async def dismiss_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.delete_original_response()
        
# --- SISTEMA DE TRADUÇÃO DAS MENSAGENS DO CHAT ---
class TranslateView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Traduzir", style=discord.ButtonStyle.secondary, emoji="🌐", custom_id="translate_button")
    async def translate_button_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        message_text = interaction.message.content
        if not message_text:
            await interaction.response.send_message("Não há texto para traduzir.", ephemeral=True)
            return

        if ":" in message_text:
            texto_para_traduzir = message_text.split(":", 1)[1].strip()
        else:
            texto_para_traduzir = message_text

        user_locale = str(interaction.locale).split("-")[0]

        try:
            translated = await asyncio.to_thread(
                GoogleTranslator(source='auto', target=user_locale).translate,
                texto_para_traduzir
            )
            await interaction.response.send_message(
                f"🔠 **Tradução ({user_locale.upper()}):**\n{translated}", 
                view=DismissView(), 
                ephemeral=True
            )
        except Exception:
            await interaction.response.send_message("Erro ao traduzir mensagem.", ephemeral=True)


# --- SISTEMA DE LOGS E AUDITORIA DA MÁFIA (PROTEGIDO) ---
async def enviar_log_mafia(guild: discord.Guild, titulo: str, descricao: str, cor: discord.Color):
    """Envia um registo de atividade para o canal privado de logs sem quebrar o bot caso falhe."""
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


# --- PAINEL DOS CAPOS (#capo-registry) ---
class CapoRegistryView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Read Omertà in my language", style=discord.ButtonStyle.secondary, emoji="🌐", custom_id="translate_omerta_capo", row=0)
    async def translate_omerta(self, interaction: discord.Interaction, button: discord.ui.Button):
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
            await interaction.response.send_message(translated, ephemeral=True)
        except Exception:
            await interaction.response.send_message(pacto_texto, ephemeral=True)

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

        capos_na_familia = [m for m in cargo_familia.members if cargo_capo in m.roles]
        if len(capos_na_familia) > 0:
            await interaction.response.send_message(f"⚠️ A **{nome_familia}** já tem um Capo a liderá-la ({capos_na_familia[0].display_name})!", ephemeral=True)
            return

        try:
            # 1. Atribui o cargo ao Capo
            await member.add_roles(cargo_familia)

            # 2. Gestão Inteligente da Categoria e Canais
            nome_cat = f"🍷 {nome_familia.upper()}"
            categoria = discord.utils.get(guild.categories, name=nome_cat)

            overwrites_base = {
                guild.default_role: discord.PermissionOverwrite(read_messages=False),
                cargo_familia: discord.PermissionOverwrite(read_messages=True, send_messages=True, read_message_history=True, connect=True)
            }

            if not categoria:
                categoria = await guild.create_category(nome_cat, overwrites=overwrites_base)

            # A) Canal de Anúncios da Família (📜)
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

            # B) Canal de Avisos Globais da Cúpula (🚨-warnings) - Apenas visível ao Capo específico
            canal_warnings = discord.utils.get(categoria.text_channels, name="🚨-warnings")
            overwrites_warnings = {
                guild.default_role: discord.PermissionOverwrite(read_messages=False),
                cargo_familia: discord.PermissionOverwrite(read_messages=False), # Soldados não vêem
                member: discord.PermissionOverwrite(read_messages=True, send_messages=False, read_message_history=True) # Apenas este Capo
            }
            if not canal_warnings:
                await guild.create_text_channel(
                    "🚨-warnings", 
                    category=categoria, 
                    overwrites=overwrites_warnings, 
                    topic=f"Canal de warnings vindos da Cúpula (Don/Capodecinas) exclusivo para o Capo da {nome_familia}."
                )
            else:
                await canal_warnings.set_permissions(member, read_messages=True, send_messages=False, read_message_history=True)

            # C) Chat Geral (💬)
            canal_chat = discord.utils.get(categoria.text_channels, name="💬-general-chat")
            if not canal_chat:
                await guild.create_text_channel(
                    "💬-general-chat", 
                    category=categoria, 
                    topic=f"Secret HQ text chat for {nome_familia}."
                )

            # D) Canal de Voz (📢)
            canal_voz = discord.utils.get(categoria.voice_channels, name="📢-meeting-room")
            if not canal_voz:
                await guild.create_voice_channel(
                    "📢-meeting-room", 
                    category=categoria
                )

            await interaction.response.send_message(
                f"🍷 **Honra e Lealdade!** Assumiste o comando da **{nome_familia}**!\n"
                f"📂 QG configurado com sucesso (`📜-capo-announcements`, `🚨-warnings`, `💬-general-chat`, `📢-meeting-room`)!", 
                ephemeral=True
            )

            await enviar_log_mafia(
                guild, 
                "🍷 NOVO CAPO & QG CRIADO", 
                f"{member.mention} assumiu a liderança da **{nome_familia}** e ativou o QG privado da Família!", 
                discord.Color.gold()
            )

        except discord.Forbidden:
            if not interaction.response.is_done():
                await interaction.response.send_message("❌ O bot não tem permissões para gerenciar cargos/canais. Garante que o bot tem a permissão de Administrador.", ephemeral=True)

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
            await interaction.response.send_message(translated, ephemeral=True)
        except Exception:
            await interaction.response.send_message(pacto_texto, ephemeral=True)

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

        try:
            for f_nome in FAMILIAS.values():
                c_antigo = discord.utils.get(guild.roles, name=f_nome)
                if c_antigo in member.roles:
                    await member.remove_roles(c_antigo)

            await member.add_roles(cargo_familia)
            await interaction.response.send_message(f"🗡️ Bem-vindo à **{nome_familia}**! Cumpre o Pacto de Omertà e obedece ao teu Capo.", ephemeral=True)
            await enviar_log_mafia(
                guild, 
                "🗡️ NOVO SOLDADO ALISTADO", 
                f"{member.mention} juntou-se à **{nome_familia}**!", 
                discord.Color.blue()
            )
        except discord.Forbidden:
            if not interaction.response.is_done():
                await interaction.response.send_message("❌ O bot não tem permissão para alterar cargos. Ajusta a hierarquia de cargos no Discord.", ephemeral=True)

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


# --- COMANDOS DE SETUP E RELATÓRIO ---

@bot.command(name="setup_logs")
@commands.has_permissions(administrator=True)
async def setup_logs(ctx):
    """Cria o canal privado de logs para a Staff e Don."""
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
    """Cria o canal central onde a Cúpula envia avisos para propagar a todas as Famílias."""
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


@bot.command(name="status_familias")
@commands.has_permissions(administrator=True)
async def status_familias(ctx):
    """Exibe um relatório detalhado de todas as Famílias, Capos e número de Soldados."""
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
    """Cria um painel elegante e imersivo explicando a hierarquia e os ranks da Máfia."""
    await ctx.message.delete()
    
    embed = discord.Embed(
        title="🏛️ ORGANIZATION & HIERARCHY — COSA NOSTRA",
        description=(
            "*\"Na nossa família não há espaço para soltos. Cada homem tem o seu lugar, "
            "o seu dever e o seu peso na balança do poder.\"*\n\n"
            "---"
        ),
        color=discord.Color.dark_red(),
        timestamp=discord.utils.utcnow()
    )
    
    embed.add_field(
        name="🎩 1. THE DON (O Chefe)",
        value="O topo da pirâmide. O Don comanda os destinos de todas as Famílias, arbita disputas territoriais e mantém a paz ou declara a guerra.",
        inline=False
    )
    
    embed.add_field(
        name="🍷 2. CAPOREGIME / CAPO (O Líder de Regime)",
        value="O comandante de cada Família (`Corleone`, `Gambino`, `Genovese`, `Lucchese`, `Bonanno`). \n"
              "• Apenas **1 Capo por Família**.\n"
              "• Lidera o seu próprio QG privado e comanda até 20 Soldados.\n"
              "• Responsável pela disciplina e estratégia do território.",
        inline=False
    )
    
    embed.add_field(
        name="🗡️ 3. SOLDIER (O Homem de Honra)",
        value="O braço armado e leal da Família.\n"
              "• Limite estrito de **20 Soldados por Família**.\n"
              "• Só pode alistar-se em Famílias que já tenham um Capo ativo.\n"
              "• Responde exclusivamente à cadeia de comando do seu Capo.",
        inline=False
    )
    
    embed.add_field(
        name="🕶️ 4. STAFF / AUDITORES",
        value="Os guardiões do sistema e da neutralidade. Garantem que as regras de Omertà são cumpridas e auditam as operações através de `#🕶️-mafia-logs`.",
        inline=False
    )
    
    embed.add_field(
        name="📜 O CÓDIGO DE CONDUTA (OMERTÀ)",
        value="• **Lealdade Absoluta:** A palavra dada é um contrato de sangue.\n"
              "• **Silêncio:** Negócios da Família nunca saem para fora das paredes do QG.\n"
              "• **Respeito Hierárquico:** O subalterno cumpre, o líder decide.",
        inline=False
    )
    
    embed.set_footer(text="Cosa Nostra System • A Ordem é a Vossa Sobrevivência")
    
    await ctx.send(embed=embed)


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
    bot.add_view(TranslateView())
    bot.add_view(CapoRegistryView())
    bot.add_view(SoldierEnlistView())
    await start_dummy_server()
    print(f"Bot Máfia & Tradutor ligado como {bot.user}")


@bot.event
async def on_message(message):
    if message.author.bot:
        return
        
    # --- SISTEMA DE PROPAGAÇÃO DE MENSAGENS (CAPOS MESSAGE -> WARNINGS) ---
    if message.channel.name == "🎯-capos-message":
        propagated_count = 0
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
                        propagated_count += 1
                    except Exception as e:
                        print(f"Erro ao propagar aviso para {nome_familia}: {e}")
        
        try:
            await message.add_reaction("✅")
        except discord.Forbidden:
            pass
        return

    await bot.process_commands(message)

    if message.content and not message.content.startswith(bot.command_prefix):
        await message.channel.send(content=f"**{message.author.display_name}**: {message.content}", view=TranslateView())
        try:
            await message.delete()
        except discord.Forbidden:
            pass

token = os.getenv("DISCORD_TOKEN")
if token:
    bot.run(token)
