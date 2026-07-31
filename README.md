# 🕵️‍♂️ Bot da Cúpula — Cosa Nostra System

Bot de Discord dedicado à gestão de uma hierarquia mafiosa, com painéis interativos, sistema de votações agregadas, tradução automática e muito mais.

---

## 📦 Estrutura do projeto
bot-mafia/
├── main.py # Ponto de entrada (executa o bot e carrega os cogs)
├── bot.py # Instância do bot (comandos, intents, prefixo)
├── config.py # Constantes (famílias, limite de soldados, etc.)
├── servidor_dummy.py # Servidor web para manter o Render acordado
├── requirements.txt # Dependências do Python
├── README.md # Este ficheiro
└── cogs/ # Extensões modulares (funcionalidades)
├── init.py # Torna a pasta um package Python
├── logs.py # Função de logs da Máfia
├── traducao.py # Sistema de tradução automática (botões por mensagem)
├── votacoes.py # Criação de votações, agregação de resultados, polls temporárias
├── paineis.py # Views e comandos para os painéis (Ranks, Capos, Soldiers)
└── comandos_setup.py # Comandos de configuração e relatório

text

---

## ⚙️ Funcionalidades principais

### 🗳️ Votações da Cúpula (`/votacao`)

- **Comando slash** exclusivo para administradores.
- Abre um modal onde se define a pergunta, as opções (máx. 10) e a duração em horas.
- Ao submeter:
  - Para cada família **com um Capo ativo**, o bot envia uma poll nativa no canal `🗳️-votações` do QG da família.
  - No canal central (onde o comando foi executado) é enviada uma poll permanente + um **painel agregado** com o total de votos em tempo real.
  - As polls das famílias são **automaticamente apagadas** após o tempo definido.
  - O painel agregado mostra quantos votaram, quantos membros são elegíveis (Don, Capo, Soldier, Consigliere, Capodecina, Assistente) e quantos ainda faltam votar.
  - O resultado agregado possui um **botão "Delete"** (só administradores) para limpar o registo.

### 🗂️ Painéis de hierarquia

- **`!setup_ranks`** – Publica um embed com a hierarquia completa da organização.
- **`!setup_capo`** – Publica uma mensagem com botões para cada família. Capos podem clicar no nome da sua família para **reivindicar a liderança** e criar automaticamente o QG privado (categoria, canais de texto e voz).
- **`!setup_soldier`** – Publica uma mensagem com botões para Soldiers se alistarem numa família (máx. 20 soldados por família, desde que haja um Capo ativo).

### 🌐 Tradução automática

- **Botão "Traduzir"** em cada mensagem enviada no chat. O bot apaga a mensagem original do utilizador e reenvia o texto com o botão.
- A tradução é apresentada de forma efémera e no idioma configurado no Discord do utilizador.
- Cache de traduções para evitar chamadas repetidas ao Google Translate.

### 📢 Propagação de comunicados

- Qualquer mensagem enviada no canal **`🎯-capos-message`** é automaticamente replicada para o canal `🚨-warnings` de todas as famílias que tenham QG.

### 📊 Relatórios

- **`!status_familias`** – Mostra o Capo e o número atual de Soldiers de cada família.

### 🔧 Comandos de configuração

- **`!sync`** – Sincroniza os comandos de barra (slash commands) no servidor atual.
- **`!setup_logs`** – Cria o canal `🕶️-mafia-logs` (registo de auditoria).
- **`!setup_capos_message`** – Cria o canal central `🎯-capos-message`.
- **`!setup_vota_message`** – Cria o canal central `🗳️ vote-command`.

---

## 🚀 Como usar (localmente)

1. **Clona o repositório**:
   ```bash
   git clone https://github.com/teu-usuario/bot-mafia.git
   cd bot-mafia
Instala as dependências:

bash
pip install -r requirements.txt
Cria um ficheiro .env (ou define a variável de ambiente) com o token do bot:

text
DISCORD_TOKEN=o_teu_token_aqui
Executa o bot:

bash
python main.py
🏗️ Deploy no Render (recomendado)
Cria um Web Service no Render e liga ao teu repositório.

Configura:

Build Command: pip install -r requirements.txt

Start Command: python main.py

Adiciona a variável de ambiente DISCORD_TOKEN com o token do bot.

O bot inclui um servidor dummy para evitar que o Render adormeça (necessário no plano gratuito). Para máxima eficácia, configura também um UptimeRobot a pingar o URL do serviço a cada 5 minutos.

📜 Dependências
discord.py>=2.4.0

deep-translator>=1.11.4

aiohttp>=3.9.0

👥 Contribuições
Sente‑te à vontade para abrir issues ou pull requests.
Honra e lealdade acima de tudo. 🍷

📝 Licença
Este projeto é distribuído sob a licença MIT.
Omertà: a palavra é um contrato de sangue. O silêncio é a nossa parede.

text

Basta copiares este conteúdo para um ficheiro chamado `README.md` na raiz do teu repositório. Ele fornece uma visão completa e profissional do teu bot, ideal para quem quiser entender ou colaborar no projeto.
