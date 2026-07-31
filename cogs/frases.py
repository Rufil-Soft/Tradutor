import asyncio
import random
import discord
from discord.ext import commands
from deep_translator import GoogleTranslator
from cogs.traducao import TranslateView  # view persistente do botão 🌍

FRASES_EN = [
    "Speak, consigliere. The herb is cured and business is booming.",
    "In the mafia, cannabis is like loyalty: it only blooms when well cultivated.",
    "This ain't no ordinary joint… it's a 'made in Italy' joint.",
    "Omertà applies to smoking too: no coughing out secrets.",
    "A Don who doesn't share his weed ain't worth the family's respect.",
    "Cannabis calms even the fiercest Capo.",
    "Loyalty is like a good strain: rare and valuable.",
    "I traded my lupara for a vaporizer. Modern times, Don.",
    "The mafia recycles: we turn debts into opportunities and leaves into joy.",
    "They say the Don has a secret grow room behind the altar.",
    "Never knock on the Don's door empty-handed... bring a joint.",
    "In our club, the ledger smells like skunk.",
    "A true gangster knows a shared joint is a peace treaty.",
    "This year's harvest was blessed by all the saints… and the godfather.",
    "The herb is green, money is too. Only the cut is different.",
    "The only 'white' we allow is joint ash.",
    "The Don never smokes alone – it's a matter of respect.",
    "Smoking before a family meeting helps keep the peace. Even if it's just the 'family'.",
    "Our code of honor includes Friday smoke sessions.",
    "I don't bribe cops… I offer them a special brownie.",
    "Capo di tutti i fumatori.",
    "The Don said: 'Cannabis unites more than blood.'",
    "Omertà: you didn't see, you didn't hear, you didn't smoke. (But pretend you did.)",
    "The only war we want is a roll-off.",
    "This family is tighter than a Gorilla Glue bud.",
    "We sell protection, but give discounts for snacks.",
    "The Don is in a good mood: the latest harvest broke records.",
    "Smoke the peace pipe, not the war gun.",
    "Our lawyer is also our dealer. Convenient.",
    "When life gives you lemons, trade them for a gram of Lemon Haze.",
    "The only debt we collect is for the munchies.",
    "The accountant came to do the books and left with red eyes.",
    "The Don doesn't authorize hits… just torching a few grams.",
    "The Cannabis Mafia's motto: 'Peace, Love, and Respect... and 30% of the profit.'",
    "Don't confuse the oregano packet with the packet's oregano.",
    "Our 'club' has more smokers than the whole of Sicily.",
    "Smoke like a Capo, think like a Don.",
    "First smoke, then solve problems. – Sun Tzu, probably.",
    "True power isn't in the gun, it's in the strain.",
    "This family knows no stress, only top-shelf strains.",
    "Herb is medicine, the mafia is the hospital.",
    "I traded my pistol for a blunt and I've never been happier.",
    "My Don said: 'Those who smoke together stay together.'",
    "The only protection we offer is against drought.",
    "If the cops ask, it's oregano.",
    "The godfather makes you an offer: smoke or smoke.",
    "Cannabis is the only witness that never talks.",
    "The family meeting starts when the joint ends.",
    "This ain't a hideout… it's a classy chill room.",
    "Judgment day has come: we decide the best strain of the month."
]


class FraseManager:
    """Garante que as frases não se repitam até que todas tenham sido usadas."""
    def __init__(self, frases):
        self._frases = frases.copy()
        self._fila = []
        self._refill()

    def _refill(self):
        self._fila = self._frases.copy()
        random.shuffle(self._fila)

    def next(self) -> str:
        if not self._fila:
            self._refill()
        return self._fila.pop()


# Instância global para manter o ciclo das frases ao longo da execução
frase_manager = FraseManager(FRASES_EN)


class Frases(commands.Cog):
    """Responde com frases engraçadas (máfia + cannabis) quando o Aquiles é mencionado."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        if self.bot.user in message.mentions:
           
            frase_original = frase_manager.next()
            await message.channel.send(f"💬 {frase_original}", view=TranslateView())

    @commands.command(name="frase")
    async def frase(self, ctx):
        """Solta uma frase aleatória do Aquiles, com botão de tradução."""
        frase_original = frase_manager.next()
        await ctx.send(f"🗣️ {frase_original}", view=TranslateView())


async def setup(bot: commands.Bot):
    await bot.add_cog(Frases(bot))
