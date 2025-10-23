import os
import json
from google import genai
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    raise ValueError(
        "A chave da API do Gemini não foi configurada. Verifique seu arquivo .env"
    )

PROMPT_TEMPLATE = """
Você é um interpretador de comandos para o simulador de mundos Orbis. Sua única tarefa é analisar o pedido do usuário, considerando o contexto atual do mundo, e traduzi-lo para uma estrutura JSON que o sistema possa executar.

As funções disponíveis são:
1. `declarar_guerra`: Inicia um conflito entre dois clãs.
   Parâmetros: `cla_agressor` (string), `cla_alvo` (string).

2. `formar_alianca`: Cria uma aliança entre dois clãs.
   Parâmetros: `cla_A` (string), `cla_B` (string).

3. `criar_missao_conquista`: Cria uma missão para conquistar um território.
   Parâmetros: `cla_executor` (string), `territorio_alvo` (string), `titulo_missao` (string).

4. `gerar_evento_global`: Inicia um evento que afeta o mundo todo.
   Parâmetros: `nome_evento` (string, ex: "PRAGA", "INVERNO_RIGOROSO"), `duracao_ticks` (integer).

5. `informar_usuario`: Usado quando o pedido do usuário não pode ser executado por causa do estado atual do mundo.
   Parâmetros: `mensagem` (string, explicando o motivo).


Analise o pedido do usuário e retorne APENAS o JSON correspondente, sem nenhuma outra palavra ou explicação.

**Exemplo 1:**
Contexto Atual do Mundo: Nenhum evento global ativo.
Pedido do usuário: "Faça o Clã Martelo de Ferro declarar guerra à Corte de Aetherion."
Sua resposta:
{{
  "name": "declarar_guerra",
  "args": {{
    "cla_agressor": "Clã Martelo de Ferro",
    "cla_alvo": "Corte de Aetherion"
  }}
}}

**Exemplo 2:**
Contexto Atual do Mundo: Já existe um evento de 'PRAGA' ativo.
Pedido do usuário: "Inicie uma praga no mundo."
Sua resposta:
{{
  "name": "informar_usuario",
  "args": {{
    "mensagem": "Não é possível iniciar uma 'PRAGA', pois este evento já está ativo no mundo."
  }}
}}

**Exemplo 3:**
Contexto Atual do Mundo: Nenhum evento global ativo.
Pedido do usuário: "Quero que um inverno rigoroso dure por 200 ticks."
Sua resposta:
{{
  "name": "gerar_evento_global",
  "args": {{
    "nome_evento": "INVERNO_RIGOROSO",
    "duracao_ticks": 200
  }}
}}

Agora, processe o seguinte pedido.

Contexto Atual do Mundo:
{contexto_mundo}

Pedido do usuário: "{user_decreto}"
Sua resposta:
"""


def interpretar_decreto(decreto_usuario: str, contexto_mundo: str) -> dict | None:
    """
    Envia o comando do usuário e o contexto do mundo para o Gemini e pede
    para ele gerar um JSON estruturado como resposta.
    """
    try:
        model = genai.GenerativeModel(model_name="gemini-pro")

        prompt_final = PROMPT_TEMPLATE.format(
            user_decreto=decreto_usuario, contexto_mundo=contexto_mundo
        )

        print(f"Enviando para o Gemini (modelo 'gemini-pro'): '{decreto_usuario}'")

        response = model.generate_content(prompt_final)

        print("--- RESPOSTA BRUTA DA API GEMINI ---")
        print(response.text)
        print("---------------------------------")

        cleaned_text = (
            response.text.strip().replace("```json", "").replace("```", "").strip()
        )
        comando_json = json.loads(cleaned_text)

        return comando_json

    except json.JSONDecodeError as e:
        print(
            f"!!! ERRO DE DECODIFICAÇÃO JSON: A resposta da IA não era um JSON válido. Erro: {e}"
        )
        print(f"Resposta recebida: {response.text}")
        return None
    except Exception as e:
        print(f"!!! ERRO INESPERADO ao interpretar decreto com Gemini: {e}")
        import traceback

        traceback.print_exc()
        return None
