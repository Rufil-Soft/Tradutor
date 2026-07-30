import asyncio
import discord
from discord.ext import commands
from discord import app_commands
from deep_translator import GoogleTranslator
from datetime import datetime
from typing import Dict
from config import BLOCK_TIMEOUT
from bot import bot

pending_blocks: Dict[int, dict] = {}
current_button_message: Dict[int, discord.Message] = {}
translation_cache: Dict[tuple, str] = {}

class TranslateBlockView(discord.ui.View):
    def __init__(self, author_id: int, first_msg_id: int, last_msg_id: int):
        super().__init__(timeout=600)
        self.author_id = author_id
        self.first_msg_id = first_msg_id
        self.last_msg_id = last_msg_id

    @discord.ui.button(label="Traduzir Bloco", style=discord.ButtonStyle.secondary, emoji="🌐")
    async def translate_block(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        channel = interaction.channel
        try:
            messages = []
            async for msg in channel.history(limit=50, before=discord.Object(id=self.last_msg_id),
                                             after=discord.Object(id=self.first_msg_id)):
                if msg.author.id == self.author_id and msg.content:
                    messages.append(msg)
            last_msg = await channel.fetch_message(self.last_msg_id)
            if last_msg.author.id == self.author_id and last_msg.content:
                messages.append(last_msg)
            messages.sort(key=lambda m: m.created_at)
            if not messages:
                await interaction.followup.send("Não foi possível recuperar o bloco.", ephemeral=True)
                return

            combined_text = "\n".join(m.content for m in messages)
            user_locale = (str(interaction.locale).split("-")[0] or "pt")[:2]
            cache_key = (combined_text, user_locale)
            if cache_key in translation_cache:
                translated = translation_cache[cache_key]
            else:
                translated = await asyncio.to_thread(
                    GoogleTranslator(source='auto', target=user_locale).translate,
                    combined_text
                )
                if translated:
                    translation_cache[cache_key] = translated

            if not translated:
                await interaction.followup.send("Não foi possível obter tradução.", ephemeral=True)
                return

            original_lines = combined_text.split("\n")
            translated_lines = translated.split("\n")
            if len(original_lines) == len(translated_lines):
                lines = [f"**{orig}**  →  *{trad}*" for orig, trad in zip(original_lines, translated_lines)]
                final = "\n".join(lines)
            else:
                final = f"🔠 **Tradução ({user_locale.upper()}):**\n{translated}"
            await interaction.followup.send(final, ephemeral=True)
        except Exception as e:
            print(f"[TRADUÇÃO] Erro ao processar bloco: {e}")
            await interaction.followup.send("Ocorreu um erro ao traduzir o bloco.", ephemeral=True)


async def finalizar_bloco(channel: discord.TextChannel, bloco: dict):
    if channel.id in current_button_message:
        try:
            await current_button_message[channel.id].delete()
        except:
            pass
    if not bloco["messages"]:
        return
    first_msg = bloco["messages"][0]
    last_msg = bloco["messages"][-1]
    view = TranslateBlockView(bloco["author_id"], first_msg.id, last_msg.id)
    button_msg = await channel.send(
        f"📚 {len(bloco['messages'])} mensagens de {first_msg.author.display_name}. Clique para traduzir:",
        view=view
    )
    current_button_message[channel.id] = button_msg


class Traducao(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.bg_task = self.bot.loop.create_task(self.close_stale_blocks())

    async def close_stale_blocks(self):
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            await asyncio.sleep(30)
            now = datetime.utcnow()
            for channel_id, bloco in list(pending_blocks.items()):
                if (now - bloco["last_time"]).total_seconds() > BLOCK_TIMEOUT:
                    channel = self.bot.get_channel(channel_id)
                    if channel:
                        await finalizar_bloco(channel, bloco)
                    pending_blocks.pop(channel_id, None)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.content:
            return
        # A propagação de comunicados é feita noutro cog (comandos_setup.py),
        # por isso aqui só tratamos da tradução.
        channel = message.channel
        now = datetime.utcnow()
        if channel.id in pending_blocks:
            bloco = pending_blocks[channel.id]
            if (message.author.id == bloco["author_id"] and
                (now - bloco["last_time"]).total_seconds() <= BLOCK_TIMEOUT):
                bloco["messages"].append(message)
                bloco["last_time"] = now
            else:
                await finalizar_bloco(channel, bloco)
                pending_blocks[channel.id] = {
                    "author_id": message.author.id,
                    "messages": [message],
                    "last_time": now
                }
        else:
            pending_blocks[channel.id] = {
                "author_id": message.author.id,
                "messages": [message],
                "last_time": now
            }

    @app_commands.context_menu(name="Traduzir Mensagem")
    async def traduzir_context(self, interaction: discord.Interaction, message: discord.Message):
        await interaction.response.defer(ephemeral=True)
        if not message.content:
            await interaction.followup.send("Esta mensagem não tem texto para traduzir.", ephemeral=True)
            return
        user_locale = (str(interaction.locale).split("-")[0] or "pt")[:2]
        try:
            translated = await asyncio.to_thread(
                GoogleTranslator(source='auto', target=user_locale).translate,
                message.content
            )
            if not translated:
                await interaction.followup.send("Não foi possível obter tradução.", ephemeral=True)
                return
            await interaction.followup.send(f"🔠 **Tradução ({user_locale.upper()}):**\n{translated}", ephemeral=True)
        except Exception as e:
            print(f"[TRADUTOR] Erro: {type(e).__name__}: {e}")
            await interaction.followup.send("Erro ao traduzir. Tenta novamente.", ephemeral=True)

    @app_commands.command(name="traduzir_utilizador", description="Traduz as últimas mensagens consecutivas de um utilizador")
    @app_commands.describe(membro="Utilizador alvo", limite="Nº máximo de mensagens a analisar (padrão: 10)")
    async def traduzir_utilizador(self, interaction: discord.Interaction, membro: discord.Member, limite: int = 10):
        await interaction.response.defer(ephemeral=True)
        if limite < 1 or limite > 50:
            await interaction.followup.send("O limite deve estar entre 1 e 50.", ephemeral=True)
            return
        messages = [msg async for msg in interaction.channel.history(limit=limite)]
        if not messages:
            await interaction.followup.send("Não encontrei mensagens recentes.", ephemeral=True)
            return
        user_msgs = [m for m in reversed(messages) if m.author == membro and m.content]
        if not user_msgs:
            await interaction.followup.send(f"{membro.mention} não tem mensagens de texto recentes.", ephemeral=True)
            return
        blocos = []
        bloco_atual = []
        for msg in user_msgs:
            if bloco_atual and msg.author != bloco_atual[-1].author:
                blocos.append(bloco_atual)
                bloco_atual = [msg]
            else:
                bloco_atual.append(msg)
        if bloco_atual:
            blocos.append(bloco_atual)

        user_locale = (str(interaction.locale).split("-")[0] or "pt")[:2]
        respostas = []
        for i, bloco in enumerate(blocos, 1):
            texto = "\n".join(m.content for m in bloco)
            try:
                translated = await asyncio.to_thread(
                    GoogleTranslator(source='auto', target=user_locale).translate,
                    texto
                )
                respostas.append(f"**Bloco {i}** ({len(bloco)} msg):\n{translated}")
            except Exception as e:
                print(f"[TRADUTOR] Erro no bloco {i}: {e}")
                respostas.append(f"**Bloco {i}**: (erro na tradução)")

        final = f"🔠 **Tradução ({user_locale.upper()}) para {membro.display_name}:**\n\n" + "\n\n".join(respostas)
        if len(final) > 2000:
            partes = [final[i:i+2000] for i in range(0, len(final), 2000)]
            for parte in partes:
                await interaction.followup.send(parte, ephemeral=True)
        else:
            await interaction.followup.send(final, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Traducao(bot))
