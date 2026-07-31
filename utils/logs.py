import discord

async def enviar_log_mafia(guild: discord.Guild, titulo: str, descricao: str, cor: discord.Color):
    try:
        canal_log = discord.utils.get(guild.text_channels, name="🕶️-mafia-logs")
        if canal_log:
            embed = discord.Embed(title=titulo, description=descricao, color=cor, timestamp=discord.utils.utcnow())
            embed.set_footer(text="Máfia System • Registro de Lealdade")
            await canal_log.send(embed=embed)
    except Exception as e:
        print(f"Erro ao enviar log da máfia: {e}")
