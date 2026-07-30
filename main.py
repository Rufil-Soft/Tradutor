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
            await interaction.response.send_message(f"🔠 **Tradução ({user_locale.upper()}):**\n{translated}", 
            view=DismissView(), 
            ephemeral=True
        )
        except Exception:
            await interaction.response.send_message("Erro ao traduzir mensagem.", ephemeral=True)


# --- PAINEL DOS CAPOS (#capo-registry) ---
class CapoRegistryView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Ler Pacto no meu idioma", style=discord.ButtonStyle.secondary, emoji="🌐", custom_id="translate_omerta_capo", row=0)
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

        capos_na_familia = [m for m in cargo_familia.members if cargo_capo in m.roles]
        if len(capos_na_familia) > 0:
            await interaction.response.send_message(f"⚠️ A **{nome_familia}** já tem um Capo a liderá-la ({capos_na_familia[0].display_name})!", ephemeral=True)
            return

        await member.add_roles(cargo_familia)
        await interaction.response.send_message(f"🍷 **Honra e Lealdade!** Assumiste o comando da **{nome_familia}**!", ephemeral=True)

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

    @discord.ui.button(label="Ler Pacto no meu idioma", style=discord.ButtonStyle.secondary, emoji="🌐", custom_id="translate_omerta_soldier", row=0)
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

        for f_nome in FAMILIAS.values():
            c_antigo = discord.utils.get(guild.roles, name=f_nome)
            if c_antigo in member.roles:
                await member.remove_roles(c_antigo)

        await member.add_roles(cargo_familia)
        await interaction.response.send_message(f"🗡️ Bem-vindo à **{nome_familia}**! Cumpre o Pacto de Omertà e obedece ao teu Capo.", ephemeral=True)

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


# --- COMANDOS DE SETUP ---

@bot.command(name="setup_canais")
@commands.has_permissions(administrator=True)
async def setup_canais(ctx):
    """Cria a categoria e os canais privados em inglês."""
    guild = ctx.guild
    msg = await ctx.send("⏳ Creating Family Headquarters...")

    # Categoria em Inglês
    nome_categoria = "🍷 FAMILY HEADQUARTERS"
    categoria = discord.utils.get(guild.categories, name=nome_categoria)
    if not categoria:
        categoria = await guild.create_category(nome_categoria)

    canais_criados = []

    for key, nome_familia in FAMILIAS.items():
        cargo_familia = discord.utils.get(guild.roles, name=nome_familia)

        if not cargo_familia:
            await ctx.send(f"⚠️ Role **{nome_familia}** not found! Please create it in Discord settings.")
            continue

        # Nome do canal em Inglês (ex: #🥃-corleone-hq)
        nome_canal = f"🥃-{key}-hq"

        canal_existente = discord.utils.get(guild.text_channels, name=nome_canal)
        if canal_existente:
            canais_criados.append(canal_existente.mention)
            continue

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            cargo_familia: discord.PermissionOverwrite(read_messages=True, send_messages=True, read_message_history=True)
        }

        canal = await guild.create_text_channel(
            name=nome_canal,
            category=categoria,
            overwrites=overwrites,
            topic=f"Secret Headquarters for {nome_familia}. Authorized personnel only."
        )
        canais_criados.append(canal.mention)

    await msg.edit(content="✅ **Family Headquarters created successfully!**\n" + "\n".join(canais_criados))


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
        "⚠️ **Reivindica a tua Família abaixo.** Ao clicar, assume a liderança do território. Apenas 1 Capo por Família."
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
    await bot.process_commands(message)

    if message.content and not message.content.startswith(bot.command_prefix):
        await message.channel.send(content=f"**{message.author.display_name}**: {message.content}", view=TranslateView())
        try:
            await message.delete()
        except Exception:
            pass

token = os.getenv("DISCORD_TOKEN")
if token:
    bot.run(token)
