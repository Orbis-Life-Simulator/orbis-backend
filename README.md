# Orbis - Backend (Simulador de Vida com IA)

Este repositório contém o código-fonte do back-end para o projeto "Orbis", um simulador de vida 2D.

A aplicação é desenvolvida em Python utilizando o framework FastAPI e se comunica com um banco de dados MongoDB para gerenciar a lógica da simulação, o estado do mundo e a persistência de eventos.

## Tecnologias

- **Linguagem:** Python 3.9+
- **Framework:** FastAPI (com WebSockets)
- **Banco de Dados:** MongoDB (via Motor/Pymongo)
- **IA:** Integração com Google Gemini para narrativa e Árvores de Comportamento para os agentes.
- **Análise de Dados:** Pandas (processamento de logs de eventos).

## Como Rodar o Projeto Localmente

Siga os passos abaixo para configurar e executar o servidor da API em sua máquina local.

### 1. Pré-requisitos

- **Python 3.9** ou superior instalado.
- **Git** para clonar o repositório.
- Uma conta no **MongoDB** (Atlas ou instalação local).
- Uma **Chave de API do Google Gemini** (opcional, mas necessária para o modo Storyteller).

### 2. Clone e Configure o Ambiente

```bash
# Clone este repositório
git clone <URL_DO_SEU_REPOSITORIO>

# Entre na pasta do projeto
cd <NOME_DO_DIRETORIO>

# Crie um ambiente virtual
python -m venv venv
```

### 3. Ative o Ambiente Virtual

A ativação depende do seu sistema operacional:

- **Windows (PowerShell):**

  ```powershell
  .\venv\Scripts\activate
  ```

  > **Nota:** Se receber um erro de permissão (*"running scripts is disabled"*), execute o comando abaixo e tente novamente:
  > `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser`

- **Windows (CMD / Prompt de Comando):**

  ```cmd
  venv\Scripts\activate.bat
  ```

- **Linux ou macOS (Bash/Zsh):**

  ```bash
  source venv/bin/activate
  ```

### 4. Configuração de Variáveis de Ambiente (.env)

Para que a aplicação funcione, é **obrigatório** criar um arquivo de configuração.

1. Crie um arquivo chamado `.env` na raiz do projeto.
2. Cole o conteúdo abaixo, substituindo pelos seus valores:

```ini
# Chave da API do Google Gemini (para o modo Criador/Storyteller)
# Se não tiver uma, pode deixar em branco, mas a funcionalidade de chat não funcionará.
GEMINI_API_KEY=sua_chave_aqui


MONGO_URI=# String de conexão do MongoDB (Local ou Atlas)
```

### 5. Instale as Dependências

Com o ambiente virtual ativado, instale as bibliotecas:

```bash
pip install -r requirements.txt
```

### 6. Inicie o Servidor

Inicie o servidor de desenvolvimento com o Uvicorn:

```bash
uvicorn app.main:app --reload
```

- **API:** Acessível em `http://127.0.0.1:8000`
- **Documentação (Swagger):** Acessível em `http://127.0.0.1:8000/docs`

### 7. Parar o Servidor

- Para encerrar o servidor, pressione **`Ctrl+C`** no terminal.
- Para sair do ambiente virtual:

```bash
deactivate
```
