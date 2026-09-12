import os
import random
import asyncio
import re
import discord
from discord.ext import commands
from cogs.traducao import TranslateView, registar_mensagem
from openai import AsyncOpenAI  # SDK compatível com OpenRouter

VERBOSE_LOGS = True  # Coloca True para ver logs detalhados da IA

FRASES_PT = [
    # Asas e voo
    "Se não tens asas, sequer estás a jogar Aion?",
    "Já voei demasiado perto do sol. O servidor expulsou-me.",
    "Asas cortadas? Acho que vais a pé para casa, herói.",
    "Voar no Aion 2 é tipo lag com passos extra.",
    "As minhas asas são cosméticas. A minha raiva não.",

    # Elyos vs Asmodians
    "Elyos de dia, Asmodian de noite. Dormir é para os fracos.",
    "A relva é sempre mais verde do lado Asmodian. Literalmente. É vermelha.",
    "Não escolho lados. Escolho quem tem os cosméticos mais bonitos.",
    "Os Asmodians têm problemas de raiva. Os Elyos têm problemas de confiança. Eu tenho os dois.",

    # Grind e progressão
    "Ding! Nível 50. Agora começa o grind a sério.",
    "Fiz grind 8 horas para conseguir uma manastone. Falhou. Chorei.",
    "O tutorial demorou 4 horas. O endgame levou-me a alma.",
    "Aion 2: onde 'só mais uma quest' é uma mentira que contas a ti mesmo às 3 da manhã.",
    "Não tenho vida. Tenho uma rotação.",

    # RNG e enchant
    "Enchant falhou. Outra vez. O meu monitor está bem, juro.",
    "O RNG do Aion não te odeia. Só gosta de te ver sofrer.",
    "Consegui um drop lendário! Era para outra classe. Claro.",
    "O RNGesus abandonou-nos. Estamos sozinhos agora.",

    # PvP e ganks
    "Fui gankado enquanto lia o tutorial. 10/10 recomendo.",
    "PvP no Abismo? Mais tipo PvP no ponto de respawn.",
    "Não faço gank a lowbies. Só... cumprimento-os agressivamente.",
    "PvP em mundo aberto: onde a amizade vai morrer.",
    "Nada diz 'bom dia' como um Sorcerer atrás de ti no Abismo.",

    # Comunidade e legions
    "Junta-te à minha legion. Temos bolachas e dívidas paralisantes.",
    "A estratégia da minha legion é 'todos em pânico' e de alguma forma funciona.",
    "O chat da legion é 90% memes e 10% 'onde é que eu vou?'",
    "Não sou líder de guild. Sou babysitter com passos extra.",

    # Bugs, lag e servidores
    "Dia de lançamento do Aion 2: 2000 jogadores, 1 servidor, 0 hipóteses.",
    "O lag é tão mau que o meu personagem voltou ao passado.",
    "Não é um bug, é uma 'mecânica surpresa'.",
    "Desconectado? Bem-vindo ao Aion 2. Tem uma boa fila de espera.",

    # F2P / P2W
    "Sou F2P. Isso significa 'Para Sempre Atrás'.",
    "As baleias no Aion 2 não nadam. Voam à tua frente.",
    "P2W? Não não, aqui chamamos 'conveniência'.",

    # No-life / tempo
    "O tempo voa quando fazes grind. As minhas asas também. E a minha sanidade.",
    "Disse a mim mesmo que parava no nível 30. Estou no 52. Mandem ajuda.",
    "Dormir é um debuff que continuo a ignorar.",
    "A vida real é só um timer AFK até ao próximo patch.",

    # Classes (humor genérico)
    "Os Clerics não curam. Julgam.",
    "Sorcerers: a apagar-te do mapa desde 2008.",
    "Os Gladiators só querem bater em coisas. Respeito.",
    "Os Assassins são a classe 'não confies em ninguém'. Coincidência: também é a comunidade.",

    # Diversos / memes
    "Aion 2: não é pay to win, é pay to não perder.",
    "Vim pelas asas. Fiquei porque não consigo fazer logout.",
    "A única coisa que voa mais rápido do que eu é o meu ouro.",
    "Jogar Aion 2 é como uma relação abusiva. Adoro.",
    "Se a vida te dá limões, troca-os por um passe premium.",
    "Não preciso de terapia. Preciso de um inventário maior.",
    "O nome do meu personagem é 'PleaseNerfMe'. Ainda não funcionou.",
    "Patch notes do Aion 2: 'arranjámos coisas'. Que coisas? Sim.",
    "Todos os MMOs têm uma regra: não confies no jogador com a mount mais xpto.",
    "PvE está bem. O PvP é onde as amizades são testadas e destruídas.",
    "Disseram-me 'joga só pela diversão'. Respondi 'vou jogar ranked num jogo PvE'.",
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

frase_manager = FraseManager(FRASES_PT)

def _resposta_valida(texto: str, finish_reason: str) -> bool:
    if not texto:
        return False
    texto = texto.strip()
    if not texto:
        return False
    if texto in FRASES_PT:
        return False
    if len(texto) < MIN_CARACTERES_RESPOSTA:
        return False
    if finish_reason == "length" and len(texto) < MIN_CARACTERES_RESPOSTA_CORTADA:
        return False
    return True

# Palavras e expressões típicas de PT-BR que devemos evitar.
# Rede de segurança: se o modelo escapar ao prompt, isto corrige.
_SUBSTITUICOES_BR_PT = {
    "você": "tu",
    "vocês": "vós",
    "a gente": "nós",
    "E aí": "Então",
    "e aí": "então",
    "Se liga": "Ouve lá",
    "se liga": "ouve lá",
    "legal": "fixe",
    "bacana": "fixe",
    "cara": "pá",
    "cara,": "pá,",
    "trem": "coisa",
    "ônibus": "autocarro",
    "celular": "telemóvel",
    "grama": "relva",
    "time": "equipa",
    "torcida": "claque",
    "estou fazendo": "estou a fazer",
    "estás fazendo": "estás a fazer",
    "está fazendo": "está a fazer",
    "estamos fazendo": "estamos a fazer",
    "estou comendo": "estou a comer",
    "está comendo": "está a comer",
    "estou falando": "estou a falar",
    "está falando": "está a falar",
    "estou pensando": "estou a pensar",
    "está pensando": "está a pensar",
}

def _normalizar_pt_pt(texto: str) -> str:
    """Aplica substituições simples de PT-BR → PT-PT no texto gerado pela IA."""
    if not texto:
        return texto
    for br, pt in _SUBSTITUICOES_BR_PT.items():
        texto = re.sub(rf"\b{re.escape(br)}\b", pt, texto, flags=re.IGNORECASE)
    return texto


class Frases(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.api_client = None
        # Modelos gratuitos do OpenRouter, por ordem de preferência.
        # Se um falhar, tenta o seguinte.
      self.modelos = [
        "openrouter/free",  # Router automático — escolhe um modelo gratuito disponível
        "arcee-ai/trinity-large-preview:free",  # Roleplay / storytelling
        "cognitivecomputations/dolphin-mistral-24b-venice-edition:free",  # Venice Uncensored
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
            print("[FRASES] Cliente OpenRouter inicializado (modelos gratuitos).")
        else:
            print("[FRASES] ⚠️ OPENROUTER_API_KEY não definida. A usar apenas frases fixas.")

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
        if not self.api_client:
            return None

        texto_limpo = re.sub(r"<@!?[0-9]+>", "", mensagem_usuario).strip()
        if not texto_limpo:
            texto_limpo = mensagem_usuario

        exemplos = frase_manager.amostra(AMOSTRA_ESTILO)
        exemplos_texto = "\n".join(f"- {frase}" for frase in exemplos)

        system_prompt = (
            "És o Aquiles, um jogador veterano e carismático de Aion 2. "
            "Falas como um gamer português experiente, com humor leve, sarcasmo amigável "
            "e um à-vontade natural. Respondes como se estivesses a conversar no chat do jogo "
            "com um amigo — nada de respostas formais ou robóticas.\n\n"

            "⚠️ REGRA ABSOLUTA DE IDIOMA ⚠️\n"
            "Escreves SEMPRE em PORTUGUÊS EUROPEU (PT-PT). NUNCA uses português do Brasil.\n"
            "Exemplos do que deves evitar:\n"
            "- ❌ 'você está fazendo' → ✅ 'tu estás a fazer'\n"
            "- ❌ 'E aí, galera' → ✅ 'Então, pessoal'\n"
            "- ❌ 'Se liga' → ✅ 'Ouve lá'\n"
            "- ❌ 'legal', 'bacana' → ✅ 'fixe', 'porreiro'\n"
            "- ❌ 'cara' → ✅ 'pá'\n"
            "- ❌ 'a gente vai' → ✅ 'nós vamos'\n"
            "- ❌ 'celular', 'ônibus', 'grama', 'time' → ✅ 'telemóvel', 'autocarro', 'relva', 'equipa'\n\n"

            "Usa SEMPRE o gerúndio perifrástico: 'estou a fazer', 'estás a jogar', 'estamos a grindar'.\n\n"

            f"Exemplos do teu estilo (repara no PT-PT natural):\n{exemplos_texto}\n\n"

            "Instruções:\n"
            "- Responde diretamente ao que o utilizador disse, com humor e um toque de gaming.\n"
            "- Mantém a resposta curta (2 a 3 frases no máximo).\n"
            "- Fala como uma pessoa real, não como um assistente.\n"
            "- Mantém tudo leve, amigável e inclusivo. Sem insultos, sem toxicidade, sem humor negro.\n"
            "- Referencia o Aion 2 (asas, Elyos, Asmodians, o Abismo, grind, legions, manastones, "
            "PvP, etc.) sempre que encaixe na piada.\n"
            "- Nunca saias da personagem, nunca menciones que és uma IA."
        )

        user_prompt = (
            f"O utilizador disse: \"{texto_limpo}\"\n\n"
            "Responde como o Aquiles, o veterano divertido de Aion 2, "
            "OBRIGATORIAMENTE em português europeu (PT-PT)."
        )

        for modelo in self.modelos:
            try:
                response = await self.api_client.chat.completions.create(
                    model=modelo,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    max_tokens=500,
                    temperature=0.9,
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
                    resposta_gerada = _normalizar_pt_pt(resposta_gerada)

                if _resposta_valida(resposta_gerada, finish_reason):
                    if VERBOSE_LOGS:
                        print(f"[FRASES] Resposta da IA: {resposta_gerada}")
                    return resposta_gerada

                print(f"[FRASES] Modelo {modelo} devolveu resposta vazia/curta/truncada "
                      f"(finish_reason={finish_reason!r}). Tentando próximo...")
            except Exception as e:
                print(f"[FRASES] Erro no OpenRouter com modelo {modelo}: {e}")

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

            base_resposta = f"🎮 {resposta}"
            try:
                msg_resposta = await message.channel.send(base_resposta, view=TranslateView())
                registar_mensagem(msg_resposta.id, base_resposta, resposta)
            except Exception as e:
                print(f"[FRASES] Erro ao enviar resposta IA: {e}")

    @commands.command(name="frase")
    async def frase(self, ctx):
        frase_original = frase_manager.next()
        base = f"🎮 {frase_original}"
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
