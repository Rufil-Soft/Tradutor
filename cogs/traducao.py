import asyncio
import discord
from discord.ext import commands
from deep_translator import GoogleTranslator

translation_cache = {}

# Função auxiliar para converter a cor RGB da role num código ANSI do Discord
def rgb_to_ansi(color: discord.Color):
    if not color or color.value == 0:
        return "\u001b[0m" # Cor padrão
    
    r, g, b = color.r, color.g, color.b
    
    # Mapeamento simples para ANSI básico com base na luminosidade/valores
    if r > 180 and g < 100 and b < 100: return "\u001b[31m" # Vermelho
    if r < 100 and g > 180 and b < 100: return "\u001b[32m" # Verde
    if r > 180 and g > 180 and b < 100: return "\u001b[33m" # Amarelo
    if r < 100 and g < 100 and b > 180: return "\u001b[34m" # Azul
    if r > 180 and g < 100 and b > 180: return "\u001b[35m" # Magenta
    if r < 100 and g > 180 and b > 180: return "\u001b[36m" # Ciano
    if r > 200 and g > 200 and b > 200: return "\u001b[37m" # Branco brilhante
    
    # Fallback genérico para aproximar cores personalizadas usando códigos ANSI de 256 cores
    ansi_code = 16 + (36 * int(r / 255 * 5)) + (6 * int(g / 255 * 5)) + int(b / 255 * 5)
    return f"\u001b[38;5;{ansi_code}m"


class TranslateView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(style=discord.ButtonStyle.secondary, emoji="🌍", custom_id="persistent_translate_button")
    async def translate_button_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)

        message = interaction.message
        message_text = message.content

        if not message_text:
            await interaction.followup.send("Não há texto para traduzir.", ephemeral=True)
            return

        # Extrai apenas o conteúdo da mensagem (ignorando o bloco ANSI do nome)
        # O formato ANSI típico será ```ansi\n...```
        linhas = message_text.split("\n")
        texto_para_traduzir = message_text
        for linha in linhas:
            if ":" in linha and "\u001b" in linha:
                # Remove o prefixo do nome e fica só com o texto real
                partes = linha.split(":", 1)
                if len(partes) > 1:
                    texto_para_traduzir = partes[1].strip().replace("```", "").strip()

        user_locale = (str(interaction.locale).split("-")[0] or "pt")[:2]

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
            f"🌍 **Tradução ({user_locale.upper()}):**\n{translated}",
            ephemeral=True
        )


class Traducao(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        print("[TRADUÇÃO] Cog carregado com suporte a ANSI color ativo.")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.content:
            return
        if message.content.startswith(self.bot.command_prefix):
            return
        if message.channel.name == "🎯-capos-message":
            return

        try:
            # Obtém a cor do cargo do utilizador e gera o código ANSI correspondente
            ansi_color = rgb_to_ansi(message.author.color)
            
            # Formata a mensagem num bloco de código ANSI para aplicar a cor da role no nome
            conteudo_formatado = f"```ansi\n{ansi_color}{message.author.display_name}\u001b[0m: {message.content}\n```"

            files = [await a.to_file() for a in message.attachments]

            await message.delete()
            await message.channel.send(
                content=conteudo_formatado,
                files=files,
                view=TranslateView()
            )
        except discord.Forbidden:
            pass
        except Exception as e:
            print(f"[TRADUÇÃO] Erro ao processar mensagem ANSI: {e}")


async def setup(bot: commands.Bot):
    await bot.add_cog(Traducao(bot))
