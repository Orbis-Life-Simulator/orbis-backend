from pydantic import BaseModel

# Estes schemas Pydantic definem a estrutura de dados para a entidade 'Species'.
# Eles são utilizados pelo FastAPI para validar dados de entrada (payloads de requisição),
# formatar dados de saída (respostas da API) e gerar a documentação interativa
# da API automaticamente.

# Propriedades base compartilhadas por todos os schemas de espécie.
class SpeciesBase(BaseModel):
    """
    Schema base para uma Espécie.
    Este modelo contém os atributos fundamentais que definem as características
    básicas de qualquer espécie no mundo da simulação.
    """
    # O nome da espécie (ex: "Humano", "Orc", "Elfo", "Zumbi").
    # Este campo geralmente deve ser único.
    name: str

    # A quantidade de pontos de vida (saúde) que um membro desta espécie
    # possui por padrão ao ser criado.
    base_health: int

    # O valor de dano base que um membro desta espécie causa em um ataque.
    base_strength: int

# Schema para a criação de uma espécie (usado em requisições POST).
class SpeciesCreate(SpeciesBase):
    """
    Schema usado para validar os dados recebidos ao criar uma nova espécie.
    Ele herda todos os campos do `SpeciesBase`. Manter esta classe separada
    (mesmo que esteja vazia com 'pass') é uma boa prática de design, pois permite
    adicionar validações ou campos específicos para o processo de criação no futuro,
    sem impactar o schema de leitura.
    """
    pass

# Schema para a leitura de uma espécie (usado em respostas GET).
class Species(SpeciesBase):
    """
    Schema completo que representa uma espécie, geralmente usado em respostas da API.
    Ele herda todos os campos do `SpeciesBase` e adiciona os campos que são
    gerados e gerenciados pelo banco de dados, como o ID.
    """
    # O identificador único da espécie, gerado automaticamente pelo banco de dados.
    id: int

    class Config:
        """
        Configurações internas para o comportamento do modelo Pydantic.
        """
        # A configuração `from_attributes = True` (conhecida como `orm_mode` em versões
        # mais antigas do Pydantic) é essencial para a integração com ORMs como o SQLAlchemy.
        # Ela instrui o Pydantic a ler os valores dos campos diretamente dos atributos de
        # um objeto de modelo do banco de dados (ex: species.id) em vez de esperar
        # um dicionário (ex: species['id']). Isso simplifica enormemente a conversão
        # de um objeto do banco de dados para uma resposta JSON na API.
        from_attributes = True
