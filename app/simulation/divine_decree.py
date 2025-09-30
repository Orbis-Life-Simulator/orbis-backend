import os
import json
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    raise ValueError(
        "A chave da API do Gemini não foi configurada. Verifique seu arquivo .env"
    )

genai.configure(api_key=api_key)

PROMPT_TEMPLATE = """
Você é um interpretador de comandos para o simulador de mundos Orbis. Sua única tarefa é analisar o pedido do usuário e traduzi-lo para uma estrutura JSON que o sistema possa executar.

As funções disponíveis são:
1. `declarar_guerra`: Inicia um conflito entre dois clãs.
   Parâmetros: `cla_agressor` (string), `cla_alvo` (string).

2. `formar_alianca`: Cria uma aliança entre dois clãs.
   Parâmetros: `cla_A` (string), `cla_B` (string).

3. `criar_missao_conquista`: Cria uma missão para conquistar um território.
   Parâmetros: `cla_executor` (string), `territorio_alvo` (string), `titulo_missao` (string).

Analise o pedido do usuário e retorne APENAS o JSON correspondente, sem nenhuma outra palavra, explicação ou formatação markdown de código.

**Exemplo 1:**
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
Pedido do usuário: "Quero que o Reino de Valmor receba a missão 'Proteger as Planícies' para conquistar as Planícies Centrais."
Sua resposta:
{{
  "name": "criar_missao_conquista",
  "args": {{
    "cla_executor": "Reino de Valmor",
    "territorio_alvo": "Planícies Centrais",
    "titulo_missao": "Proteger as Planícies"
  }}
}}

Agora, processe o seguinte pedido.

Pedido do usuário: "{user_decreto}"
Sua resposta:
"""


def interpretar_decreto(decreto_usuario: str) -> dict | None:
    """
    Envia o comando do usuário para o Gemini e pede para ele gerar um JSON
    estruturado como resposta.
    """
    model = genai.GenerativeModel(model_name="gemini-1.5-pro-latest")

    prompt_final = PROMPT_TEMPLATE.format(user_decreto=decreto_usuario)

    try:
        print(f"Enviando para o Gemini (modo JSON): '{decreto_usuario}'")
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
