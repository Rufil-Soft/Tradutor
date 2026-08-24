import os
import random
import asyncio
import re
import discord
from discord.ext import commands
from cogs.traducao import TranslateView, registar_mensagem
from groq import AsyncGroq

VERBOSE_LOGS = False  # Coloca True se precisares de logs detalhados da IA

FRASES_EN = [
    "Speak, consigliere. The herb is cured and business is booming.",
    # ... (mantém a lista completa das frases) ...
]

AMOSTRA_ESTILO = 6
MIN_CARACTERES_RESPOSTA = 8
MIN_CARACTERES_RESPOSTA_CORTADA = 30

frase_manager = None

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

def _resposta_valida(texto: str, finish_reason: str) -> bool:
    if not texto:
        return False
    texto = texto.strip()
    if not texto:
        return False
    if texto in FRASES_EN:
        return False
    if len(texto) < MIN_CARACTERES_RESPOSTA:
        return False
    if finish_reason == "length" and len(texto) < MIN_CARACTERES_RESPOSTA_CORTADA:
        return False
    return True

class Frases(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.groq_client = None
        self.groq_model = "openai/gpt-oss-20b"
        self.delete_lock = asyncio.Lock()
        self._init_groq()

    def _init_groq(self):
        api_key = os.getenv("GROQ_API_KEY")
        if api_key:
            self.groq_client = AsyncGroq(api_key=api_key)
            print("[FRASES] Cliente Groq inicializado.")
        else:
            print("[FRASES] ⚠️ GROQ_API_KEY não definida. A usar apenas frases fixas.")

    async def apagar_com_retry(self, message: discord.Message, tentativas: int = 3) -> bool:
        async with self.delete_lock:
            for i in range(tentativas):
                try:
                    await message.delete()
                    return True
                except discord.HTTPException as e:
                    if e.status == 429 and i < tentativas - 1:
                        retry_after = getattr(e, 'retry_after', 1.0)
                        print(f"[FRASES] Rate limit ao apagar {message.id}, retry em {retry_after:.2f}s")
                        await asyncio.sleep(retry_after + 0.5)
                        continue
                    else:
                        print(f"[FRASES] Falha ao apagar mensagem {message.id}: {e}")
                        return False
                except discord.Forbidden:
                    print(f"[FRASES] Sem permissão para apagar {message.id}")
                    return False
            return False

    async def _gerar_resposta_ia(self, mensagem_usuario: str) -> str:
        if not self.groq_client:
            return None

        texto_limpo = re.sub(r"<@!?[0-9]+>", "", mensagem_usuario).strip()
        if not texto_limpo:
            texto_limpo = mensagem_usuario

        exemplos = frase_manager.amostra(AMOSTRA_ESTILO)
        exemplos_texto = "\n".join(f"- {frase}" for frase in exemplos)

        system_prompt = (
            "You are Aquiles, the Don of a cannabis-themed mafia family. "
            "You are witty, wise, and laid-back, like a classic mafia godfather with a cannabis twist. "
            "You answer directly to the user's message, in a natural conversational way. "
            "Use the examples below only as a reference for tone and humor style, "
            "but never repeat them word-for-word. Always create a fresh, relevant reply.\n\n"
            f"Examples of your style:\n{exemplos_texto}\n\n"
            "Instructions:\n"
            "- Respond to what the user said, not with a random phrase.\n"
            "- Keep your reply short (2-3 sentences).\n"
            "- Speak in English, unless the user writes in Portuguese; then reply in Portuguese.\n"
            "- Prefer common words (cannabis, marijuana, weed, herb) to help translation."
        )

        user_prompt = (
            f"The user said: \"{texto_limpo}\"\n\n"
            "Respond as Aquiles."
        )

        modelos = [
            self.groq_model,
            "openai/gpt-oss-120b",
        ]

        for modelo in modelos:
            try:
                response = await self.groq_client.chat.completions.create(
                    model=modelo,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    max_tokens=600,
                    temperature=0.85,
                    reasoning_effort="low",
                    reasoning_format="hidden",
                )
                finish_reason = response.choices[0].finish_reason
                if VERBOSE_LOGS:
                    print(f"[FRASES] Modelo: {modelo}")
                    print(f"[FRASES] Finish reason: {finish_reason}")

                resposta_gerada = response.choices[0].message.content
                if VERBOSE_LOGS:
                    print(f"[FRASES] Conteúdo bruto: {resposta_gerada!r}")

                if resposta_gerada:
                    resposta_gerada = resposta_gerada.strip()

                if _resposta_valida(resposta_gerada, finish_reason):
                    if VERBOSE_LOGS:
                        print(f"[FRASES] Resposta da IA: {resposta_gerada}")
                    return resposta_gerada

                print(f"[FRASES] Modelo {modelo} devolveu resposta vazia/curta/truncada "
                      f"(finish_reason={finish_reason!r}). Tentando próximo...")
            except Exception as e:
                print(f"[FRASES] Erro na API Groq com modelo {modelo}: {e if VERBOSE_LOGS else 'erro (ver detalhe com VERBOSE_LOGS=True)'}")

        return None

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        if self.bot.user in message.mentions:
            conteudo_formatado = f"<@{message.author.id}>: {message.content}"

            try:
                msg_echo = await message.channel.send(
                    content=conteudo_formatado,
                    files=[await a.to_file() for a in message.attachments],
                    view=TranslateView(),
                    allowed_mentions=discord.AllowedMentions(users=False)
                )
            except Exception as e:
                print(f"[FRASES] Erro ao enviar echo: {e}")
                return

            sucesso = await self.apagar_com_retry(message)
            if not sucesso:
                try:
                    await msg_echo.delete()
                except Exception as e:
                    print(f"[FRASES] Erro ao apagar echo: {e}")
                return

            registar_mensagem(msg_echo.id, conteudo_formatado, message.content)

            resposta = await self._gerar_resposta_ia(message.content)
            if not resposta:
                resposta = frase_manager.next()

            base_resposta = f"💬 {resposta}"
            try:
                msg_resposta = await message.channel.send(base_resposta, view=TranslateView())
                registar_mensagem(msg_resposta.id, base_resposta, resposta)
            except Exception as e:
                print(f"[FRASES] Erro ao enviar resposta IA: {e}")

    @commands.command(name="frase")
    async def frase(self, ctx):
        frase_original = frase_manager.next()
        base = f"🗣️ {frase_original}"
        msg = await ctx.send(base, view=TranslateView())
        registar_mensagem(msg.id, base, frase_original)

    @commands.command(name="iatest")
    async def iatest(self, ctx, *, texto: str):
        resposta = await self._gerar_resposta_ia(texto)
        if resposta:
            await ctx.send(f"🧠 IA: {resposta}")
        else:
            await ctx.send("❌ IA falhou ou devolveu vazio.")

async def setup(bot: commands.Bot):
    await bot.add_cog(Frases(bot))
