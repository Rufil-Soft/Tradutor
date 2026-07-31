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
            "The commander of each Family (Corleone, Gambino, Genovese, Lucchese, Bonanno, Colombo).\n"
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

    @discord.ui.button(label="Claim Family", style=discord.ButtonStyle.primary, emoji="🍷", custom_id="capo_claim_main", row=1)
    async def claim_family(self, interaction: discord.Interaction, button: discord.ui.Button):
        cargo_capo = discord.utils.get(interaction.guild.roles, name="Capo")
        if cargo_capo not in interaction.user.roles:
            await interaction.response.send_message("❌ Apenas membros com a patente de **Capo** podem reivindicar uma Família.", ephemeral=True)
            return

        guild = interaction.guild
        disponiveis = []
        for familia_key, nome_familia in FAMILIAS.items():
            cargo_fam = discord.utils.get(guild.roles, name=nome_familia)
            if not cargo_fam:
                continue
            capos = [m for m in cargo_fam.members if cargo_capo in m.roles]
            if not capos:
                disponiveis.append((familia_key, nome_familia))

        if not disponiveis:
            await interaction.response.send_message("⚠️ Todas as famílias já têm um Capo nomeado.", ephemeral=True)
            return

        class FamilyChoiceView(discord.ui.View):
            def __init__(self):
                super().__init__(timeout=60)
                for familia_key, nome_familia in disponiveis:
                    botao = discord.ui.Button(
                        label=nome_familia,
                        style=discord.ButtonStyle.primary,
                        emoji="🍷",
                        custom_id=f"capo_choose_{familia_key}"
                    )
                    botao.callback = self.make_callback(familia_key)
                    self.add_item(botao)

            def make_callback(self, familia_key: str):
                async def callback(button_interaction: discord.Interaction):
                    await Paineis.handle_capo_claim_static(button_interaction, familia_key, guild)
                return callback

        view = FamilyChoiceView()
        await interaction.response.send_message("🍷 Escolhe a família que queres liderar:", view=view, ephemeral=True)


class SoldierEnlistView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

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

    @discord.ui.button(label="🗡️ Join a Family", style=discord.ButtonStyle.primary, custom_id="soldier_enlist_main", row=1)
    async def enlist_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        cargo_soldier = discord.utils.get(interaction.guild.roles, name="Soldier")
        if cargo_soldier not in interaction.user.roles:
            await interaction.response.send_message("❌ Precisas da patente **Soldier** para te alistar.", ephemeral=True)
            return

        guild = interaction.guild
        cargo_capo = discord.utils.get(guild.roles, name="Capo")
        opcoes_validas = []

        for familia_key, nome_familia in FAMILIAS.items():
            cargo_fam = discord.utils.get(guild.roles, name=nome_familia)
            if not cargo_fam:
                continue
            capos = [m for m in cargo_fam.members if cargo_capo in m.roles]
            if capos:
                qtd = sum(1 for m in cargo_fam.members if cargo_soldier in m.roles)
                if qtd < LIMITE_SOLDIERS:
                    opcoes_validas.append((familia_key, nome_familia))

        if not opcoes_validas:
            await interaction.response.send_message("⚠️ Nenhuma família disponível para alistamento neste momento.", ephemeral=True)
            return

        class FamilyButtonsView(discord.ui.View):
            def __init__(self):
                super().__init__(timeout=60)
                for familia_key, nome_familia in opcoes_validas:
                    botao = discord.ui.Button(
                        label=nome_familia,
                        style=discord.ButtonStyle.primary,
                        emoji="🗡️",
                        custom_id=f"soldier_join_{familia_key}"
                    )
                    botao.callback = self.make_callback(familia_key)
                    self.add_item(botao)

            def make_callback(self, familia_key: str):
                async def callback(button_interaction: discord.Interaction):
                    await Paineis.handle_soldier_join_static(button_interaction, familia_key, guild)
                return callback

        view = FamilyButtonsView()
        await interaction.response.send_message("🗡️ Escolhe a família a que te queres juntar:", view=view, ephemeral=True)


class Paineis(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ------- Métodos estáticos (chamados pelas views temporárias) -------
    @staticmethod
    async def handle_capo_claim_static(interaction: discord.Interaction, familia_key: str, guild: discord.Guild):
        member = interaction.user
        cargo_capo = discord.utils.get(guild.roles, name="Capo")
        nome_familia = FAMILIAS[familia_key]
        cargo_familia = discord.utils.get(guild.roles, name=nome_familia)

        if not cargo_familia:
            await interaction.response.send_message(f"❌ O cargo **{nome_familia}** não existe.", ephemeral=True)
            return

        for m in list(cargo_familia.members):
            if cargo_capo not in m.roles:
                try:
                    await m.remove_roles(cargo_familia)
                except Exception:
                    pass

        capos_na_familia = [m for m in cargo_familia.members if cargo_capo in m.roles]
        if capos_na_familia:
            await interaction.response.send_message(f"⚠️ A **{nome_familia}** já tem um Capo ativo.", ephemeral=True)
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
            canal_anuncios = discord.utils.get(categoria.text_channels, name="📜-announcements")
            if not canal_anuncios:
                canal_antigo = discord.utils.get(categoria.text_channels, name="📜-capo-announcements")
                if canal_antigo:
                    await canal_antigo.edit(name="📜-announcements")
                    canal_anuncios = canal_antigo

            overwrites_announcements = {
                guild.default_role: discord.PermissionOverwrite(read_messages=False),
                cargo_familia: discord.PermissionOverwrite(read_messages=True, send_messages=False),
                cargo_capo: discord.PermissionOverwrite(read_messages=True, send_messages=True)
            }
            if not canal_anuncios:
                await guild.create_text_channel("📜-announcements", category=categoria, overwrites=overwrites_announcements, topic=f"Official announcements for {nome_familia}.")
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
                await guild.create_text_channel("🚨-warnings", category=categoria, overwrites=overwrites_warnings, topic=f"Canal de warnings exclusivo para o Capo da {nome_familia}.")
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

    @staticmethod
    async def handle_soldier_join_static(interaction: discord.Interaction, familia_key: str, guild: discord.Guild):
        member = interaction.user
        cargo_soldier = discord.utils.get(guild.roles, name="Soldier")
        nome_familia = FAMILIAS[familia_key]
        cargo_fam = discord.utils.get(guild.roles, name=nome_familia)

        if not cargo_fam:
            await interaction.response.send_message("Erro: cargo da família não encontrado.", ephemeral=True)
            return

        qtd = sum(1 for m in cargo_fam.members if cargo_soldier in m.roles)
        if qtd >= LIMITE_SOLDIERS:
            await interaction.response.send_message(f"⚠️ A **{nome_familia}** já está cheia!", ephemeral=True)
            return

        # Remove todas as outras famílias antes de adicionar a nova
        for f_nome in FAMILIAS.values():
            c_antigo = discord.utils.get(guild.roles, name=f_nome)
            if c_antigo in member.roles:
                await member.remove_roles(c_antigo)

        await member.add_roles(cargo_fam)
        await interaction.response.send_message(f"🗡️ Foste alistado na **{nome_familia}**!", ephemeral=True)
        await enviar_log_mafia(guild, "🗡️ NOVO SOLDADO ALISTADO", f"{member.mention} juntou-se à **{nome_familia}**!", discord.Color.blue())

    # ------- Listener unificado de actualização de membro (LOGS MELHORADOS) -------
    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        cargo_capo = discord.utils.get(after.guild.roles, name="Capo")
        cargo_soldier = discord.utils.get(after.guild.roles, name="Soldier")

        # ------------------------------------------------------------
        # 1) Capo perdeu o cargo → remove-o de todas as famílias
        # ------------------------------------------------------------
        if cargo_capo:
            was_capo = cargo_capo in before.roles
            is_capo = cargo_capo in after.roles
            if was_capo and not is_capo:
                for nome_familia in FAMILIAS.values():
                    cargo_fam = discord.utils.get(after.guild.roles, name=nome_familia)
                    if cargo_fam and cargo_fam in after.roles:
                        try:
                            await after.remove_roles(cargo_fam)
                        except discord.Forbidden:
                            pass
                await enviar_log_mafia(
                    after.guild,
                    "🔻 CAPO DEGRADADO",
                    f"{after.mention} deixou de ser Capo e foi removido de todas as famílias.",
                    discord.Color.orange()
                )

        # ------------------------------------------------------------
        # 2) Soldier perdeu o cargo → remove-o da família atual
        # ------------------------------------------------------------
        if cargo_soldier:
            was_soldier = cargo_soldier in before.roles
            is_soldier = cargo_soldier in after.roles
            if was_soldier and not is_soldier:
                for nome_familia in FAMILIAS.values():
                    cargo_fam = discord.utils.get(after.guild.roles, name=nome_familia)
                    if cargo_fam and cargo_fam in after.roles:
                        try:
                            await after.remove_roles(cargo_fam)
                        except discord.Forbidden:
                            pass
                await enviar_log_mafia(
                    after.guild,
                    "🗡️ SOLDADO PERDEU PATENTE",
                    f"{after.mention} deixou de ser Soldier e foi removido da sua família.",
                    discord.Color.orange()
                )

        # ------------------------------------------------------------
        # 3) Alterações manuais de roles de família (ganhou ou perdeu)
        # ------------------------------------------------------------
        roles_familia_antes = set(r.name for r in before.roles if r.name in FAMILIAS.values())
        roles_familia_depois = set(r.name for r in after.roles if r.name in FAMILIAS.values())

        ganhou = roles_familia_depois - roles_familia_antes
        perdeu = roles_familia_antes - roles_familia_depois

        for nome_fam in ganhou:
            await enviar_log_mafia(
                after.guild,
                "📥 NOVA FAMÍLIA ATRIBUÍDA",
                f"{after.mention} recebeu a role **{nome_fam}**.",
                discord.Color.green()
            )
        for nome_fam in perdeu:
            await enviar_log_mafia(
                after.guild,
                "📤 FAMÍLIA REMOVIDA",
                f"{after.mention} perdeu a role **{nome_fam}**.",
                discord.Color.red()
            )

        # ------------------------------------------------------------
        # 4) Impedir Soldier de acumular várias famílias (mantém a 1ª)
        # ------------------------------------------------------------
        if cargo_soldier and cargo_soldier in after.roles:
            roles_familia = [r for r in after.roles if r.name in FAMILIAS.values()]
            if len(roles_familia) > 1:
                for role in roles_familia[1:]:
                    try:
                        await after.remove_roles(role)
                    except discord.Forbidden:
                        pass
                await enviar_log_mafia(
                    after.guild,
                    "🛡️ FAMÍLIA DUPLICADA BLOQUEADA",
                    f"{after.mention} tentou acumular múltiplas famílias. Foram removidas as excedentes.",
                    discord.Color.orange()
                )

    # ------- Listener de saída do servidor -------
    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        cargo_capo = discord.utils.get(member.guild.roles, name="Capo")
        cargo_soldier = discord.utils.get(member.guild.roles, name="Soldier")

        # Verifica se o membro que saiu era Capo ou Soldier
        era_capo = cargo_capo in member.roles if cargo_capo else False
        era_soldier = cargo_soldier in member.roles if cargo_soldier else False

        if era_capo or era_soldier:
            familias = [r.name for r in member.roles if r.name in FAMILIAS.values()]
            tipo = "Capo" if era_capo else "Soldier"
            detalhes = f"Pertencia a: {', '.join(familias)}" if familias else "Não tinha família."
            await enviar_log_mafia(
                member.guild,
                f"🚪 {tipo.upper()} SAIU DO SERVIDOR",
                f"{member.mention} ({member.display_name}) saiu do servidor.\n{detalhes}",
                discord.Color.dark_gray()
            )

    # ------- Comandos de setup -------
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
            value="The commander of each Family (Corleone, Gambino, Genovese, Lucchese, Bonanno, Colombo). \n"
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
