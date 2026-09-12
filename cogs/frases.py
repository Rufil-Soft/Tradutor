import os
import time
import random
import asyncio
import re
import discord
from discord.ext import commands
from cogs.traducao import TranslateView, registar_mensagem
from openai import AsyncOpenAI

VERBOSE_LOGS = True

# Timeout por chamada individual à API (segundos). Modelos ':free' partilhados
# podem "pendurar-se" sob carga; falhar depressa e passar ao próximo modelo
# da lista é preferível a deixar o utilizador à espera vários minutos.
API_TIMEOUT_SEGUNDOS = 15

# Cooldown por utilizador entre menções ao bot (segundos). Sem isto, qualquer
# pessoa pode disparar uma chamada externa por cada menção, sem limite —
# agrava os rate-limits partilhados da OpenRouter e, se algum dia usares um
# modelo pago no fallback, também é uma via de abuso de custo.
COOLDOWN_SEGUNDOS = 10
_ultima_mencao = {}  # user_id -> timestamp da última menção processada

# Frases de fallback quando a IA falha (todos os modelos indisponíveis, ou só
# devolveram lixo/raciocínio vazado). Uma lista pequena mas com variedade,
# para o utilizador não ver sempre a mesma frase repetida se a IA estiver
# instável durante algum tempo.
FRASES_FALLBACK_PT = [
    "Estou com lag mental, tenta outra vez.",
    "Server dos meus pensamentos caiu, dá-me um segundo.",
    "Fiquei preso num loading screen aqui dentro, repete lá isso.",
    "Isto que dissestes fez-me crashar tipo boss bugado. Outra vez?",
    "Tive um disconnect a meio do raciocínio, pa. Manda de novo.",
    "Ainda a fazer respawn das ideias, espera aí.",
]


def _frase_fallback() -> str:
    return random.choice(FRASES_FALLBACK_PT)

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
        # "meta-llama/llama-3.3-70b-instruct:free" é um modelo de instrução
        # DIRETA (sem raciocínio interno) — elimina de vez a causa raiz dos
        # bugs anteriores (content=None com finish_reason="length"), porque
        # não existe raciocínio escondido a consumir o orçamento de tokens.
        # É também o modelo ':free' mais antigo e estabelecido da OpenRouter
        # (desde dez/2024), com 13 provedores diferentes por trás do mesmo
        # slug — a própria OpenRouter já faz balanceamento/fallback entre
        # eles antes mesmo de chegar ao nosso código.
        #
        # Mantemos 2 modelos de reserva para o caso (raro) de a família
        # Llama 3.3 estar completamente indisponível:
        # - a variante 8B, mais leve, da mesma família;
        # - "openrouter/free" como router genérico de último recurso.
        self.modelos = [
            "meta-llama/llama-3.3-70b-instruct:free",
            "meta-llama/llama-3.3-8b-instruct:free",
            "openrouter/free",
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
        mensagens_api = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        # Disparamos os modelos em PARALELO (não sequencialmente) e ficamos
        # com o primeiro que devolver uma resposta válida, cancelando os
        # restantes. Como são todos modelos ':free' (custo zero), isto não
        # tem custo extra — e evita que a latência total seja a SOMA de
        # vários timeouts/falhas em cadeia (era isso que estava a tornar o
        # bot lento: openrouter/free a falhar, depois 15s à espera do
        # nemotron, depois o gemma). Agora a latência sentida é a do modelo
        # mais rápido a responder bem, não a soma de todos os que falharam.
        tasks = {
            asyncio.create_task(self._tentar_modelo(modelo, mensagens_api)): modelo
            for modelo in self.modelos
        }

        resposta_final = None
        try:
            for tarefa in asyncio.as_completed(list(tasks.keys())):
                resultado = await tarefa
                if resultado:
                    resposta_final = resultado
                    break
        finally:
            for tarefa in tasks:
                if not tarefa.done():
                    tarefa.cancel()

        return resposta_final

    async def _tentar_modelo(self, modelo: str, mensagens_api: list) -> str:
        """Faz uma chamada a um único modelo e devolve a resposta se for
        válida, ou None em caso de falha/resposta inválida. Nunca lança
        exceção — é seguro correr várias instâncias em paralelo."""
        try:
            response = await self.api_client.chat.completions.create(
                model=modelo,
                messages=mensagens_api,
                # 900 dá margem confortável mesmo que a lista alguma vez
                # inclua um modelo de raciocínio (ex.: o "openrouter/free"
                # de último recurso pode calhar nisso). Para os modelos
                # principais (instrução direta, sem raciocínio) isto é só
                # uma rede de segurança — normalmente terminam bem antes.
                max_tokens=900,
                temperature=0.85,
                timeout=API_TIMEOUT_SEGUNDOS,
                # No-op inofensivo em modelos sem raciocínio (como os dois
                # principais da lista agora); só entra em ação se a chamada
                # cair no fallback "openrouter/free" e este escolher um
                # modelo de raciocínio.
                extra_body={"reasoning": {"effort": "low", "exclude": True}},
            )

            # Alguns modelos ':free' da OpenRouter, quando o provedor
            # upstream falha a meio do pedido, devolvem um objeto de
            # resposta "válido" (sem lançar HTTPException) mas com
            # 'choices' a None/vazio. Sem esta verificação, o acesso a
            # response.choices[0] rebenta com
            # "'NoneType' object is not subscriptable".
            choices = getattr(response, "choices", None)
            if not choices:
                erro_upstream = getattr(response, "error", None)
                print(f"[FRASES] Modelo {modelo} devolveu resposta sem 'choices'. "
                      f"Erro upstream reportado: {erro_upstream!r}")
                return None

            finish_reason = choices[0].finish_reason

            if VERBOSE_LOGS:
                print(f"[FRASES] Modelo: {modelo} | finish_reason: {finish_reason}")

            resposta_gerada = choices[0].message.content
            if VERBOSE_LOGS:
                print(f"[FRASES] Conteudo bruto ({modelo}): {resposta_gerada!r}")

            if resposta_gerada:
                resposta_gerada = resposta_gerada.strip()

            if _resposta_valida(resposta_gerada, finish_reason):
                if VERBOSE_LOGS:
                    print(f"[FRASES] OK ({modelo}): {resposta_gerada}")
                return resposta_gerada

            print(f"[FRASES] Modelo {modelo} devolveu resposta invalida.")
            return None
        except asyncio.CancelledError:
            # Esperado quando outro modelo já respondeu primeiro — não é um erro.
            raise
        except Exception as e:
            print(f"[FRASES] Erro no modelo {modelo}: {e}")
            return None

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        if self.bot.user in message.mentions:
            agora = time.time()
            ultima = _ultima_mencao.get(message.author.id)
            if ultima and (agora - ultima) < COOLDOWN_SEGUNDOS:
                restante = COOLDOWN_SEGUNDOS - (agora - ultima)
                try:
                    aviso = await message.channel.send(
                        f"⏳ Calma aí, {message.author.mention}! Espera {restante:.0f}s antes de me chamares outra vez.",
                        delete_after=6,
                        allowed_mentions=discord.AllowedMentions(users=False)
                    )
                except Exception:
                    pass
                return
            _ultima_mencao[message.author.id] = agora
            if len(_ultima_mencao) > 500:
                expirar = [uid for uid, ts in _ultima_mencao.items() if agora - ts > COOLDOWN_SEGUNDOS * 10]
                for uid in expirar:
                    _ultima_mencao.pop(uid, None)

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
                resposta = _frase_fallback()

            base_resposta = f"🎮 {resposta}"
            try:
                msg_resposta = await message.channel.send(base_resposta, view=TranslateView())
                registar_mensagem(msg_resposta.id, base_resposta, resposta)
            except Exception as e:
                print(f"[FRASES] Erro ao enviar resposta IA: {e}")

    @commands.command(name="frase")
    async def frase(self, ctx):
        """Responde com uma frase temática gerada pela IA, ou uma frase fixa
        (com variedade) se a IA não estiver disponível."""
        async with ctx.typing():
            resposta = await self._gerar_resposta_ia("Diz algo aleatório e divertido sobre o jogo.")
        if not resposta:
            resposta = _frase_fallback()
        msg = await ctx.send(f"🎮 {resposta}", view=TranslateView())
        registar_mensagem(msg.id, f"🎮 {resposta}", resposta)

    @commands.command(name="iatest")
    async def iatest(self, ctx, *, texto: str):
        resposta = await self._gerar_resposta_ia(texto)
        if resposta:
            await ctx.send(f"🧠 IA: {resposta}")
        else:
            await ctx.send(f"❌ IA falhou. Fallback: {_frase_fallback()}")


async def setup(bot: commands.Bot):
    await bot.add_cog(Frases(bot))
