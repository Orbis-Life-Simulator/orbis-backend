# Orbis - Backend (Simulador de Vida com IA)

Este repositório contém o código-fonte do back-end para o projeto "Orbis", um simulador de vida 2D.

A aplicação é desenvolvida em Python utilizando o framework FastAPI e se comunica com um banco de dados para gerenciar a lógica da simulação e o estado do mundo.

## Tecnologias

- **Linguagem:** Python 3.9+
- **Framework:** FastAPI
- **Banco de Dados:** MongoDB (via Motor/Pymongo) e/ou SQLite
- **IA:** Integração com Google Gemini e Lógica de Máquina de Estados Finitos (FSM).

## Como Rodar o Projeto Localmente

Siga os passos abaixo para configurar e executar o servidor da API em sua máquina local.

### 1. Pré-requisitos

- Certifique-se de ter o [Python 3.9](https://www.python.org/downloads/) ou superior instalado.
- Git para clonar o repositório.
- Uma conta no MongoDB (Atlas ou local) e uma chave de API do Google Gemini.

### 2. Clone e Configure o Ambiente

```bash
# Navegue para o diretório do projeto
cd orbis-backend

# Crie um ambiente virtual para isolar as dependências
python -m venv venv
```

### 3. Ative o Ambiente Virtual

A ativação depende do seu sistema operacional e do terminal que você está usando:

- **Linux, macOS ou Windows (usando Git Bash):**
   Utilize o comando `source`. Este comando é específico para terminais baseados em Unix/Bash.

  ```bash
  source venv/bin/activate
  ```

- **Windows (usando PowerShell ou CMD):**
  Execute o script de ativação diretamente.

  ```powershell
  venv\Scripts\activate
  ```

### 4. Configuração de Variáveis de Ambiente (.env)

Para que a aplicação funcione, é **obrigatório** configurar as chaves de acesso.

1. Crie um arquivo chamado `.env` na raiz do projeto (no mesmo nível que `main.py` ou `requirements.txt`).
2. Adicione as seguintes variáveis ao arquivo, substituindo pelos seus valores reais:

```env
GEMINI_API_KEY=sua_chave_da_api_google_gemini_aqui (Se nao tiver uma chave de api do gemini, pode ser uma chave aleatória) 
MONGO_URI=sua_string_de_conexao_mongodb_aqui
```

> **Nota:** Sem este arquivo configurado corretamente, a conexão com o banco de dados e as funcionalidades de IA não funcionarão.

### 5. Instale as Dependências

Com o ambiente virtual ativado e o `.env` criado, instale as bibliotecas necessárias:

```bash
pip install -r requirements.txt
```

### 6. Popule o Banco de Dados

Para que a simulação tenha dados iniciais (espécies, clãs, recursos, etc.), execute o script de "seeding":

```bash
python seed_db.py
```

### 7. Inicie o Servidor

Use o Uvicorn para iniciar o servidor de desenvolvimento do FastAPI. A flag `--reload` faz com que o servidor reinicie automaticamente sempre que você salvar uma alteração no código.

```bash
uvicorn app.main:app --reload
```

A API estará rodando e acessível em `http://127.0.0.1:8000`. Para ver a documentação interativa e testar os endpoints, acesse `http://127.0.0.1:8000/docs`.

### 8. Pare o Servidor e Desative o Ambiente

- Para **parar o servidor**, volte ao terminal onde ele está rodando e pressione **`Ctrl+C`**.
- Quando terminar de trabalhar no projeto, você pode **desativar o ambiente virtual** com o comando:

```bash
deactivate
