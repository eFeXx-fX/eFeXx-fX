#!/usr/bin/env python3
"""
Desenha data/contributions.json (gerado por contribuicoes.py) como o gráfico
de contribuições do perfil, em SVG, dentro de uma janela no estilo Omarchy:
borda fina colorida, sem barra de título e prompt do starship no topo.

Semanas são colunas e dias são linhas, como no GitHub, mas cada mês junta
o mesmo dia de todos os anos (o janeiro da grade é a soma de todos os
janeiros). Embaixo ficam a legenda (Menos, Mais) e o resumo. O canto do
prompt diz desde que ano a conta existe. Na versão animada, as semanas
aparecem da esquerda para a direita uma vez só.

As cores vêm de scripts/tema.json (gerado localmente pelo preencher.py);
sem ele, usa o tema efexx.

    python scripts/grafico.py
    STATIC=1 gera a versão parada (usada na prévia).
    GRAFICO_SAIDA=arquivo.svg muda o destino; TEMA_JSON=arquivo.json muda o tema.
"""
import datetime
import json
import os
from html import escape

AQUI = os.path.dirname(os.path.abspath(__file__))
DADOS = os.environ.get("GRAFICO_DADOS", os.path.join(AQUI, "..", "data", "contributions.json"))
SAIDA = os.environ.get("GRAFICO_SAIDA", os.path.join(AQUI, "..", "contrib-heatmap.svg"))
PARADO = bool(os.environ.get("STATIC"))

FONTE = ("'JetBrainsMono Nerd Font', 'JetBrains Mono', 'CaskaydiaMono Nerd Font', 'Cascadia Mono', "
         "ui-monospace, 'DejaVu Sans Mono', Menlo, Consolas, monospace")
MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]
DIAS_ROTULO = {1: "seg", 3: "qua", 5: "sex"}

TEMA = {  # tema efexx; scripts/tema.json, se existir, substitui
    "fundo": "#080E0A", "texto": "#c8f7d8", "apagado": "#6a6e95",
    "borda_ativa": "#39FF14", "destaque": "#39FF14", "secao": "#7cf8f7",
    "prompt": "#7cf8f7", "pendente": "#e0af68",
    "grafico": ["#0f1a13", "#0f3d1c", "#17702e", "#2bb83f", "#39FF14", "#a4ffa0"],
}
_tema = os.environ.get("TEMA_JSON", os.path.join(AQUI, "tema.json"))
if os.path.exists(_tema):
    with open(_tema, encoding="utf-8") as f:
        TEMA.update(json.load(f))
NIVEIS = TEMA["grafico"][:5]  # o GitHub usa 5 níveis (0 a 4)

QUADRO, PASSO = 11, 14          # tamanho do quadrado e distância entre eles
MARGEM, ROTULOS_X = 22, 32      # margem da janela e coluna dos dias da semana
TOPO_GRADE = 66                 # prompt + rótulos dos meses
BORDA = 2


def esc(texto):
    return escape(str(texto), quote=True)


def tag(nome, conteudo=None, **kw):
    attrs = "".join(f' {k.rstrip("_").replace("_", "-")}="{esc(v)}"' for k, v in kw.items())
    return f"<{nome}{attrs}/>" if conteudo is None else f"<{nome}{attrs}>{conteudo}</{nome}>"


def data_br(iso):
    ano, mes, dia = iso.split("-")
    return f"{dia}/{mes}/{ano}"


def plural(n):
    return "dia" if n == 1 else "dias"


def selo_desde(t, largura, ano, data_iso):
    """Caixa no canto do prompt: no GitHub desde o ano da conta."""
    largura_caixa, altura_caixa = 214, 28
    x = largura - MARGEM - largura_caixa
    y = 6
    rotulo = (
        f'<text x="{x + largura_caixa / 2:.1f}" y="{y + 19}" font-size="13" '
        f'text-anchor="middle" xml:space="preserve">'
        f'<tspan fill="{t["texto"]}">no GitHub desde </tspan>'
        f'<tspan fill="{t["destaque"]}" font-weight="700">{esc(ano)}</tspan>'
        f'</text>'
    )
    return (
        "<g>"
        + tag("title", f"Conta criada em {data_br(data_iso)}")
        + tag("rect", x=x, y=y, width=largura_caixa, height=altura_caixa, rx=4,
              fill="#0f3d1c", stroke=t["destaque"], stroke_width=1.5)
        + rotulo
        + "</g>"
    )


def _nivel(contagem, cortes):
    if contagem <= 0:
        return 0
    q1, q2, q3 = cortes
    if contagem <= q1:
        return 1
    if contagem <= q2:
        return 2
    if contagem <= q3:
        return 3
    return 4


def mesclar(dias, ano_grade):
    """Uma grade de janeiro a dezembro. Cada dia soma o mesmo dia em todos os anos.

    29 de fevereiro, num ano da grade que não é bissexto, entra no dia 28.
    """
    bissexto = (ano_grade % 4 == 0 and ano_grade % 100 != 0) or ano_grade % 400 == 0
    por_dia = {}
    for d in dias:
        data = datetime.date.fromisoformat(d["date"])
        mes, dia = data.month, data.day
        if mes == 2 and dia == 29 and not bissexto:
            dia = 28
        item = por_dia.setdefault((mes, dia), {"count": 0, "anos": set()})
        item["count"] += d["count"]
        if d["count"]:
            item["anos"].add(data.year)
    positivos = sorted(item["count"] for item in por_dia.values() if item["count"] > 0)

    def corte(fracao):
        if not positivos:
            return 0
        k = (len(positivos) - 1) * fracao
        baixo = int(k)
        alto = min(baixo + 1, len(positivos) - 1)
        return positivos[baixo] + (positivos[alto] - positivos[baixo]) * (k - baixo)

    cortes = (corte(0.25), corte(0.50), corte(0.75))
    grade = []
    dia = datetime.date(ano_grade, 1, 1)
    fim = datetime.date(ano_grade, 12, 31)
    um = datetime.timedelta(days=1)
    while dia <= fim:
        item = por_dia.get((dia.month, dia.day), {"count": 0, "anos": set()})
        grade.append({
            "date": dia.isoformat(),
            "count": item["count"],
            "level": _nivel(item["count"], cortes),
            "anos": sorted(item["anos"]),
        })
        dia += um
    return grade


def desenhar(dados):
    t, dias, r = TEMA, dados["dias"], dados["resumo"]
    entrada = dados.get("entrada") or {"data": "2022-12-25", "ano": 2022}
    ano_inicio = int(entrada["ano"])
    ano_grade = datetime.date.today().year
    dias = mesclar(dias, ano_grade)
    primeiro = datetime.date.fromisoformat(dias[0]["date"])
    antes = (primeiro.weekday() + 1) % 7        # semana começa no domingo, como no GitHub
    semanas = (antes + len(dias) + 6) // 7
    x0 = MARGEM + ROTULOS_X
    largura = x0 + semanas * PASSO + MARGEM
    base_grade = TOPO_GRADE + 7 * PASSO
    altura = base_grade + 112
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{largura}" height="{altura}" '
           f'viewBox="0 0 {largura} {altura}" font-family="{FONTE}" role="img">',
           tag("title", f"Gráfico de contribuições no GitHub desde {ano_inicio}. "
               "Cada mês junta o mesmo dia de todos os anos."),
           tag("rect", width=largura, height=altura, fill=t["fundo"]),
           tag("rect", x=BORDA / 2, y=BORDA / 2, width=largura - BORDA, height=altura - BORDA,
               fill="none", stroke=t["borda_ativa"], stroke_width=BORDA)]

    # prompt no estilo starship
    out.append(f'<text x="{MARGEM}" y="26" font-size="12.5" xml:space="preserve">'
               f'<tspan fill="{t["prompt"]}" font-weight="700">~/contribuicoes \u276f</tspan>'
               f'<tspan fill="{t["texto"]}"> contribuicoes --desde-{ano_inicio}</tspan></text>')
    out.append(selo_desde(t, largura, ano_inicio, entrada["data"]))

    # meses em cima e dias da semana à esquerda. Cada mês já reúne todos os anos.
    visto = None
    for i, d in enumerate(dias):
        data = datetime.date.fromisoformat(d["date"])
        col = (i + antes) // 7
        if data.day <= 7 and data.month != visto and col < semanas - 1:
            visto = data.month
            out.append(tag("text", MESES[data.month - 1], x=x0 + col * PASSO, y=TOPO_GRADE - 8,
                           font_size=10, fill=t["apagado"]))
    for linha, nome in DIAS_ROTULO.items():
        out.append(tag("text", nome, x=MARGEM, y=TOPO_GRADE + linha * PASSO + QUADRO - 2,
                       font_size=9.5, fill=t["apagado"]))

    # quadrados, um grupo por semana
    colunas = [[] for _ in range(semanas)]
    for i, d in enumerate(dias):
        col, linha = divmod(i + antes, 7)
        nivel = max(0, min(len(NIVEIS) - 1, int(d.get("level", 0))))
        n = d["count"]
        data = datetime.date.fromisoformat(d["date"])
        anos = d.get("anos") or []
        if len(anos) > 1:
            extra = f" em {len(anos)} anos"
        elif len(anos) == 1:
            extra = f" em {anos[0]}"
        else:
            extra = ""
        dica = f'{data.day:02d}/{data.month:02d}: {n} contribuiç{"ão" if n == 1 else "ões"}{extra}'
        colunas[col].append(tag("rect", tag("title", esc(dica)), x=x0 + col * PASSO,
                                y=TOPO_GRADE + linha * PASSO, width=QUADRO, height=QUADRO,
                                rx=1, fill=NIVEIS[nivel]))
    for col, quadros in enumerate(colunas):
        if PARADO:
            out.append("<g>" + "".join(quadros) + "</g>")
        else:
            inicio = 0.2 + col * 0.03
            out.append(f'<g opacity="0"><animate attributeName="opacity" values="0;1" '
                       f'begin="{inicio:.2f}s" dur="0.4s" fill="freeze"/>{"".join(quadros)}</g>')

    # legenda no canto direito, logo abaixo da grade
    ly = base_grade + 8
    lx = largura - MARGEM - 30 - len(NIVEIS) * PASSO
    out.append(tag("text", "Menos", x=lx - 6, y=ly + QUADRO - 2, font_size=10,
                   fill=t["apagado"], text_anchor="end"))
    for cor in NIVEIS:
        out.append(tag("rect", x=lx, y=ly, width=QUADRO, height=QUADRO, rx=1, fill=cor))
        lx += PASSO
    out.append(tag("text", "Mais", x=lx + 2, y=ly + QUADRO - 2, font_size=10, fill=t["apagado"]))

    # resumo
    sy = ly + QUADRO + 16
    out.append(tag("line", x1=BORDA, y1=sy, x2=largura - BORDA, y2=sy,
                   stroke=t["apagado"], stroke_opacity=0.35))
    total = f'{r["total"]:,}'.replace(",", ".")
    y1, y2 = sy + 26, sy + 50
    out.append(f'<text x="{MARGEM}" y="{y1}" font-size="13" xml:space="preserve">'
               f'<tspan fill="{t["destaque"]}" font-weight="700">{esc(total)}</tspan>'
               f'<tspan fill="{t["apagado"]}"> contribuições desde {ano_inicio}</tspan></text>')
    out.append(tag("text", f'{data_br(entrada["data"])} a {data_br(r["fim"])}', x=largura - MARGEM, y=y1,
                   font_size=12, fill=t["apagado"], text_anchor="end"))
    out.append(f'<text x="{MARGEM}" y="{y2}" font-size="13" fill="{t["apagado"]}" xml:space="preserve">'
               f'sequência atual <tspan fill="{t["secao"]}" font-weight="700">{r["atual"]} {plural(r["atual"])}</tspan>'
               f' · maior <tspan fill="{t["secao"]}" font-weight="700">{r["maior"]} {plural(r["maior"])}</tspan></text>')
    if r["melhor"]:
        out.append(f'<text x="{largura - MARGEM}" y="{y2}" font-size="12" fill="{t["apagado"]}" '
                   f'text-anchor="end">melhor dia <tspan fill="{t["pendente"]}" font-weight="700">'
                   f'{r["melhor"]}</tspan> em {data_br(r["melhor_data"])}</text>')
    out.append("</svg>")
    return "".join(out)


if __name__ == "__main__":
    with open(DADOS, encoding="utf-8") as f:
        svg = desenhar(json.load(f))
    with open(SAIDA, "w", encoding="utf-8") as f:
        f.write(svg)
    print(f"gerado {os.path.normpath(SAIDA)} ({len(svg)} bytes)")
