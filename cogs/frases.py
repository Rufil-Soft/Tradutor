import os
import random
import asyncio
import discord
from discord.ext import commands
from cogs.traducao import TranslateView
from groq import AsyncGroq

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


frase_manager = FraseManager(FRASES_EN)


class Frases(commands.Cog):
    """Aquiles responde com IA (Groq) quando mencionado."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.groq_client = None
        self.groq_model = "llama3-8b-8192"
        self._init_groq()

    def _init_groq(self):
        api_key = os.getenv("GROQ_API_KEY")
        if api_key:
            self.groq_client = AsyncGroq(api_key=api_key)
            print("[FRASES] Cliente Groq inicializado.")
        else:
            print("[FRASES] ⚠️ GROQ_API_KEY não definida. A usar apenas frases fixas.")

    async def _gerar_resposta_ia(self, frase_base: str, mensagem_usuario: str) -> str:
        if not self.groq_client:
            return None

        system_prompt = (
            "You are Aquiles, the Don of a cannabis-themed mafia family. "
            "You are witty, wise, and speak like a classic mafia godfather but with a cannabis twist. "
            "Keep your answers short (2-3 sentences), in English, and always cool and respectful. "
            "You can refer to cannabis as 'herb', 'medicine', 'green gold', etc. "
            "Never break character."
        )
        user_prompt = (
            f"Context: Someone just said: \"{mensagem_usuario}\"\n"
            f"Base idea to use (but you can adapt): \"{frase_base}\"\n\n"
            "Generate a natural, short reply as Aquiles the Don."
        )

        try:
            response = await self.groq_client.chat.completions.create(
                model=self.groq_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=150,
                temperature=0.8,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            print(f"[FRASES] Erro na API Groq: {e}")
            return None

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        if self.bot.user in message.mentions:
            # 1. Apaga a mensagem original
            try:
                await message.delete()
            except discord.Forbidden:
                pass

            # 2. Republica a mensagem do utilizador, como o traducao.py faria
            conteudo_formatado = f"<@{message.author.id}>: {message.content}"
            files = [await a.to_file() for a in message.attachments]
            await message.channel.send(
                content=conteudo_formatado,
                files=files,
                view=TranslateView(),
                allowed_mentions=discord.AllowedMentions(users=False)
            )

            # 3. Aquiles responde
            frase_base = frase_manager.next()
            resposta = await self._gerar_resposta_ia(frase_base, message.content)
            if not resposta:
                resposta = frase_base

            async with message.channel.typing():
                await asyncio.sleep(1)
                await message.channel.send(f"💬 {resposta}", view=TranslateView())

    @commands.command(name="frase")
    async def frase(self, ctx):
        """Solta uma frase aleatória do Aquiles, com botão de tradução."""
        frase_original = frase_manager.next()
        await ctx.send(f"🗣️ {frase_original}", view=TranslateView())


async def setup(bot: commands.Bot):
    await bot.add_cog(Frases(bot))
