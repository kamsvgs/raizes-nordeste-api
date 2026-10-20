# Raízes do Nordeste – API Back-End

Projeto Multidisciplinar (trilha **Back-End**) – estudo de caso da rede de lanchonetes *Raízes do Nordeste*.
API REST em **Python 3.12 + FastAPI + SQLAlchemy** que implementa o **Fluxo A: Pedido → Pagamento mock → Atualização de status**,
com estoque por unidade, fidelização com consentimento (LGPD), promoções e auditoria.

> O relatório do projeto (PDF) descreve o contrato, o DER, os diagramas e o plano de testes que esta API implementa.

## Links e evidências
| Item | Onde |
|---|---|
| Repositório Git público | https://github.com/kamsvgs/raizes-nordeste-api.git |
| Swagger/OpenAPI (local) | http://localhost:8000/docs (JSON em `/openapi.json`) |
| Coleção Postman | `postman/raizes-nordeste.postman_collection.json` (ambiente em `postman/local.postman_environment.json`) |
| DER e diagramas UML | `docs/der.png`, `docs/casos_de_uso.png`, `docs/classes.png`, `docs/sequencia.png`, `docs/estados_pedido.png`, `docs/camadas.png` |
| Deploy (opcional) | — |

## Requisitos
- **Linguagem:** Python 3.11+ (testado com 3.12) · **Git**
- **Banco de dados:** SQLite (já incluso no Python, nenhuma instalação necessária); PostgreSQL é compatível via `DATABASE_URL`
- **Dependências:** `requirements.txt` (FastAPI, SQLAlchemy 2, Alembic, PyJWT, bcrypt, pytest…)
- (Opcional) Node.js, para rodar a coleção Postman via Newman

## Instalação e execução (Windows PowerShell)
```powershell
git clone https://github.com/kamsvgs/raizes-nordeste-api.git
cd raizes-nordeste-api
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env          # ajuste SECRET_KEY
alembic upgrade head                 # cria o banco (SQLite) e as tabelas
python -m app.infrastructure.db.seed # carrega dados de exemplo
uvicorn app.api.main:app --reload    # http://localhost:8000
```
Linux/macOS: `source .venv/bin/activate` e `cp .env.example .env`.

- **Painel de testes:** http://localhost:8000
- **Swagger (OpenAPI):** http://localhost:8000/docs  ·  JSON: http://localhost:8000/openapi.json
- **Saúde:** `GET /health`

## Usuários do seed (senha de todos: `Senha@123`)
| Perfil | E-mail | Vínculo |
|---|---|---|
| ADMIN | admin@raizes.test | rede |
| GERENTE | gerente.recife@raizes.test | unidade 1 (Recife) |
| ATENDENTE | atendente.recife@raizes.test | unidade 1 |
| COZINHA | cozinha.recife@raizes.test | unidade 1 |
| CLIENTE | cliente@raizes.test | com consentimento de fidelidade |
| CLIENTE | cliente2@raizes.test | sem consentimento |

Unidades: 1 (Recife, cozinha completa) e 2 (Fortaleza, cardápio reduzido). Produtos 10 a 15 (15 = sazonal).

## Painel de testes (jeito mais simples)
Com a API rodando, abra **http://localhost:8000** (a raiz): um painel em português, com botões, para fazer o fluxo completo sem
escrever JSON – entrar por perfil, ver o cardápio, criar pedido, pagar (aprovado, recusado ou falha do gateway), acompanhar o
andamento (cozinha, atendente, gerente) e repor estoque. O painel mostra, no rodapé, a resposta técnica de cada chamada.
Ele é só uma conveniência para testes manuais: a documentação oficial da API continua sendo o Swagger.

## Como testar no Swagger
1. `POST /auth/login` com um usuário acima → copie `accessToken`.
2. Clique em **Authorize** e cole o token.
3. Fluxo: `GET /unidades/1/cardapio` → `POST /pedidos` → `POST /pedidos/{id}/pagamento` → `PATCH /pedidos/{id}/status`.

**Tokens do pagamento mock:** `tok_aprovado` (200, pedido PAGO) · `tok_recusado` (402, pedido CANCELADO e estoque devolvido) ·
`tok_timeout` (503, pedido segue AGUARDANDO_PAGAMENTO; pode tentar de novo).

## Testes
```powershell
pytest                                # 38 testes automatizados (cenários T01–T20 do relatório + regras extras)
```
Coleção Postman/Newman (com a API rodando e o seed recém-aplicado – a coleção altera estoque e cria pedidos):
```powershell
npm install -g newman
newman run postman/raizes-nordeste.postman_collection.json -e postman/local.postman_environment.json
```
Teste de concorrência de estoque (20 pedidos simultâneos disputando 5 unidades → exatamente 5 criados, 15 com 409):
```powershell
python tests/carga_concorrencia.py
```
Ordem das pastas: Auth → Cardapio → Estoque → Pedidos → Pagamento → Status → Fidelidade → Auditoria → Erros.
Para repetir a execução, recrie o banco (apague `raizes.db`, rode `alembic upgrade head` e o seed).

## Estrutura
```
app/
  domain/          enums, exceções, regras de negócio puras (regras.py) e porta do gateway (ports.py)
  application/     casos de uso (pedidos, pagamentos, estoque, fidelidade, catálogo, contas)
  infrastructure/  db (models, repositórios, seed), gateways (mock), security (JWT/bcrypt), auditoria
  api/             routers, schemas (DTOs), dependências, tratamento padronizado de erros, main.py
alembic/           migrations     tests/   pytest     postman/   coleção e ambiente     docs/   diagramas UML e DER
```

## Convenções da API
- Erros sempre no formato `{error, message, details[], timestamp, path, requestId}`.
- Status: 200/201/204 sucesso · 400 JSON malformado · 401 sem token/credenciais · 402 pagamento recusado ·
  403 sem permissão · 404 não encontrado · 409 conflito de regra (estoque, transição) · 422 validação · 503 gateway.
- Listagens paginadas: `?page=1&limit=10` (máx. 100) → `{items, page, limit, total}`.
- `POST /pedidos` aceita `Idempotency-Key` (repetição retorna o pedido original com 200).
- `canalPedido` obrigatório: `APP`, `TOTEM`, `BALCAO`, `PICKUP`, `WEB`; filtro `GET /pedidos?canalPedido=TOTEM`.

## Segurança e LGPD (resumo)
Senhas com bcrypt · JWT com expiração · autorização por perfil e por unidade · respostas sem dados sensíveis ·
consentimento por finalidade com histórico imutável · `DELETE /clientes/me` anonimiza o titular · auditoria de ações sensíveis (`GET /auditoria`, ADMIN) ·
nenhum dado de cartão é armazenado.

## Variáveis de ambiente (`.env`, modelo em `.env.example`)
| Variável | Para que serve | Padrão |
|---|---|---|
| `DATABASE_URL` | string de conexão (SQLite local; PostgreSQL recomendado em produção) | `sqlite:///./raizes.db` |
| `SECRET_KEY` | segredo de assinatura do JWT (**troque**; gere com `python -c "import secrets; print(secrets.token_urlsafe(48))"`) | valor de desenvolvimento |
| `ACCESS_TOKEN_MINUTES` | validade do token | `60` |
| `BCRYPT_ROUNDS` | custo do hash de senha | `12` |

## Observabilidade
Cada requisição gera uma linha de log com `requestId`, método, rota, status e tempo (`raizes.acesso`); o mesmo `requestId`
volta no cabeçalho `X-Request-Id` e em todo erro JSON, permitindo correlacionar com a trilha de auditoria.
