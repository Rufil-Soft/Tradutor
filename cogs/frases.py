import os
import random
import asyncio
import discord
from discord.ext import commands
from cogs.traducao import TranslateView, registar_mensagem
from groq import AsyncGroq

# Mantém a lista original de frases
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

AMOSTRA_ESTILO = 6


class FraseManager:
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

    def amostra(self, k: int) -> list:
        k = min(k, len(self._frases))
        return random.sample(self._frases, k)


frase_manager = FraseManager(FRASES_EN)


class Frases(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.groq_client = None
        self.groq_model = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")
        self._init_groq()

    def _init_groq(self):
        api_key = os.getenv("GROQ_API_KEY")
        if api_key:
            self.groq_client = AsyncGroq(api_key=api_key)
            print("[FRASES] Cliente Groq inicializado.")
        else:
            print("[FRASES] ⚠️ GROQ_API_KEY não definida. A usar apenas frases fixas.")

    async def _gerar_resposta_ia(self, mensagem_usuario: str) -> str | None:
        if not self.groq_client:
            return None

        if not mensagem_usuario or not mensagem_usuario.strip():
            return None

        exemplos = frase_manager.amostra(AMOSTRA_ESTILO)
        exemplos_texto = "\n".join(f"- {frase}" for frase in exemplos)

        system_prompt = (
            "You are Aquiles, the Don of a cannabis-themed mafia family. "
            "You have a sharp, wise, and laid-back mafia godfather personality with a cannabis twist. "
            "Use the example phrases below as inspiration for tone, vocabulary, and humor, "
            "but NEVER repeat them word-for-word. Always create a fresh answer that directly responds to the user's message.\n\n"
            f"Examples of your style:\n{exemplos_texto}\n\n"
            "Instructions:\n"
            "- Answer the user's specific question or react to their statement.\n"
            "- Stay in character at all times.\n"
            "- Keep your reply short (2-3 sentences).\n"
            "- Prefer common words (cannabis, marijuana, weed, herb) over obscure slang, to help translation."
        )

        user_prompt = (
            f"The user said: \"{mensagem_usuario.strip()}\"\n\n"
            "Respond as Aquiles, using the example style but focused on what was said."
        )

        try:
            response = await asyncio.wait_for(
                self.groq_client.chat.completions.create(
                    model=self.groq_model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    max_tokens=150,
                    temperature=0.9,
                ),
                timeout=15
            )
            resposta_gerada = response.choices[0].message.content.strip()
            print(f"[FRASES] Resposta da IA: {resposta_gerada}")

            # Se a IA devolver vazio ou copiar uma frase fixa, consideramos falha
            if not resposta_gerada:
                return None
            if resposta_gerada in FRASES_EN:
                return None
            if len(resposta_gerada) > 500:
                resposta_gerada = resposta_gerada[:497] + "..."
            return resposta_gerada
        except Exception as e:
            print(f"[FRASES] Erro na API Groq: {e}")
            return None

    def _limpar_mencao(self, conteudo: str) -> str:
        """Remove menções do bot antes de enviar para a IA."""
        texto = conteudo

        # Menção clássica <@ID> ou <@!ID>
        if self.bot.user:
            for mention in (
                f"<@{self.bot.user.id}>",
                f"<@!{self.bot.user.id}>",
                self.bot.user.mention
            ):
                texto = texto.replace(mention, "")

        return texto.strip()

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        if not self.bot.user or self.bot.user not in message.mentions:
            return

        try:
            await message.delete()
        except discord.Forbidden:
            pass

        conteudo_formatado = f"<@{message.author.id}>: {message.content}"
        files = [await a.to_file() for a in message.attachments]
        msg_echo = await message.channel.send(
            content=conteudo_formatado,
            files=files,
            view=TranslateView(),
            allowed_mentions=discord.AllowedMentions(users=False)
        )
        registar_mensagem(msg_echo.id, conteudo_formatado, message.content)

        # Usa o texto sem a menção ao bot para a IA
        texto_para_ia = self._limpar_mencao(message.content)

        # Se não houver texto relevante, usa frase fixa diretamente
        if not texto_para_ia:
            resposta = frase_manager.next()
        else:
            resposta = await self._gerar_resposta_ia(texto_para_ia)
            if not resposta:
                resposta = frase_manager.next()

        async with message.channel.typing():
            await asyncio.sleep(1)
            base_resposta = f"💬 {resposta}"
            msg_resposta = await message.channel.send(base_resposta, view=TranslateView())
            registar_mensagem(msg_resposta.id, base_resposta, resposta)

    @commands.command(name="frase")
    async def frase(self, ctx):
        frase_original = frase_manager.next()
        base = f"🗣️ {frase_original}"
        msg = await ctx.send(base, view=TranslateView())
        registar_mensagem(msg.id, base, frase_original)

    @commands.command(name="iatest")
    async def iatest(self, ctx, *, texto: str):
        """Testa a IA diretamente, sem fallback."""
        resposta = await self._gerar_resposta_ia(texto)
        if resposta:
            await ctx.send(f"🧠 IA: {resposta}")
        else:
            await ctx.send("❌ IA falhou ou devolveu vazio.")


async def setup(bot: commands.Bot):
    await bot.add_cog(Frases(bot))
