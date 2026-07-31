import random
import asyncio
import discord
from discord.ext import commands
from deep_translator import GoogleTranslator

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

# Cache de traduções
_t_cache = {}

async def translate(key: str, target: str) -> str:
    """Traduz 'key' para 'target' (código de 2 letras). Cache interno."""
    if target == "pt":
        return key  # mantém original se for português (ou podes optar por traduzir para PT também)
    cache_key = (key, target)
    if cache_key in _t_cache:
        return _t_cache[cache_key]
    try:
        res = await asyncio.to_thread(GoogleTranslator(source='auto', target=target).translate, key)
        _t_cache[cache_key] = res
        return res
    except Exception:
        return key  # fallback

class Frases(commands.Cog):
    """Responde com frases engraçadas (máfia + cannabis) quando o Aquiles é mencionado."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        # Verifica se o bot foi mencionado diretamente
        if self.bot.user in message.mentions:
            frase_original = random.choice(FRASES_EN)
            user_locale = str(message.author.locale).split("-")[0] if hasattr(message.author, 'locale') else "pt"
            frase_traduzida = await translate(frase_original, user_locale)
            await message.channel.send(f"💬 {frase_traduzida}")

    @commands.command(name="frase")
    async def frase(self, ctx):
        """Solta uma frase aleatória do Aquiles, traduzida automaticamente."""
        frase_original = random.choice(FRASES_EN)
        user_locale = str(ctx.author.locale).split("-")[0] if hasattr(ctx.author, 'locale') else "pt"
        frase_traduzida = await translate(frase_original, user_locale)
        await ctx.send(f"🗣️ {frase_traduzida}")

async def setup(bot: commands.Bot):
    await bot.add_cog(Frases(bot))
