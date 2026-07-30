import asyncio
import traceback
import discord
from discord.ext import commands
from discord import app_commands
from deep_translator import GoogleTranslator
from datetime import datetime
from typing import Dict
from config import BLOCK_TIMEOUT
from bot import bot

# Estruturas do sistema de blocos
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
            async for msg in channel.history(
                limit=50,
                before=discord.Object(id=self.last_msg_id),
                after=discord.Object(id=self.first_msg_id)
            ):
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

            # Usa cache se existir
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

            # Formata a resposta
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
            traceback.print_exc()
            await interaction.followup.send("Ocorreu um erro ao traduzir o bloco.", ephemeral=True)


async def finalizar_bloco(channel: discord.TextChannel, bloco: dict):
    if channel.id in current_button_message:
        try:
            await current_button_message[channel.id].delete()
        except Exception:
            pass
    if not bloco["messages"]:
        return
    first_msg = bloco["messages"][0]
    last_msg = bloco["messages"][-1]
    view = TranslateBlockView(bloco["author_id"], first_msg.id, last_msg.id)
    try:
        button_msg = await channel.send(
            f"📚 {len(bloco['messages'])} mensagens de {first_msg.author.display_name}. Clique para traduzir:",
            view=view
        )
        current_button_message[channel.id] = button_msg
    except Exception as e:
        print(f"[TRADUÇÃO] Erro ao enviar botão de bloco: {e}")


class Traducao(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        print("[TRADUÇÃO] Cog carregado.")
        self.bg_task = self.bot.loop.create_task(self._close_stale_blocks())

    async def _close_stale_blocks(self):
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

    # Sistema automático de blocos
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.content:
            return
        # Não interferir no canal de comunicados
        if message.channel.name == "🎯-capos-message":
            return

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

    # Menu de contexto "Traduzir Mensagem"
    @app_commands.context_menu(name="Traduzir Mensagem")
    async def traduzir_context(self, interaction: discord.Interaction, message: discord.Message):
        await interaction.response.defer(ephemeral=True)
        if not message.content:
            await interaction.followup.send("Esta mensagem não tem texto para traduzir.", ephemeral=True)
            return
        user_locale = (str(interaction.locale).split("-")[0] or "pt")[:2]
        print(f"[TRADUTOR] Traduzindo para '{user_locale}' (msg de {message.author})")
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


async def setup(bot: commands.Bot):
    await bot.add_cog(Traducao(bot))
