#!/usr/bin/env python3
"""
Desenha data/contributions.json (gerado por contribuicoes.py) como o gráfico
de contribuições do perfil, em SVG, dentro de uma janela no estilo Omarchy:
borda fina colorida, sem barra de título e prompt do starship no topo.

Semanas são colunas e dias são linhas, como no GitHub. Embaixo ficam a
legenda (Menos, Mais) e o resumo com datas no formato brasileiro. Na versão
animada, as semanas aparecem da esquerda para a direita uma vez só.

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


def desenhar(dados):
    t, dias, r = TEMA, dados["dias"], dados["resumo"]
    primeiro = datetime.date.fromisoformat(dias[0]["date"])
    antes = (primeiro.weekday() + 1) % 7        # semana começa no domingo, como no GitHub
    semanas = (antes + len(dias) + 6) // 7
    x0 = MARGEM + ROTULOS_X
    largura = x0 + semanas * PASSO + MARGEM
    base_grade = TOPO_GRADE + 7 * PASSO
    altura = base_grade + 112
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{largura}" height="{altura}" '
           f'viewBox="0 0 {largura} {altura}" font-family="{FONTE}" role="img">',
           tag("title", "Gráfico de contribuições no GitHub no último ano"),
           tag("rect", width=largura, height=altura, fill=t["fundo"]),
           tag("rect", x=BORDA / 2, y=BORDA / 2, width=largura - BORDA, height=altura - BORDA,
               fill="none", stroke=t["borda_ativa"], stroke_width=BORDA)]

    # prompt no estilo starship
    out.append(f'<text x="{MARGEM}" y="26" font-size="12.5" xml:space="preserve">'
               f'<tspan fill="{t["prompt"]}" font-weight="700">~/contribuicoes \u276f</tspan>'
               f'<tspan fill="{t["texto"]}"> contribuicoes --ultimo-ano</tspan></text>')

    # meses em cima e dias da semana à esquerda
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
        dica = f'{data_br(d["date"])}: {n} contribuiç{"ão" if n == 1 else "ões"}'
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
               f'<tspan fill="{t["apagado"]}"> contribuições no último ano</tspan></text>')
    out.append(tag("text", f'{data_br(r["inicio"])} a {data_br(r["fim"])}', x=largura - MARGEM, y=y1,
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
