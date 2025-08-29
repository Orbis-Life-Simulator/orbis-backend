from fastapi import WebSocket
from typing import List, Dict

# A classe ConnectionManager é responsável por gerenciar e organizar todas as
# conexões WebSocket ativas com o servidor. Ela atua como um "hub" central
# para saber quem está conectado e para onde enviar as mensagens.
class ConnectionManager:
    def __init__(self):
        """
        Inicializa o gerenciador de conexões.
        'active_connections' é a estrutura de dados principal. É um dicionário onde:
        - A chave (key) é o 'world_id' (um inteiro), representando um mundo específico da simulação.
        - O valor (value) é uma lista de objetos WebSocket, contendo todas as conexões
          de clientes que estão "assistindo" àquele mundo específico.
        Isso nos permite enviar atualizações apenas para os clientes interessados em um
        determinado mundo, em vez de para todos os clientes conectados.
        """
        self.active_connections: Dict[int, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, world_id: int):
        """
        Registra uma nova conexão de cliente (via WebSocket) e a associa a um mundo.

        Args:
            websocket (WebSocket): O objeto da conexão WebSocket fornecido pelo FastAPI.
            world_id (int): O ID do mundo ao qual o cliente está se conectando.
        """
        # Aceita a solicitação de conexão do cliente. Este é um passo obrigatório
        # no protocolo WebSocket para estabelecer a comunicação.
        await websocket.accept()

        # Se este for o primeiro cliente a se conectar a este 'world_id',
        # precisamos primeiro inicializar a lista de conexões para ele.
        if world_id not in self.active_connections:
            self.active_connections[world_id] = []
        
        # Adiciona a nova conexão à lista de conexões ativas para o mundo especificado.
        self.active_connections[world_id].append(websocket)

    def disconnect(self, websocket: WebSocket, world_id: int):
        """
        Remove uma conexão WebSocket da lista de conexões ativas quando um cliente se desconecta.

        Args:
            websocket (WebSocket): O objeto da conexão que está sendo encerrada.
            world_id (int): O ID do mundo ao qual o cliente estava conectado.
        """
        # Verifica se o mundo existe no nosso dicionário para evitar erros.
        if world_id in self.active_connections:
            # Remove o objeto WebSocket específico da lista de conexões daquele mundo.
            self.active_connections[world_id].remove(websocket)

    async def broadcast(self, message: str, world_id: int):
        """
        Envia uma mensagem para TODOS os clientes conectados a um mundo específico.

        Args:
            message (str): A mensagem (geralmente em formato JSON) a ser enviada.
            world_id (int): O ID do mundo para o qual a mensagem deve ser transmitida.
        """
        # Verifica se há alguma conexão ativa para este mundo antes de tentar enviar.
        if world_id in self.active_connections:
            # Itera sobre cada objeto de conexão na lista correspondente ao 'world_id'.
            for connection in self.active_connections[world_id]:
                # Envia a mensagem de texto para o cliente através da sua conexão WebSocket.
                await connection.send_text(message)

# Cria uma instância única e global do ConnectionManager.
# Este padrão (Singleton) é muito comum em aplicações web, pois garante que
# todas as partes da sua aplicação (diferentes rotas de API, processos em background, etc.)
# usem o mesmo objeto para gerenciar o estado das conexões. Isso evita que as listas
# de conexões fiquem dessincronizadas.
manager = ConnectionManager()
