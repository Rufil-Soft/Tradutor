import asyncio
import discord
from discord.ext import commands
from deep_translator import GoogleTranslator
from config import FAMILIAS, LIMITE_SOLDIERS
from utils.logs import enviar_log_mafia
from bot import bot


class RanksView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Read Ranks in my language", style=discord.ButtonStyle.secondary, emoji="🌐", custom_id="translate_ranks", row=0)
    async def translate_ranks(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        user_locale = str(interaction.locale).split("-")[0] or "pt"
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
            "The guardians of the system and neutrality. They ensure Omertà rules are followed and audit operations through `#🕶️-mafia-logs`.\n\n"
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


class CapoRegistryView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    # ------ NOVO BOTÃO DE TRADUÇÃO ------
    @discord.ui.button(label="Translate", style=discord.ButtonStyle.secondary, emoji="🌐", custom_id="translate_capo_oath", row=0)
    async def translate_oath(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        user_locale = str(interaction.locale).split("-")[0] or "pt"
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
        try:
            translated = await asyncio.to_thread(GoogleTranslator(source='auto', target=user_locale).translate, texto)
            await interaction.followup.send(translated, ephemeral=True)
        except Exception as e:
            await interaction.followup.send("❌ Falha na tradução. Tenta novamente.", ephemeral=True)

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
        if capos_na_familia:
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
            overwrites_announcements = {
                guild.default_role: discord.PermissionOverwrite(read_messages=False),
                cargo_familia: discord.PermissionOverwrite(read_messages=True, send_messages=False),
                cargo_capo: discord.PermissionOverwrite(read_messages=True, send_messages=True)
            }
            if not canal_anuncios:
                await guild.create_text_channel("📜-capo-announcements", category=categoria, overwrites=overwrites_announcements, topic=f"Official announcements for {nome_familia}.")
            else:
                await canal_anuncios.edit(overwrites=overwrites_announcements)
            
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
                await canal_warnings.edit(overwrites=overwrites_warnings)
            
            # Canal Votações
            canal_votacoes = discord.utils.get(categoria.text_channels, name="🗳️-votações")
            overwrites_votacoes = {
                guild.default_role: discord.PermissionOverwrite(read_messages=False),
                cargo_familia: discord.PermissionOverwrite(read_messages=True, send_messages=True, read_message_history=True)
            }
            if not canal_votacoes:
                await guild.create_text_channel("🗳️-votações", category=categoria, overwrites=overwrites_votacoes, topic=f"Canal de votações oficiais para a {nome_familia}.")
            else:
                await canal_votacoes.edit(overwrites=overwrites_votacoes)
            
            # Chat Geral
            canal_chat = discord.utils.get(categoria.text_channels, name="💬-general-chat")
            overwrites_chat = {
                guild.default_role: discord.PermissionOverwrite(read_messages=False),
                cargo_familia: discord.PermissionOverwrite(read_messages=True, send_messages=True, read_message_history=True)
            }
            if not canal_chat:
                await guild.create_text_channel("💬-general-chat", category=categoria, overwrites=overwrites_chat, topic=f"Secret HQ text chat for {nome_familia}.")
            else:
                await canal_chat.edit(overwrites=overwrites_chat)
            
            # Sala de Voz
            canal_voz = discord.utils.get(categoria.voice_channels, name="📢-meeting-room")
            if not canal_voz:
                await guild.create_voice_channel("📢-meeting-room", category=categoria, overwrites=overwrites_base)
            else:
                await canal_voz.edit(overwrites=overwrites_base)
            
            await interaction.followup.send(
                f"🍷 **Honra e Lealdade!** Assumiste o comando da **{nome_familia}**!\n📂 QG configurado com sucesso!", ephemeral=True
            )
            await enviar_log_mafia(guild, "🍷 NOVO CAPO & QG CRIADO", f"{member.mention} assumiu a liderança da **{nome_familia}** e ativou o QG privado da Família!", discord.Color.gold())
        except discord.Forbidden:
            await interaction.followup.send("❌ O bot não tem permissões para gerenciar cargos/canais.", ephemeral=True)

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


class SoldierEnlistView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    # ------ NOVO BOTÃO DE TRADUÇÃO ------
    @discord.ui.button(label="Translate", style=discord.ButtonStyle.secondary, emoji="🌐", custom_id="translate_soldier_oath", row=0)
    async def translate_oath(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        user_locale = str(interaction.locale).split("-")[0] or "pt"
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
        try:
            translated = await asyncio.to_thread(GoogleTranslator(source='auto', target=user_locale).translate, texto)
            await interaction.followup.send(translated, ephemeral=True)
        except Exception as e:
            await interaction.followup.send("❌ Falha na tradução. Tenta novamente.", ephemeral=True)

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


class Paineis(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="setup_ranks")
    @commands.has_permissions(administrator=True)
    async def setup_ranks(self, ctx):
        await ctx.message.delete()
        embed = discord.Embed(
            title="🏛️ ORGANIZATION & HIERARCHY — COSA NOSTRA",
            description=(
                "*\"In our family, there is no room for freelancers. Every man has his place, "
                "his duty, and his weight on the scales of power.\"*\n\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━"
            ),
            color=discord.Color.dark_red(),
            timestamp=discord.utils.utcnow()
        )
        embed.add_field(name="\u200b", value="\u200b", inline=False)
        embed.add_field(
            name="🎩 1. THE DON (The Boss)",
            value="The top of the pyramid. The Don commands the destiny of all Families, arbitrates territorial disputes, and maintains peace or declares war.",
            inline=False
        )
        embed.add_field(
            name="🍷 2. CAPOREGIME / CAPO (The Regime Leader)",
            value="The commander of each Family (Corleone, Gambino, Genovese, Lucchese, Bonanno). \n"
                  "• Only 1 Capo per Family.\n"
                  "• Leads their own private HQ and commands up to 20 Soldiers.\n"
                  "• Responsible for discipline and territory strategy.",
            inline=False
        )
        embed.add_field(
            name="🗡️ 3. SOLDIER (The Man of Honor)",
            value="The armed and loyal arm of the Family.\n"
                  "• Strict limit of 20 Soldiers per Family.\n"
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

    @commands.command(name="setup_capo")
    @commands.has_permissions(administrator=True)
    async def setup_capo(self, ctx):
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

    @commands.command(name="setup_soldier")
    @commands.has_permissions(administrator=True)
    async def setup_soldier(self, ctx):
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


async def setup(bot: commands.Bot):
    bot.add_view(RanksView())
    bot.add_view(CapoRegistryView())
    bot.add_view(SoldierEnlistView())
    await bot.add_cog(Paineis(bot))
