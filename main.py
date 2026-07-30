# --- SISTEMA DE VOTAÇÕES INTERATIVAS (MODAL + SLASH COMMAND) ---
class DonPollModal(discord.ui.Modal, title="Criar Votação Oficial da Cúpula"):
    pergunta = discord.ui.TextInput(
        label="Pergunta da Votação",
        placeholder="Ex: A que horas atacamos amanhã?",
        style=discord.TextStyle.short,
        required=True
    )
    opcoes = discord.ui.TextInput(
        label="Opções (separadas por vírgula)",
        placeholder="Ex: 14h, 16h, 20h",
        style=discord.TextStyle.paragraph,
        required=True
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        pergunta_texto = self.pergunta.value
        raw_opcoes = [o.strip() for o in self.opcoes.value.split(",") if o.strip()]
        
        if len(raw_opcoes) < 2:
            await interaction.followup.send("❌ Tens de fornecer pelo menos 2 opções válidas separadas por vírgula.", ephemeral=True)
            return
        
        if len(raw_opcoes) > 10:
            await interaction.followup.send("❌ O Discord permite no máximo 10 opções por votação.", ephemeral=True)
            return

        guild = interaction.guild
        enviados = 0
        familias_sem_qg = []

        for familia_key, nome_familia in FAMILIAS.items():
            nome_cat = f"🍷 {nome_familia.upper()}"
            categoria = discord.utils.get(guild.categories, name=nome_cat)
            
            if categoria:
                canal_votacoes = discord.utils.get(categoria.text_channels, name="🗳️-votações")
                if canal_votacoes:
                    try:
                        # Cria uma nova instância de Poll para cada canal individualmente
                        poll = discord.Poll(question=pergunta_texto, duration=24)
                        for opt in raw_opcoes:
                            poll.add_answer(text=opt)

                        await canal_votacoes.send(
                            content=f"🗳️ **VOTAÇÃO DA CÚPULA** (Aberta por {interaction.user.mention})",
                            poll=poll
                        )
                        enviados += 1
                    except Exception as e:
                        print(f"Erro ao enviar votação para {nome_familia}: {e}")
                else:
                    familias_sem_qg.append(nome_familia)
            else:
                familias_sem_qg.append(nome_familia)
        
        resposta = f"✅ Votação interativa criada e propagada com sucesso para o canal de votações de **{enviados}** Famílias!"
        if familias_sem_qg:
            resposta += f"\n⚠️ *Aviso: As seguintes Famílias não têm QG/canal de votações ativo:* {', '.join(familias_sem_qg)}"

        await interaction.followup.send(resposta, ephemeral=True)
