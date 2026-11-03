#!/usr/bin/env python3
"""
Busca o calendário público de contribuições de um usuário do GitHub, de todos
os anos desde a criação da conta, e grava data/contributions.json com os dias,
um resumo (total, sequências, melhor dia) e a data em que a conta foi criada.

Lê o mesmo trecho de HTML que a página do perfil carrega
(https://github.com/users/<usuario>/contributions), então não precisa de token.
Cada célula do calendário traz a data e o nível que o próprio GitHub calculou
(0 a 4); o número de contribuições vem do tooltip ligado à célula.

Só usa a biblioteca padrão do Python.

    GRAFICO_USUARIO=eFeXx-fX python scripts/contribuicoes.py
"""
import datetime
import json
import os
import re
import sys
import urllib.request
from html.parser import HTMLParser

AQUI = os.path.dirname(os.path.abspath(__file__))
USUARIO = os.environ.get("GRAFICO_USUARIO", "eFeXx-fX")
ENDERECO = "https://github.com/users/{usuario}/contributions"
SAIDA = os.environ.get("GRAFICO_DADOS", os.path.join(AQUI, "..", "data", "contributions.json"))
QUANTIDADE = re.compile(r"^\s*(No|\d[\d,]*)\s+contributions?\b", re.I)


class _Calendario(HTMLParser):
    def __init__(self):
        super().__init__()
        self.celulas = {}   # id -> {"date", "level"}
        self.dicas = {}     # id -> texto do tooltip
        self._dica = None
        self._partes = []

    def handle_starttag(self, nome, atributos):
        a = dict(atributos)
        if nome == "td" and "data-date" in a:
            self.celulas[a.get("id", a["data-date"])] = {
                "date": a["data-date"], "level": int(a.get("data-level", 0) or 0)}
        elif nome == "tool-tip" and a.get("for"):
            self._dica, self._partes = a["for"], []

    def handle_data(self, dado):
        if self._dica:
            self._partes.append(dado)

    def handle_endtag(self, nome):
        if nome == "tool-tip" and self._dica:
            self.dicas[self._dica] = "".join(self._partes).strip()
            self._dica = None


def buscar_entrada(usuario, tempo_limite=30):
    """Data em que a conta foi criada, no formato AAAA-MM-DD, e o ano."""
    pedido = urllib.request.Request(
        f"https://api.github.com/users/{usuario}",
        headers={
            "User-Agent": "efexx-perfil (+https://github.com/eFeXx-fX)",
            "Accept": "application/vnd.github+json",
        })
    with urllib.request.urlopen(pedido, timeout=tempo_limite) as resposta:
        info = json.load(resposta)
    data = info["created_at"][:10]
    return {"data": data, "ano": int(data[:4])}


def buscar(usuario, inicio=None, fim=None, tempo_limite=30):
    endereco = ENDERECO.format(usuario=usuario)
    if inicio and fim:
        endereco += f"?from={inicio}&to={fim}"
    pedido = urllib.request.Request(endereco, headers={
        "User-Agent": "efexx-perfil (+https://github.com/eFeXx-fX)", "Accept": "text/html"})
    with urllib.request.urlopen(pedido, timeout=tempo_limite) as resposta:
        html = resposta.read().decode("utf-8", "replace")
    cal = _Calendario()
    cal.feed(html)
    dias = []
    for id_celula, celula in cal.celulas.items():
        achado = QUANTIDADE.match(cal.dicas.get(id_celula, ""))
        if achado:
            n = 0 if achado.group(1).lower() == "no" else int(achado.group(1).replace(",", ""))
        else:
            n = celula["level"]  # sem tooltip: o nível é o melhor que se sabe
        if inicio and fim and not inicio <= celula["date"] <= fim:
            continue
        dias.append({"date": celula["date"], "count": n, "level": celula["level"]})
    dias.sort(key=lambda d: d["date"])
    if inicio and fim:
        esperado = (datetime.date.fromisoformat(fim) - datetime.date.fromisoformat(inicio)).days + 1
        if len(dias) < max(7, int(esperado * 0.9)):
            raise RuntimeError(f"esperava {esperado} dias entre {inicio} e {fim}, vieram {len(dias)}")
    elif len(dias) < 300:
        raise RuntimeError(f"esperava um ano inteiro de dias do GitHub, vieram {len(dias)}")
    return dias


def buscar_historico(usuario, entrada):
    """Todos os dias desde a criação da conta até hoje, um ano por pedido."""
    hoje = datetime.date.today()
    por_data = {}
    for ano in range(int(entrada["ano"]), hoje.year + 1):
        ini = datetime.date(ano, 1, 1)
        fim = datetime.date(ano, 12, 31)
        if ini < datetime.date.fromisoformat(entrada["data"]):
            ini = datetime.date.fromisoformat(entrada["data"])
        if fim > hoje:
            fim = hoje
        if ini > fim:
            continue
        for dia in buscar(usuario, ini.isoformat(), fim.isoformat()):
            por_data[dia["date"]] = dia
    dias = [por_data[k] for k in sorted(por_data)]
    if len(dias) < 300:
        raise RuntimeError(f"esperava o histórico desde {entrada['data']}, vieram {len(dias)} dias")
    return dias


def resumo(dias):
    total = sum(d["count"] for d in dias)
    maior = seguidos = 0
    for d in dias:
        seguidos = seguidos + 1 if d["count"] else 0
        maior = max(maior, seguidos)
    atual = 0
    # o dia de hoje ainda pode estar vazio sem quebrar a sequência
    cauda = dias[:-1] if dias and not dias[-1]["count"] else dias
    for d in reversed(cauda):
        if not d["count"]:
            break
        atual += 1
    melhor = max(dias, key=lambda d: d["count"])
    return {"total": total, "atual": atual, "maior": maior,
            "melhor": melhor["count"], "melhor_data": melhor["date"],
            "inicio": dias[0]["date"], "fim": dias[-1]["date"]}


def main():
    entrada = buscar_entrada(USUARIO)
    dias = buscar_historico(USUARIO, entrada)
    dados = {"usuario": USUARIO,
             "gerado_em": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
             "entrada": entrada,
             "resumo": resumo(dias), "dias": dias}
    os.makedirs(os.path.dirname(SAIDA), exist_ok=True)
    with open(SAIDA, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False)
    r = dados["resumo"]
    print(f"gerado {os.path.normpath(SAIDA)}: {r['total']} contribuições desde {entrada['ano']}, "
          f"sequência atual {r['atual']}, maior {r['maior']}")


if __name__ == "__main__":
    try:
        main()
    except Exception as erro:  # mensagem curta no log do Actions
        print(f"erro ao buscar as contribuições: {erro}", file=sys.stderr)
        sys.exit(1)
