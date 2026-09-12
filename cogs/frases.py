import os
import asyncio
import re
import discord
from discord.ext import commands
from cogs.traducao import TranslateView, registar_mensagem
from openai import AsyncOpenAI

VERBOSE_LOGS = True

# Resposta de fallback quando a IA falha (curta e temática, mas genérica)
FALLBACK_PT = "Estou com lag mental, tenta outra vez."

# Padrões que indicam que o modelo vazou raciocínio interno em vez de
# dar a resposta final. Rejeitamos e tentamos o próximo modelo.
_PADROES_RACIOCINIO = (
    "thinking process",
    "analyze user input",
    "identify key constraints",
    "brainstorming content",
    "here's a thinking",
    "here is a thinking",
    "chain of thought",
    "let me think",
    "step 1:",
    "step 2:",
    "1. **analyze",
    "**analyze user",
    "user input:",
    "**constraints",
    "i need to respond",
    "must use european",
    "**brainstorm",
)

MIN_CARACTERES_RESPOSTA = 8


def _resposta_valida(texto: str, finish_reason: str) -> bool:
    if not texto:
        return False
    texto = texto.strip()
    if len(texto) < MIN_CARACTERES_RESPOSTA:
        return False
    # Se foi cortada por limite de tokens, exigimos um mínimo maior
    if finish_reason == "length" and len(texto) < 30:
        return False
    # Rejeita raciocínio interno vazado
    t_lower = texto.lower()
    for padrao in _PADROES_RACIOCINIO:
        if padrao in t_lower:
            return False
    return True


class Frases(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.api_client = None
        # "openrouter/free" é um router mantido pela própria OpenRouter que
        # escolhe automaticamente, em cada pedido, um modelo gratuito
        # disponível naquele momento. Evita ficarmos presos a slugs fixos
        # (ex.: minimax/minimax-m2.7:free) que a OpenRouter descontinua ou
        # reclassifica como pagos sem aviso — foi exatamente isso que causou
        # o 404 no minimax no log mais recente.
        #
        # Mantemos 2 modelos fixos como último recurso, para o caso raro de
        # o próprio router falhar; se algum destes começar a dar 404/410 de
        # forma persistente, está descontinuado e deve ser substituído —
        # confirma sempre em https://openrouter.ai/models?fmt=cards&max_price=0
        self.modelos = [
            "openrouter/free",
            "nvidia/nemotron-3-ultra-550b-a55b:free",
            "google/gemma-4-31b-it:free",
        ]
        self.delete_lock = asyncio.Lock()
        self._init_api()

    def _init_api(self):
        api_key = os.getenv("OPENROUTER_API_KEY")
        if api_key:
            self.api_client = AsyncOpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=api_key,
            )
            print("[FRASES] Cliente OpenRouter inicializado.")
        else:
            print("[FRASES] AVISO: OPENROUTER_API_KEY nao definida. Respostas serao fallback.")

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
                    print(f"[FRASES] Sem permissao para apagar {message.id}")
                    return False
            return False

    async def _gerar_resposta_ia(self, mensagem_usuario: str) -> str:
        if not self.api_client:
            return None

        texto_limpo = re.sub(r"<@!?[0-9]+>", "", mensagem_usuario).strip()
        if not texto_limpo:
            return None

        system_prompt = (
            "Es o Aquiles, um jogador veterano e carismatico de Aion 2. "
            "Respondes de forma curta, engracada e natural, como se estivesses a conversar "
            "com um amigo no chat do jogo. O teu objetivo e fazer a pessoa rir ou sorrir, "
            "com piadas leves sobre a vida de MMO (grind, ganks, RNG, lag, P2W, asas, "
            "Elyos vs Asmodians, o Abismo, legions, manastones, PvP).\n\n"

            "REGRAS OBRIGATORIAS:\n"
            "1. Escreves SEMPRE em portugues europeu (PT-PT). Nunca portugues do Brasil.\n"
            "   - Usa 'tu' em vez de 'voce'.\n"
            "   - Usa 'estou a fazer' em vez de 'estou fazendo'.\n"
            "   - Usa 'fixe' em vez de 'legal'/'bacana'.\n"
            "   - Usa 'pa' em vez de 'cara'.\n"
            "2. Responde APENAS com a resposta final. NUNCA escrevas o teu raciocinio, "
            "   listas, 'thinking process', 'analyze user input', nem nada do genero.\n"
            "3. Maximo 3 frases curtas.\n"
            "4. NUNCA menciones que es uma IA. Mantem sempre a personagem.\n"
            "5. Mantem tudo leve e amigavel. Sem insultos, sem toxicidade, sem humor negro.\n"
            "6. Responde sempre ao que a pessoa disse, nao mudes de assunto."
        )

        user_prompt = f"Mensagem do jogador: \"{texto_limpo}\"\n\nResponde como o Aquiles."

        for modelo in self.modelos:
            try:
                response = await self.api_client.chat.completions.create(
                    model=modelo,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    max_tokens=300,
                    temperature=0.85,
                )

                # Alguns modelos ':free' da OpenRouter, quando o provedor
                # upstream falha a meio do pedido, devolvem um objeto de
                # resposta "válido" (sem lançar HTTPException) mas com
                # 'choices' a None/vazio. Sem esta verificação, o acesso a
                # response.choices[0] rebenta com
                # "'NoneType' object is not subscriptable" — foi isto que
                # aconteceu ao nemotron no log mais recente.
                choices = getattr(response, "choices", None)
                if not choices:
                    erro_upstream = getattr(response, "error", None)
                    print(f"[FRASES] Modelo {modelo} devolveu resposta sem 'choices'. "
                          f"Erro upstream reportado: {erro_upstream!r}")
                    continue

                finish_reason = choices[0].finish_reason

                if VERBOSE_LOGS:
                    print(f"[FRASES] Modelo: {modelo} | finish_reason: {finish_reason}")

                resposta_gerada = choices[0].message.content
                if VERBOSE_LOGS:
                    print(f"[FRASES] Conteudo bruto: {resposta_gerada!r}")

                if resposta_gerada:
                    resposta_gerada = resposta_gerada.strip()

                if _resposta_valida(resposta_gerada, finish_reason):
                    if VERBOSE_LOGS:
                        print(f"[FRASES] OK: {resposta_gerada}")
                    return resposta_gerada

                print(f"[FRASES] Modelo {modelo} devolveu resposta invalida. A tentar proximo...")
            except Exception as e:
                print(f"[FRASES] Erro no modelo {modelo}: {e}")

        return None

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        if self.bot.user in message.mentions:
            conteudo_formatado = f"<@{message.author.id}>: {message.content}"

            # 1) Envia o echo (mensagem do utilizador + botão 🌍)
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

            # 2) Tenta apagar a mensagem original
            sucesso = await self.apagar_com_retry(message)
            if not sucesso:
                try:
                    await msg_echo.delete()
                except Exception:
                    pass
                return

            registar_mensagem(msg_echo.id, conteudo_formatado, message.content)

            # 3) Gera a resposta da IA (ou usa fallback)
            async with message.channel.typing():
                resposta = await self._gerar_resposta_ia(message.content)
            if not resposta:
                resposta = FALLBACK_PT

            base_resposta = f"🎮 {resposta}"
            try:
                msg_resposta = await message.channel.send(base_resposta, view=TranslateView())
                registar_mensagem(msg_resposta.id, base_resposta, resposta)
            except Exception as e:
                print(f"[FRASES] Erro ao enviar resposta IA: {e}")

    @commands.command(name="frase")
    async def frase(self, ctx):
        """Fallback simples: responde uma frase temática."""
        await ctx.send(f"🎮 {FALLBACK_PT}", view=TranslateView())

    @commands.command(name="iatest")
    async def iatest(self, ctx, *, texto: str):
        resposta = await self._gerar_resposta_ia(texto)
        if resposta:
            await ctx.send(f"🧠 IA: {resposta}")
        else:
            await ctx.send(f"❌ IA falhou. Fallback: {FALLBACK_PT}")


async def setup(bot: commands.Bot):
    await bot.add_cog(Frases(bot))
