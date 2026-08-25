"""Configuração do Superset para o ambiente local do gov-bricks (ADR-0019).

Sobrepõe o config padrão da imagem — só o que a DAG de publicação precisa para
funcionar. Em homologação e produção, o mesmo ajuste precisa existir no config
do deployment.
"""

# A API de papéis e permissões do Flask-AppBuilder não é registrada por padrão:
# sem isto, /api/v1/security/roles/ responde 404 e a DAG de publicação não tem
# como criar papel nem conceder dataset a ninguém (ADR-0020). O Superset expõe
# por padrão apenas login, refresh, csrf_token e guest_token.
FAB_ADD_SECURITY_API = True
