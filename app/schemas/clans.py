from pydantic import BaseModel

# Estes schemas Pydantic definem a estrutura de dados para a entidade 'Clan'.
# O FastAPI os utiliza para validar, serializar e documentar os dados
# relacionados a clãs que são trocados através da API.

class ClanBase(BaseModel):
    """
    Schema base para um Clã.
    Este modelo contém os campos essenciais que são necessários tanto para
    criar um novo clã quanto para exibi-lo em uma resposta da API.
    """
    # O nome único do clã (ex: "Clã da Rocha", "Tribo do Rio").
    name: str
    
    # A chave estrangeira que associa este clã a uma espécie principal.
    # Isso pode ser usado para definir que um clã é predominantemente de uma
    # certa espécie (ex: um clã de Orcs, um clã de Elfos).
    species_id: int

class ClanCreate(ClanBase):
    """
    Schema usado para validar os dados de entrada ao criar um novo clã.
    Ele herda todos os campos do `ClanBase`.
    
    Manter esta classe separada é uma boa prática, pois permite adicionar
    validações ou campos específicos para o processo de criação no futuro,
    sem afetar os outros schemas.
    """
    pass

class Clan(ClanBase):
    """
    Schema completo para representar um Clã, geralmente usado em respostas da API.
    Ele herda os campos do `ClanBase` e adiciona os campos que são gerados
    e gerenciados pelo banco de dados, como o ID.
    """
    # O ID único do clã, gerado automaticamente pelo banco de dados.
    # Este campo é usado para identificar o clã de forma única em toda a aplicação.
    id: int

    class Config:
        """
        Configurações internas para o comportamento do modelo Pydantic.
        """
        # A configuração `from_attributes = True` (anteriormente `orm_mode = True`)
        # é fundamental para a integração com ORMs como o SQLAlchemy.
        # Ela permite que o Pydantic leia os dados diretamente dos atributos de um
        # objeto de modelo do SQLAlchemy (ex: clan.id, clan.name), facilitando
        # a conversão do objeto do banco de dados para um formato JSON válido
        # que pode ser enviado como resposta da API.
        from_attributes = True
