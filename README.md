# 🕵️‍♂️ Bot da Cúpula — Cosa Nostra System

Bot de Discord dedicado à gestão de uma hierarquia mafiosa, com painéis interativos, sistema de votações agregadas, tradução automática e muito mais.

---

## 📦 Estrutura do projeto

- **`main.py`** – Ponto de entrada (executa o bot e carrega os módulos)
- **`bot.py`** – Instância do bot (comandos, intents, prefixo)
- **`config.py`** – Constantes (famílias, limite de soldados, cargos elegíveis)
- **`servidor_dummy.py`** – Servidor web para manter o Render acordado
- **`requirements.txt`** – Dependências do Python
- **`README.md`** – Este ficheiro
- **`cogs/`** – Funcionalidades modulares
  - **`__init__.py`** – Torna a pasta um package Python
  - **`logs.py`** – Função de logs da Máfia
  - **`traducao.py`** – Sistema de tradução automática (botões por mensagem)
  - **`votacoes.py`** – Votações, agregação de resultados e polls temporárias
  - **`paineis.py`** – Views e comandos para os painéis (Ranks, Capos, Soldiers)
  - **`comandos_setup.py`** – Comandos de configuração e relatório

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
