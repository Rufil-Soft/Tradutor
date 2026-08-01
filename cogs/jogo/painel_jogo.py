import discord
from discord.ext import commands
from datetime import datetime, timedelta
from config import FAMILIAS
from utils.logs import enviar_log_mafia
from cogs.jogo.economia import (
    economia, salvar_dados, inicializar_familia,
    adicionar_dinheiro, adicionar_balas, adicionar_licor,
    adicionar_edificio, obter_familia_jogador
)

# Tempo de espera entre roubos (5 minutos)
COOLDOWN_ROUBO = timedelta(minutes=5)

class PainelJogoView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    # ---------- BOTÕES DE CONSTRUÇÃO ----------
    @discord.ui.button(label="Apartamento (1000$)", style=discord.ButtonStyle.primary, emoji="🏢", custom_id="construir_apartamento", row=1)
    async def construir_apartamento(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._construir(interaction, "apartamentos", 1000, "Apartamento")

    @discord.ui.button(label="Casino (2500$)", style=discord.ButtonStyle.primary, emoji="🎰", custom_id="construir_casino", row=1)
    async def construir_casino(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._construir(interaction, "casinos", 2500, "Casino")

    @discord.ui.button(label="Loja de Licor (1500$)", style=discord.ButtonStyle.primary, emoji="🍾", custom_id="construir_loja_licor", row=1)
    async def construir_loja_licor(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._construir(interaction, "lojas_licor", 1500, "Loja de Licor")

    @discord.ui.button(label="Fábrica de Balas (3000$)", style=discord.ButtonStyle.primary, emoji="🔫", custom_id="construir_fabrica_balas", row=1)
    async def construir_fabrica_balas(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._construir(interaction, "fabrica_balas", 3000, "Fábrica de Balas")

    async def _construir(self, interaction: discord.Interaction, tipo: str, custo: int, nome: str):
        """Lógica comum para construir um edifício."""
        familia = obter_familia_jogador(interaction.user)
        if not familia:
            await interaction.response.send_message("❌ Não pertences a nenhuma família.", ephemeral=True)
            return

        inicializar_familia(familia)
        dados = economia["familias"][familia]

        if dados["dinheiro"] < custo:
            await interaction.response.send_message(f"❌ A tua família precisa de {custo}$ (tem {dados['dinheiro']}$).", ephemeral=True)
            return

        # Cobra o dinheiro e adiciona o edifício
        adicionar_dinheiro(familia, -custo)
        adicionar_edificio(familia, tipo, 1)
        await salvar_dados(interaction.client)

        await interaction.response.send_message(f"✅ {nome} construído! A {familia} agora tem {dados[tipo]} {nome}(s).", ephemeral=True)
        await enviar_log_mafia(
            interaction.guild,
            f"🏗️ {nome} Construído",
            f"{interaction.user.mention} construiu um {nome} para a **{familia}**.\n"
            f"Custo: {custo}$ | Dinheiro restante: {dados['dinheiro']}$",
            discord.Color.blue()
        )

    # ---------- ROUBAR CARRO ----------
    @discord.ui.button(label="Roubar Carro", style=discord.ButtonStyle.danger, emoji="🚗", custom_id="roubar_carro", row=2)
    async def roubar_carro(self, interaction: discord.Interaction, button: discord.ui.Button):
        jogador_id = str(interaction.user.id)
        agora = datetime.utcnow()

        # Inicializar jogador se não existir
        if jogador_id not in economia["jogadores"]:
            economia["jogadores"][jogador_id] = {"carros": 0, "ultimo_roubo": None}

        jogador = economia["jogadores"][jogador_id]

        # Verificar cooldown
        if jogador["ultimo_roubo"]:
            ultimo = datetime.fromisoformat(jogador["ultimo_roubo"])
            if agora - ultimo < COOLDOWN_ROUBO:
                restante = COOLDOWN_ROUBO - (agora - ultimo)
                minutos = int(restante.total_seconds() // 60)
                segundos = int(restante.total_seconds() % 60)
                await interaction.response.send_message(
                    f"⏳ Tens de esperar {minutos}m {segundos}s para roubar outro carro.", ephemeral=True
                )
                return

        # Roubar carro com sucesso
        jogador["carros"] += 1
        jogador["ultimo_roubo"] = agora.isoformat()
        await salvar_dados(interaction.client)

        await interaction.response.send_message(
            f"🚗 Roubaste um carro! Agora tens {jogador['carros']} carro(s).", ephemeral=True
        )

    # ---------- VENDER CARRO ----------
    @discord.ui.button(label="Vender Carro (500$)", style=discord.ButtonStyle.success, emoji="💰", custom_id="vender_carro", row=2)
    async def vender_carro(self, interaction: discord.Interaction, button: discord.ui.Button):
        familia = obter_familia_jogador(interaction.user)
        if not familia:
            await interaction.response.send_message("❌ Não pertences a nenhuma família.", ephemeral=True)
            return

        jogador_id = str(interaction.user.id)
        jogador = economia["jogadores"].get(jogador_id, {"carros": 0})

        if jogador["carros"] < 1:
            await interaction.response.send_message("❌ Não tens carros para vender.", ephemeral=True)
            return

        jogador["carros"] -= 1
        adicionar_dinheiro(familia, 500)
        await salvar_dados(interaction.client)

        await interaction.response.send_message(
            f"💰 Vendeste um carro por 500$! A tua família recebeu o dinheiro.\n"
            f"Agora tens {jogador['carros']} carro(s).", ephemeral=True
        )

    # ---------- CONVERTER CARRO EM BALAS ----------
    @discord.ui.button(label="Converter Carro em Balas (5 🔫)", style=discord.ButtonStyle.secondary, emoji="⚙️", custom_id="converter_carro", row=2)
    async def converter_carro(self, interaction: discord.Interaction, button: discord.ui.Button):
        familia = obter_familia_jogador(interaction.user)
        if not familia:
            await interaction.response.send_message("❌ Não pertences a nenhuma família.", ephemeral=True)
            return

        inicializar_familia(familia)
        dados = economia["familias"][familia]

        if dados["fabrica_balas"] < 1:
            await interaction.response.send_message("❌ A tua família precisa de uma Fábrica de Balas para converter carros.", ephemeral=True)
            return

        jogador_id = str(interaction.user.id)
        jogador = economia["jogadores"].get(jogador_id, {"carros": 0})

        if jogador["carros"] < 1:
            await interaction.response.send_message("❌ Não tens carros para converter.", ephemeral=True)
            return

        jogador["carros"] -= 1
        adicionar_balas(familia, 5)
        await salvar_dados(interaction.client)

        await interaction.response.send_message(
            f"⚙️ Converteste um carro em 5 balas para a {familia}!\n"
            f"Agora tens {jogador['carros']} carro(s).", ephemeral=True
        )


class PainelJogo(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="setup_jogo")
    @commands.has_permissions(administrator=True)
    async def setup_jogo(self, ctx):
        """Envia o painel principal de jogo (construção, carros, etc.)."""
        await ctx.message.delete()
        embed = discord.Embed(
            title="🏙️ Centro de Operações da Máfia",
            description=(
                "Usa os botões abaixo para expandir o teu império!\n\n"
                "**Construção:**\n"
                "🏢 Apartamento – 1000$ (rende 100$/h)\n"
                "🎰 Casino – 2500$ (rende 200$/h)\n"
                "🍾 Loja de Licor – 1500$ (produz 5 licor/h)\n"
                "🔫 Fábrica de Balas – 3000$ (produz 2 balas/h)\n\n"
                "**Carros:**\n"
                "🚗 Roubar – espera 5 min entre roubos\n"
                "💰 Vender – 500$ por carro\n"
                "⚙️ Converter – 5 balas por carro (requer fábrica)"
            ),
            color=discord.Color.dark_gold()
        )
        embed.set_footer(text="Omertà • Sistema Económico")
        await ctx.send(embed=embed, view=PainelJogoView())


async def setup(bot: commands.Bot):
    bot.add_view(PainelJogoView())
    await bot.add_cog(PainelJogo(bot))
