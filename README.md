# Orbis - Backend (Simulador de Vida com IA)

Este repositório contém o código-fonte do back-end para o projeto "Orbis", um simulador de vida 2D.

A aplicação é desenvolvida em Python utilizando o framework FastAPI e se comunica com um banco de dados SQLite para gerenciar a lógica da simulação e o estado do mundo.

## Tecnologias

- **Linguagem:** Python 3.9+
- **Framework:** FastAPI
- **Banco de Dados:** SQLite (via SQLAlchemy)
- **IA:** Lógica de script e Máquina de Estados Finitos (FSM) para o comportamento dos personagens.

## Como Rodar o Projeto Localmente

Siga os passos abaixo para configurar e executar o servidor da API em sua máquina local.

### 1. Pré-requisitos

- Certifique-se de ter o [Python 3.9](https://www.python.org/downloads/) ou superior instalado.
- Git para clonar o repositório.

### 2. Clone e Configure o Ambiente

```bash
# Clone este repositório para sua máquina local
git clone <URL_DO_SEU_REPOSITORIO>

# Navegue para o diretório do projeto
cd <NOME_DO_DIRETORIO>

# Crie um ambiente virtual para isolar as dependências
python -m venv venv
```

### 3. Ative o Ambiente Virtual e Instale as Dependências

Para ativar o ambiente, use o comando correspondente ao seu sistema operacional:

```bash
# No Linux ou macOS (usando um terminal bash)
source venv/bin/activate

# No Windows (usando PowerShell ou CMD)
source venv/Scripts/activate
```

Com o ambiente ativado, instale todas as bibliotecas necessárias:

```bash
pip install -r requirements.txt
```

### 4. Popule o Banco de Dados

Para que a simulação funcione, o banco de dados precisa ser preenchido com dados iniciais (espécies, clãs, recursos, etc.). Execute o script de "seeding":

```bash
python seed_db.py
```

Isso criará um arquivo `orbis.db` na raiz do projeto com todas as tabelas e dados necessários.

### 5. Inicie o Servidor

Use o Uvicorn para iniciar o servidor de desenvolvimento do FastAPI. A flag `--reload` faz com que o servidor reinicie automaticamente sempre que você salvar uma alteração no código.

```bash
uvicorn app.main:app --reload
```

A API estará rodando e acessível em `http://127.0.0.1:8000`. Para ver a documentação interativa e testar os endpoints, acesse `http://127.0.0.1:8000/docs`.

### 6. Pare o Servidor e Desative o Ambiente

- Para **parar o servidor**, volte ao terminal onde ele está rodando e pressione **`Ctrl+C`**.
- Quando terminar de trabalhar no projeto, você pode **desativar o ambiente virtual** com o comando:

```bash
deactivate
```
