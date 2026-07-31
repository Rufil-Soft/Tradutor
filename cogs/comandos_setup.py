import discord
from discord.ext import commands
from config import FAMILIAS, LIMITE_SOLDIERS
from cogs.logs import enviar_log_mafia  # (não usado neste ficheiro, mas inofensivo)
from bot import bot

class ComandosSetup(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="sync")
    @commands.has_permissions(administrator=True)
    async def sync_commands(self, ctx):
        """Sincroniza os comandos de barra instantaneamente no servidor atual."""
        try:
            bot.tree.copy_global_to(guild=ctx.guild)
            synced = await bot.tree.sync(guild=ctx.guild)
            await ctx.send(f"✅ Sincronizados **{len(synced)}** comandos de barra neste servidor!")
        except Exception as e:
            await ctx.send(f"❌ Erro ao sincronizar: {e}")

    @commands.command(name="setup_logs")
    @commands.has_permissions(administrator=True)
    async def setup_logs(self, ctx):
        """Cria o canal de logs da máfia."""
        guild = ctx.guild
        nome_canal = "🕶️-mafia-logs"
        canal_existente = discord.utils.get(guild.text_channels, name=nome_canal)
        if canal_existente:
            await ctx.send(f"⚠️ O canal de logs já existe: {canal_existente.mention}")
            return
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }
        for role in guild.roles:
            if role.permissions.administrator:
                overwrites[role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
        canal = await guild.create_text_channel(
            name=nome_canal,
            overwrites=overwrites,
            topic="Registo oficial de movimentações e lealdade das Famílias."
        )
        await ctx.send(f"✅ Canal de logs criado: {canal.mention}")

    @commands.command(name="setup_capos_message")
    @commands.has_permissions(administrator=True)
    async def setup_capos_message(self, ctx):
        """Cria o canal central de comunicados (🎯-capos-message)."""
        guild = ctx.guild
        nome_canal = "🎯-capos-message"
        canal_existente = discord.utils.get(guild.text_channels, name=nome_canal)
        if canal_existente:
            await ctx.send(f"⚠️ O canal central já existe: {canal_existente.mention}")
            return
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }
        cargo_capo = discord.utils.get(guild.roles, name="Capo")
        if cargo_capo:
            overwrites[cargo_capo] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
        for role in guild.roles:
            if role.permissions.administrator:
                overwrites[role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
        canal = await guild.create_text_channel(
            name=nome_canal,
            overwrites=overwrites,
            topic="Propagação de comunicados para 🚨-warnings das famílias."
        )
        await ctx.send(f"✅ Canal criado: {canal.mention}")

    @commands.command(name="setup_vota_message")
    @commands.has_permissions(administrator=True)
    async def setup_vota_message(self, ctx):
        """Cria o canal central de votações (🗳️ vote-command)."""
        guild = ctx.guild
        nome_canal = "🗳️ vote-command"
        canal_existente = discord.utils.get(guild.text_channels, name=nome_canal)
        if canal_existente:
            await ctx.send(f"⚠️ O canal central de votações já existe: {canal_existente.mention}")
            return
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }
        for role in guild.roles:
            if role.permissions.administrator or role.name == "Capo":
                overwrites[role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
        canal = await guild.create_text_channel(
            name=nome_canal,
            overwrites=overwrites,
            topic="Usa /votacao para criar votações globais."
        )
        await ctx.send(f"✅ Canal criado: {canal.mention}")

    @commands.command(name="status_familias")
    @commands.has_permissions(administrator=True)
    async def status_familias(self, ctx):
        """Relatório de poder das famílias (Capo e soldados)."""
        guild = ctx.guild
        cargo_capo = discord.utils.get(guild.roles, name="Capo")
        cargo_soldier = discord.utils.get(guild.roles, name="Soldier")
        embed = discord.Embed(title="📊 RELATÓRIO DE PODER DAS FAMÍLIAS", color=discord.Color.dark_red())
        for key, nome_familia in FAMILIAS.items():
            cargo_fam = discord.utils.get(guild.roles, name=nome_familia)
            if not cargo_fam:
                continue
            capos = [m.mention for m in cargo_fam.members if cargo_capo and cargo_capo in m.roles]
            capo_str = capos[0] if capos else "*Sem Capo*"
            qtd_soldados = sum(1 for m in cargo_fam.members if cargo_soldier and cargo_soldier in m.roles)
            embed.add_field(
                name=f"🍷 {nome_familia}",
                value=f"**Capo:** {capo_str}\n**Soldados:** `{qtd_soldados}/{LIMITE_SOLDIERS}`",
                inline=False
            )
        await ctx.send(embed=embed)

    # Listener on_message para propagação de comunicados
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return
        # Só propaga mensagens do canal 🎯-capos-message
        if message.channel.name == "🎯-capos-message":
            for familia_key, nome_familia in FAMILIAS.items():
                nome_cat = f"🍷 {nome_familia.upper()}"
                categoria = discord.utils.get(message.guild.categories, name=nome_cat)
                if categoria:
                    canal_warnings = discord.utils.get(categoria.text_channels, name="🚨-warnings")
                    if canal_warnings:
                        try:
                            # --- Processa o texto (trunca se necessário) ---
                            descricao = message.content
                            if len(descricao) > 4090:
                                descricao = descricao[:4090] + "\n... (mensagem truncada)"

                            embed = discord.Embed(
                                title="🚨 COMUNICADO OFICIAL DA CÚPULA",
                                description=descricao,
                                color=discord.Color.dark_red()
                            )
                            embed.set_author(
                                name=message.author.display_name,
                                icon_url=message.author.display_avatar.url if message.author.display_avatar else None
                            )

                            # --- Processa anexos ---
                            if message.attachments:
                                links = "\n".join(f"[{a.filename}]({a.url})" for a in message.attachments)
                                embed.add_field(name="📎 Anexos", value=links, inline=False)
                                # Se o primeiro anexo for uma imagem, usa como imagem do embed
                                primeiro = message.attachments[0]
                                if primeiro.content_type and primeiro.content_type.startswith("image/"):
                                    embed.set_image(url=primeiro.url)

                            await canal_warnings.send(embed=embed)
                        except Exception as e:
                            print(f"Erro ao propagar aviso para {nome_familia}: {e}")
            try:
                await message.add_reaction("✅")
            except discord.Forbidden:
                pass
            return


async def setup(bot: commands.Bot):
    await bot.add_cog(ComandosSetup(bot))
