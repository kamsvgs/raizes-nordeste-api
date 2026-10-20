"""Cenários T01–T20 do plano de testes do relatório (mesmos nomes e resultados esperados)."""
NOVO = {"canalPedido": "TOTEM", "unidadeId": 1, "itens": [{"produtoId": 10, "quantidade": 2}]}


def criar(client, h, quem="cliente", body=None, **hd):
    return client.post("/pedidos", json=body or NOVO, headers={**h[quem], **hd})


def pagar(client, h, pid, token="tok_aprovado", quem="cliente"):
    return client.post(f"/pedidos/{pid}/pagamento", json={"formaPagamento": "MOCK", "tokenCartao": token},
                       headers=h[quem])


def saldo_estoque(client, h, produto=10, unidade=1):
    r = client.get(f"/unidades/{unidade}/estoque", headers=h["gerente"])
    return next(i["quantidade"] for i in r.json() if i["produtoId"] == produto)


# ----------------------------- positivos -----------------------------
def test_t01_login_valido(client):
    r = client.post("/auth/login", json={"email": "cliente@raizes.test", "senha": "Senha@123"})
    assert r.status_code == 200 and r.json()["tokenType"] == "Bearer" and r.json()["accessToken"]


def test_t02_cardapio(client):
    r = client.get("/unidades/1/cardapio?page=1&limit=10")
    assert r.status_code == 200
    nomes = [i["nome"] for i in r.json()["items"]]
    assert "Tapioca de queijo coalho" in nomes and r.json()["total"] == 6
    # unidade 2 tem cozinha reduzida: sem café completo e sem bolo sazonal
    r2 = client.get("/unidades/2/cardapio")
    assert r2.json()["total"] == 3


def test_t03_criar_pedido(client, h):
    r = criar(client, h)
    assert r.status_code == 201
    b = r.json()
    assert b["status"] == "AGUARDANDO_PAGAMENTO" and b["canalPedido"] == "TOTEM" and b["valorTotal"] == 25.0


def test_t04_filtrar_por_canal(client, h):
    criar(client, h)
    criar(client, h, body={**NOVO, "canalPedido": "APP"})
    r = client.get("/pedidos?canalPedido=TOTEM", headers=h["cliente"])
    assert r.status_code == 200 and r.json()["total"] == 1
    assert all(i["canalPedido"] == "TOTEM" for i in r.json()["items"])


def test_t05_pagamento_aprovado(client, h):
    pid = criar(client, h).json()["id"]
    r = pagar(client, h, pid)
    assert r.status_code == 200
    assert r.json()["pagamento"]["status"] == "APROVADO" and r.json()["pedido"]["status"] == "PAGO"
    assert r.json()["pontosCreditados"] == 25


def test_t06_cozinha_em_preparo(client, h):
    pid = criar(client, h).json()["id"]
    pagar(client, h, pid)
    r = client.patch(f"/pedidos/{pid}/status", json={"status": "EM_PREPARO"}, headers=h["cozinha"])
    assert r.status_code == 200 and r.json()["status"] == "EM_PREPARO"
    r = client.patch(f"/pedidos/{pid}/status", json={"status": "PRONTO"}, headers=h["cozinha"])
    assert r.json()["status"] == "PRONTO"
    r = client.patch(f"/pedidos/{pid}/status", json={"status": "ENTREGUE"}, headers=h["atendente"])
    assert r.json()["status"] == "ENTREGUE"


def test_t07_entrada_estoque(client, h):
    antes = saldo_estoque(client, h)
    r = client.post("/estoque/movimentos", headers=h["gerente"], json={
        "unidadeId": 1, "produtoId": 10, "tipo": "ENTRADA", "quantidade": 50, "motivo": "Reposição semanal"})
    assert r.status_code == 201 and r.json()["saldoAtual"] == antes + 50


def test_t08_idempotencia(client, h):
    antes = saldo_estoque(client, h)
    r1 = criar(client, h, **{"Idempotency-Key": "abc-1"})
    r2 = criar(client, h, **{"Idempotency-Key": "abc-1"})
    assert r1.status_code == 201 and r2.status_code == 200 and r1.json()["id"] == r2.json()["id"]
    assert saldo_estoque(client, h) == antes - 2  # baixou uma única vez


def test_t09_consentimento_e_pontos(client, h):
    r = client.post("/fidelidade/consentimentos", headers=h["cliente"],
                    json={"finalidade": "FIDELIDADE", "concedido": True, "versaoTermo": "2026-01"})
    assert r.status_code == 201
    pagar(client, h, criar(client, h).json()["id"])
    assert client.get("/fidelidade/saldo", headers=h["cliente"]).json()["pontos"] > 0


def test_t09b_sem_consentimento_nao_acumula(client, h):
    pid = criar(client, h, "cliente2").json()["id"]
    r = pagar(client, h, pid, quem="cliente2")
    assert r.status_code == 200 and r.json()["pontosCreditados"] == 0


def test_t10_auditoria(client, h):
    pid = criar(client, h).json()["id"]
    pagar(client, h, pid)
    client.patch(f"/pedidos/{pid}/status", json={"status": "EM_PREPARO"}, headers=h["cozinha"])
    r = client.get("/auditoria?entidade=pedido", headers=h["admin"])
    acoes = {i["acao"] for i in r.json()["items"]}
    assert r.status_code == 200 and {"PEDIDO_CRIADO", "PEDIDO_STATUS_ALTERADO"} <= acoes


# ----------------------------- negativos -----------------------------
def test_t11_sem_token(client):
    r = client.get("/pedidos")
    assert r.status_code == 401 and r.json()["error"] == "NAO_AUTENTICADO"


def test_t12_perfil_sem_permissao(client, h):
    r = client.post("/estoque/movimentos", headers=h["cliente"], json={
        "unidadeId": 1, "produtoId": 10, "tipo": "ENTRADA", "quantidade": 5, "motivo": "teste"})
    assert r.status_code == 403 and r.json()["error"] == "ACESSO_NEGADO"


def test_t13_canal_ausente(client, h):
    body = {k: v for k, v in NOVO.items() if k != "canalPedido"}
    r = criar(client, h, body=body)
    assert r.status_code == 422 and r.json()["error"] == "VALIDATION_ERROR"
    assert r.json()["details"][0]["field"] == "canalPedido"


def test_t13b_canal_invalido_e_json_malformado(client, h):
    assert criar(client, h, body={**NOVO, "canalPedido": "XYZ"}).status_code == 422
    r = client.post("/pedidos", content="{oops", headers={**h["cliente"], "Content-Type": "application/json"})
    assert r.status_code == 400 and r.json()["error"] == "REQUISICAO_INVALIDA"


def test_t14_quantidade_negativa(client, h):
    r = criar(client, h, body={**NOVO, "itens": [{"produtoId": 10, "quantidade": -1}]})
    assert r.status_code == 422 and r.json()["details"][0]["field"] == "itens[0].quantidade"


def test_t15_produto_inexistente(client, h):
    r = criar(client, h, body={**NOVO, "itens": [{"produtoId": 9999, "quantidade": 1}]})
    assert r.status_code == 404 and r.json()["error"] == "PRODUTO_NAO_ENCONTRADO"
    # produto existente mas fora do cardápio da unidade 2 (café completo)
    r = criar(client, h, body={"canalPedido": "APP", "unidadeId": 2, "itens": [{"produtoId": 14, "quantidade": 1}]})
    assert r.status_code == 404


def test_t16_estoque_insuficiente(client, h):
    antes = saldo_estoque(client, h)
    r = criar(client, h, body={**NOVO, "itens": [{"produtoId": 10, "quantidade": 999}]})
    assert r.status_code == 409 and r.json()["error"] == "ESTOQUE_INSUFICIENTE"
    assert "Disponível" in r.json()["details"][0]["issue"]
    assert saldo_estoque(client, h) == antes  # nada foi baixado


def test_t17_pagamento_recusado(client, h):
    antes = saldo_estoque(client, h)
    pid = criar(client, h).json()["id"]
    r = pagar(client, h, pid, "tok_recusado")
    assert r.status_code == 402 and r.json()["error"] == "PAGAMENTO_RECUSADO"
    assert client.get(f"/pedidos/{pid}", headers=h["cliente"]).json()["status"] == "CANCELADO"
    assert saldo_estoque(client, h) == antes  # estoque devolvido


def test_t18_gateway_indisponivel(client, h):
    pid = criar(client, h).json()["id"]
    r = pagar(client, h, pid, "tok_timeout")
    assert r.status_code == 503 and r.json()["error"] == "GATEWAY_INDISPONIVEL"
    assert client.get(f"/pedidos/{pid}", headers=h["cliente"]).json()["status"] == "AGUARDANDO_PAGAMENTO"
    assert client.get(f"/pedidos/{pid}/pagamento", headers=h["cliente"]).json()["status"] == "ERRO_GATEWAY"
    # nova tentativa permitida
    assert pagar(client, h, pid).status_code == 200


def test_t19_transicao_invalida(client, h):
    pid = criar(client, h).json()["id"]
    r = client.patch(f"/pedidos/{pid}/status", json={"status": "ENTREGUE"}, headers=h["admin"])
    assert r.status_code == 409 and r.json()["error"] == "TRANSICAO_INVALIDA"


def test_t20_pedido_de_outro_cliente(client, h):
    pid = criar(client, h).json()["id"]
    r = client.get(f"/pedidos/{pid}", headers=h["cliente2"])
    assert r.status_code == 404 and r.json()["error"] == "PEDIDO_NAO_ENCONTRADO"


# ----------------------------- regras adicionais -----------------------------
def test_cancelamento_regras(client, h):
    antes = saldo_estoque(client, h)
    pid = criar(client, h).json()["id"]
    r = client.post(f"/pedidos/{pid}/cancelamento", json={"motivo": "Desisti do pedido"}, headers=h["cliente"])
    assert r.status_code == 200 and r.json()["status"] == "CANCELADO" and saldo_estoque(client, h) == antes
    # pedido pago: cliente não cancela, gerente sim (RN11)
    pid2 = criar(client, h).json()["id"]
    pagar(client, h, pid2)
    assert client.post(f"/pedidos/{pid2}/cancelamento", json={"motivo": "Quero cancelar"}, headers=h["cliente"]).status_code == 403
    r = client.post(f"/pedidos/{pid2}/cancelamento", json={"motivo": "Erro de cobrança"}, headers=h["gerente"])
    assert r.status_code == 200
    assert client.get("/fidelidade/saldo", headers=h["cliente"]).json()["pontos"] == 0  # pontos estornados


def test_pagar_duas_vezes_conflito(client, h):
    pid = criar(client, h).json()["id"]
    pagar(client, h, pid)
    r = pagar(client, h, pid)
    assert r.status_code == 409 and r.json()["error"] == "PEDIDO_NAO_AGUARDA_PAGAMENTO"


def test_resgate_de_pontos_e_promocao(client, h):
    # acumula 150 pontos (3 pedidos de R$ 50 não: usa 6 x 25 = 150)
    for _ in range(6):
        pagar(client, h, criar(client, h).json()["id"])
    assert client.get("/fidelidade/saldo", headers=h["cliente"]).json()["pontos"] == 150
    r = criar(client, h, body={**NOVO, "resgatarPontos": 100})
    assert r.status_code == 201 and r.json()["desconto"] == 5.0 and r.json()["valorTotal"] == 20.0
    assert criar(client, h, body={**NOVO, "resgatarPontos": 50}).status_code == 422  # não múltiplo de 100
    # promoção de 10% da unidade
    p = client.post("/promocoes", headers=h["gerente"], json={
        "nome": "Terça nordestina", "tipo": "PERCENTUAL", "valor": 10, "inicio": "2020-01-01", "fim": "2099-12-31",
        "unidadeId": 1})
    assert p.status_code == 201
    r = criar(client, h, "cliente2")
    assert r.json()["desconto"] == 2.5 and r.json()["valorTotal"] == 22.5


def test_lgpd_anonimizacao_e_revogacao(client, h):
    r = client.post("/fidelidade/consentimentos", headers=h["cliente"],
                    json={"finalidade": "FIDELIDADE", "concedido": False})
    assert r.status_code == 201
    pid = criar(client, h).json()["id"]
    assert pagar(client, h, pid).json()["pontosCreditados"] == 0  # consentimento revogado
    assert client.get("/clientes/me", headers=h["cliente"]).status_code == 200
    assert client.delete("/clientes/me", headers=h["cliente"]).status_code == 204
    # token antigo deixa de valer (usuário inativo)
    assert client.get("/auth/me", headers=h["cliente"]).status_code == 401
    # o histórico de pedidos permanece, sem vínculo identificável
    assert client.get(f"/pedidos/{pid}", headers=h["admin"]).status_code == 200


def test_cadastro_e_login_novo_cliente(client):
    r = client.post("/auth/register", json={"nome": "Maria Souza", "email": "maria@exemplo.com", "senha": "Senha@123"})
    assert r.status_code == 201 and "senha" not in r.text and "hash" not in r.text
    assert client.post("/auth/register", json={"nome": "Maria", "email": "maria@exemplo.com", "senha": "Senha@123"}).status_code == 409
    assert client.post("/auth/register", json={"nome": "Maria", "email": "x", "senha": "123"}).status_code == 422
    assert client.post("/auth/login", json={"email": "maria@exemplo.com", "senha": "errada"}).status_code == 401


def test_atendente_balcao_sem_cliente_e_isolamento_de_unidade(client, h):
    body = {"canalPedido": "BALCAO", "unidadeId": 1, "itens": [{"produtoId": 11, "quantidade": 1}]}
    r = client.post("/pedidos", json=body, headers=h["atendente"])
    assert r.status_code == 201 and r.json()["clienteId"] is None
    r = client.post("/pedidos", json={**body, "unidadeId": 2}, headers=h["atendente"])
    assert r.status_code == 403
    # gerente da unidade 1 não mexe no estoque da unidade 2
    r = client.post("/estoque/movimentos", headers=h["gerente"], json={
        "unidadeId": 2, "produtoId": 10, "tipo": "ENTRADA", "quantidade": 5, "motivo": "teste"})
    assert r.status_code == 403


def test_paginacao_limite_maximo(client):
    assert client.get("/produtos?limit=101").status_code == 422
    assert client.get("/produtos?limit=2").json()["limit"] == 2


def test_rota_inexistente_usa_erro_padrao(client):
    r = client.get("/nao-existe")
    assert r.status_code == 404 and {"error", "message", "details", "timestamp", "path", "requestId"} <= set(r.json())


# ----------------------------- validações adicionais da revisão -----------------------------
def test_unidade_inexistente(client, h):
    r = criar(client, h, body={**NOVO, "unidadeId": 999})
    assert r.status_code == 404 and r.json()["error"] == "UNIDADE_NAO_ENCONTRADA"


def test_token_invalido_ou_adulterado(client):
    r = client.get("/pedidos", headers={"Authorization": "Bearer abc.def.ghi"})
    assert r.status_code == 401 and r.json()["error"] == "NAO_AUTENTICADO"


def test_filtro_canal_invalido_na_listagem(client, h):
    r = client.get("/pedidos?canalPedido=XYZ", headers=h["cliente"])
    assert r.status_code == 422 and r.json()["details"][0]["field"] == "canalPedido"


def test_login_retorna_usuario_sem_dados_sensiveis(client):
    r = client.post("/auth/login", json={"email": "gerente.recife@raizes.test", "senha": "Senha@123"})
    u = r.json()["user"]
    assert u["perfil"] == "GERENTE" and u["unidadeId"] == 1 and "senha" not in r.text and "hash" not in r.text


def test_acesso_a_dados_pessoais_e_auditado(client, h):
    assert client.get("/clientes/me", headers=h["cliente"]).status_code == 200
    r = client.get("/auditoria?entidade=cliente", headers=h["admin"])
    assert "DADOS_PESSOAIS_CONSULTADOS" in {i["acao"] for i in r.json()["items"]}


def test_falha_de_login_e_auditada(client, h):
    client.post("/auth/login", json={"email": "cliente@raizes.test", "senha": "errada"})
    r = client.get("/auditoria?acao=LOGIN_FALHOU", headers=h["admin"])
    assert r.json()["total"] >= 1


def test_openapi_tem_exemplos_e_codigos_de_status(client):
    spec = client.get("/openapi.json").json()
    op = spec["paths"]["/pedidos"]["post"]
    assert {"200", "201", "400", "401", "403", "404", "409", "422"} <= set(op["responses"])
    schema_pedido = spec["components"]["schemas"]["PedidoIn"]
    assert schema_pedido["examples"][0]["canalPedido"] == "TOTEM"
    pag = spec["paths"]["/pedidos/{pedido_id}/pagamento"]["post"]["responses"]
    assert {"402", "409", "503"} <= set(pag)
    assert pag["503"]["content"]["application/json"]["example"]["error"] == "GATEWAY_INDISPONIVEL"
    # todo endpoint protegido documenta 401
    for path, ops in spec["paths"].items():
        for met, o in ops.items():
            if "security" in o:
                assert "401" in o["responses"], (met, path)


def test_painel_de_testes_na_raiz(client):
    r = client.get("/")
    assert r.status_code == 200 and "text/html" in r.headers["content-type"]
    assert "Painel de testes" in r.text and "/docs" in r.text
    assert "/" not in {p for p in client.get("/openapi.json").json()["paths"]}  # não polui a documentação da API
