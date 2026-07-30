import discord
from discord.ext import commands
from discord import app_commands
import asyncio
from deep_translator import GoogleTranslator
from config import FAMILIAS, LIMITE_SOLDIERS
from cogs.logs import enviar_log_mafia
from bot import bot

class RanksView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Read Ranks in my language", style=discord.ButtonStyle.secondary, emoji="🌐", custom_id="translate_ranks")
    async def translate_ranks(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        user_locale = str(interaction.locale).split("-")[0] or "pt"
        ranks_texto = (
            "🏛️ **ORGANIZATION & HIERARCHY — COSA NOSTRA**\n\n"
            "\"In our family, there is no room for freelancers...\"\n\n"
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

class CapoRegistryView(discord.ui.View):
    # ... (todo o código do painel dos capos, igual ao que já tens, adaptado para importar FAMILIAS e enviar_log_mafia)
    pass

class SoldierEnlistView(discord.ui.View):
    # ... (todo o código do painel dos soldiers)
    pass


class Paineis(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="setup_ranks")
    @commands.has_permissions(administrator=True)
    async def setup_ranks(self, ctx):
        # ... código que publica o embed com RanksView
        pass

    @commands.command(name="setup_capo")
    @commands.has_permissions(administrator=True)
    async def setup_capo(self, ctx):
        # ... código que publica a mensagem com CapoRegistryView
        pass

    @commands.command(name="setup_soldier")
    @commands.has_permissions(administrator=True)
    async def setup_soldier(self, ctx):
        # ... código que publica a mensagem com SoldierEnlistView
        pass

async def setup(bot: commands.Bot):
    await bot.add_cog(Paineis(bot))
