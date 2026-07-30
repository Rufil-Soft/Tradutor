import asyncio
import discord
from discord.ext import commands
from deep_translator import GoogleTranslator

translation_cache = {}

class TranslateView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Traduzir", style=discord.ButtonStyle.secondary, emoji="🌐", custom_id="persistent_translate_button")
    async def translate_button_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)

        message_text = interaction.message.content
        if not message_text:
            await interaction.followup.send("Não há texto para traduzir.", ephemeral=True)
            return

        # Define o idioma com base nas definições do Discord do utilizador
        user_locale = (str(interaction.locale).split("-")[0] or "pt")[:2]
        texto_para_traduzir = message_text

        cache_key = (texto_para_traduzir, user_locale)
        if cache_key in translation_cache:
            translated = translation_cache[cache_key]
        else:
            try:
                translated = await asyncio.to_thread(
                    GoogleTranslator(source='auto', target=user_locale).translate,
                    texto_para_traduzir
                )
                if translated:
                    translation_cache[cache_key] = translated
            except Exception as e:
                print(f"[TRADUTOR] Erro na tradução: {e}")
                await interaction.followup.send("Erro ao traduzir. Tenta novamente.", ephemeral=True)
                return

        if not translated:
            await interaction.followup.send("Não foi possível traduzir o texto.", ephemeral=True)
            return

        await interaction.followup.send(
            f"🌐 **Tradução ({user_locale.upper()}):**\n{translated}",
            ephemeral=True
        )


class Traducao(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        print("[TRADUÇÃO] Cog carregado. Botão de tradução ativo.")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.content:
            return
        if message.content.startswith(self.bot.command_prefix):
            return
        if message.channel.name == "🎯-capos-message":
            return

        try:
            # Em vez de apagar a mensagem, edita-a adicionando a view com o botão!
            # Nota: No Discord, se o bot não for o autor da mensagem, não a pode editar diretamente.
            # Por isso, a forma limpa de manter o autor original e por o botão é via webhook ou criando uma nova formatada.
            
            # Se preferires manter exatamente quem enviou sem webhooks, a forma mais fiável 
            # é enviar a mensagem com o nome do autor no texto e o botão em baixo:
            conteudo_formatado = f"**{message.author.display_name}**: {message.content}"
            
            # Guarda os anexos se houver (imagens, etc.)
            files = [await a.to_file() for a in message.attachments]

            await message.delete() # Remove a original sem formatação de botões
            await message.channel.send(
                content=conteudo_formatado,
                files=files,
                view=TranslateView()
            )
        except discord.Forbidden:
            pass
        except Exception as e:
            print(f"[TRADUÇÃO] Erro ao adicionar botão à mensagem: {e}")


async def setup(bot: commands.Bot):
    await bot.add_cog(Traducao(bot))
