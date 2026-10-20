"""Teste de concorrência de estoque (evidência da decisão D4 – baixa atômica).

Dispara N pedidos simultâneos de 1 unidade do mesmo produto, com saldo de 5 unidades:
esperado = exatamente 5 respostas 201, as demais 409 (ESTOQUE_INSUFICIENTE) e saldo final 0.

Uso (com a API rodando e o seed aplicado):   python tests/carga_concorrencia.py [URL_BASE] [N]
"""
import collections
import concurrent.futures as cf
import json
import sys
import urllib.error
import urllib.request

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
N = int(sys.argv[2]) if len(sys.argv) > 2 else 20


def chamar(metodo, caminho, token=None, corpo=None):
    h = {"Content-Type": "application/json"}
    if token:
        h["Authorization"] = "Bearer " + token
    req = urllib.request.Request(BASE + caminho, method=metodo, headers=h,
                                 data=json.dumps(corpo).encode() if corpo is not None else None)
    try:
        r = urllib.request.urlopen(req, timeout=30)
        return r.status, json.loads(r.read() or b"null")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def login(email):
    return chamar("POST", "/auth/login", corpo={"email": email, "senha": "Senha@123"})[1]["accessToken"]


gerente, cliente = login("gerente.recife@raizes.test"), login("cliente@raizes.test")
chamar("POST", "/estoque/movimentos", gerente, {"unidadeId": 1, "produtoId": 12, "tipo": "AJUSTE", "quantidade": 5,
                                                "motivo": "Preparação do teste de concorrência"})


def pedir(_):
    return chamar("POST", "/pedidos", cliente, {"canalPedido": "APP", "unidadeId": 1,
                                                 "itens": [{"produtoId": 12, "quantidade": 1}]})[0]


with cf.ThreadPoolExecutor(N) as ex:
    resultado = collections.Counter(ex.map(pedir, range(N)))
saldo = next(i["quantidade"] for i in chamar("GET", "/unidades/1/estoque", gerente)[1] if i["produtoId"] == 12)
print(f"{N} pedidos simultâneos (saldo inicial 5): {dict(resultado)} | saldo final: {saldo}")
assert resultado.get(201) == 5 and saldo == 0 and set(resultado) <= {201, 409}, "Falha: estoque inconsistente!"
print("OK – nenhuma venda além do estoque.")
