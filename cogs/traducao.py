class Traducao(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.delete_lock = asyncio.Lock()

    async def apagar_com_retry(self, message, tentativas=3):
        async with self.delete_lock:
            for i in range(tentativas):
                try:
                    await message.delete()
                    return True
                except discord.HTTPException as e:
                    if e.status == 429 and i < tentativas - 1:
                        retry_after = getattr(e, 'retry_after', 1.0)
                        await asyncio.sleep(retry_after + 0.5)
                        continue
                    else:
                        print(f"[TRADUÇÃO] Falha ao apagar {message.id}: {e}")
                        return False
                except discord.Forbidden:
                    print(f"[TRADUÇÃO] Sem permissão para apagar {message.id}")
                    return False
        return False

    @commands.Cog.listener()
    async def on_message(self, message):
        # ... verificações ...
        conteudo = f"<@{message.author.id}>: {message.content}"
        # 1. Envia republicação
        try:
            msg_enviada = await message.channel.send(conteudo, view=TranslateView(), allowed_mentions=...)
        except Exception as e:
            print(f"[TRADUÇÃO] Erro ao enviar: {e}")
            return
        # 2. Tenta apagar original
        sucesso = await self.apagar_com_retry(message)
        if not sucesso:
            # rollback: apaga a republicação para não duplicar
            try:
                await msg_enviada.delete()
            except Exception as e:
                print(f"[TRADUÇÃO] Erro ao apagar republicação: {e}")
            return
        registar_mensagem(msg_enviada.id, conteudo, message.content)
