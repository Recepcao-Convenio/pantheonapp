#!/usr/bin/env python3
"""
Pantheon na Mão — lê o "Relatório Financeiro Premium Pantheon" (PDF) e devolve os
dados do Financeiro do app, um registro por mês.

Uso (normalmente chamado pelo tools/atualizar.py --financeiro-pdf ...):
  python3 tools/financeiro_pdf.py relatorio.pdf [outro.pdf ...]   -> imprime um resumo

Fonte da verdade = as tabelas do relatório (entradas e saídas por categoria, receita
real da Associação). O anexo (extrato analítico) é usado para o detalhe: maiores
pagamentos por categoria, quinzenas e tickets médios. O leitor confere se o anexo
fecha com as tabelas, centavo a centavo, e para com erro se não fechar.

Regra fixa (definida pela Anna): todo valor recebido da Clínica Lótus é reembolso da
parte dela em custos divididos (ex.: medicação da STIN), não receita. Ele sai das
entradas e é abatido de "Fornecedores de Produtos e Insumos Médicos" no mesmo mês —
direto da linha da STIN quando ela foi paga no mesmo dia; os demais numa linha
"(−) Reembolso de custo dividido". O resultado
operacional não muda. O nome da Lótus nunca vai para os dados do app.

Requer o programa pdftotext (pacote poppler-utils).
"""
import re
import subprocess
import sys
from collections import defaultdict

MES_ABR = {"Jan": 1, "Fev": 2, "Mar": 3, "Abr": 4, "Mai": 5, "Jun": 6, "Jul": 7,
           "Ago": 8, "Set": 9, "Out": 10, "Nov": 11, "Dez": 12}
MESES = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto",
         "Setembro", "Outubro", "Novembro", "Dezembro"]

ENTRADAS = ["Recebimento de Convênio/Associação Médica", "Recebimento de Pacientes – Cartão (Débito/Crédito)",
            "Recebimento de Pacientes – PIX", "Entrada Lucas (Neuron)", "Outras Entradas Operacionais"]
SAIDAS = ["Repasse a Médicos e Prestadores (PF)", "Retirada Lucas (Neuron)",
          "Fornecedores de Produtos e Insumos Médicos", "Funcionários",
          "Softwares, Marketing e Taxas de Pagamento", "Contas Fixas", "Impostos e Tributos",
          "Serviços Administrativos, Contábeis e Seguros", "Concessionárias (Água/Luz/Telefone/Internet)",
          "Tarifas e Encargos Bancários", "Despesas Operacionais Diversas"]
EXCLUIDAS = ["Aplicação Financeira", "Transferências Excluídas", "Empréstimos, Financiamentos e Cartão Corporativo"]

RE_VAL = r"-?R\$\s*[\d.]+,\d{2}"
RE_LINHA = re.compile(r"^\s*(\d{2})/(\d{2})/(\d{4})\s+([A-Z][a-z]{2})/(\d{2})\s+(.*?)\s*(" + RE_VAL + r")\s*$")


def num(s):
    s = s.replace("R$", "").replace(" ", "")
    neg = s.startswith("-")
    v = float(s.lstrip("-").replace(".", "").replace(",", "."))
    return -v if neg else v


def texto(pdf):
    return subprocess.run(["pdftotext", "-layout", pdf, "-"], capture_output=True, text=True, check=True).stdout


def ruido(l):
    s = l.strip()
    return (not s or s.startswith("Relatório Financeiro Premium") or s.startswith("Data ")
            or "lançamento(s)" in s or s.startswith("ANEXO") or s.startswith("Extrato analítico")
            or s in ("(categoria)", "(entrada)"))


def nome_cat(txt, lista):
    t = " ".join(txt.split())
    for c in sorted(lista, key=len, reverse=True):
        if t.startswith(c) or c.startswith(t[:max(12, len(t))]):
            return c
    for c in lista:
        if t[:20] and c.startswith(t[:20]):
            return c
    return None


# ---------------- tabelas ----------------
def tabela_meses(txt, titulo, cats, meses_cols):
    """Lê a tabela 'Categoria  Mês1  Mês2 ...  [Total]  %' depois do título."""
    i = txt.index(titulo)
    fim = re.compile(r"^\s*Total\s+-?R\$.*$", re.M).search(txt, i)
    bloco = txt[i:fim.end()]
    linhas = bloco.splitlines()
    out = {}
    pend = ""
    for l in linhas:
        vals = re.findall(RE_VAL, l)
        rot = re.split(r"\s{2,}-?R\$", l)[0].strip()
        if rot.startswith("Total"):
            out["__total__"] = [abs(num(v)) for v in vals[:len(meses_cols)]]
            break
        if len(vals) >= len(meses_cols):
            nome = (pend + " " + rot).strip() if pend else rot
            pend = ""
            c = nome_cat(nome, cats)
            if c is None:
                # nome quebrado em duas linhas: a 2ª parte vem depois
                c = nome
            out[c] = [abs(num(v)) for v in vals[:len(meses_cols)]]
            ultimo = c
        elif rot and not rot.startswith("Categoria") and out:
            # continuação do nome da categoria anterior (quebra de linha)
            if ultimo in out and ultimo not in cats:
                novo = nome_cat(ultimo + " " + rot, cats)
                if novo:
                    out[novo] = out.pop(ultimo)
                    ultimo = novo
    faltam = [c for c in out if c != "__total__" and c not in cats]
    if faltam:
        raise ValueError(f"categoria não reconhecida em '{titulo}': {faltam}")
    return out


def meses_do_relatorio(txt):
    cab = re.search(r"Categoria\s+((?:[A-Z][a-zçã]+/\d{2}\s+)+)", txt[txt.index("ANÁLISE DETALHADA DE SAÍDAS"):])
    cols = re.findall(r"([A-Z][a-zçã]+)/(\d{2})", cab.group(1))
    out = []
    for m, a in cols:
        k = m[:3]
        if k == "Mar" and m.startswith("Mar"):
            k = "Mar"
        out.append((2000 + int(a), MES_ABR[k]))
    return out


# ---------------- anexo ----------------
def anexo_saidas(txt):
    a = txt.index("ANEXO — EXTRATO DE SAÍDAS")
    b = txt.index("ANEXO — EXTRATO DE ENTRADAS")
    linhas = txt[a:b].splitlines()
    rows, cat = [], None
    for idx, l in enumerate(linhas):
        if "lançamento(s)" in l:
            # nome da categoria: na mesma linha ou na seguinte
            cand = re.split(r"\s{2,}\d+ lançamento", l)[0].strip()
            if not cand:
                for k in range(idx + 1, min(idx + 4, len(linhas))):
                    if linhas[k].strip():
                        cand = re.split(r"\s{2,}[\d.]+,\d{2}", linhas[k])[0].strip()
                        break
            cat = nome_cat(cand, SAIDAS) or next((e for e in EXCLUIDAS if cand.startswith(e)), cand)
            continue
        m = RE_LINHA.match(l)
        if not m:
            continue
        desc = m.group(6).strip()
        if not desc:  # descrição quebrada: está nas linhas vizinhas
            viz = []
            for k in (idx - 1, idx + 1):
                if 0 <= k < len(linhas) and not ruido(linhas[k]) and not RE_LINHA.match(linhas[k]):
                    viz.append(linhas[k].strip())
            desc = " ".join(viz)
        rows.append(dict(dia=int(m.group(1)), mes=int(m.group(2)), ano=int(m.group(3)),
                         desc=" ".join(desc.split()), valor=abs(num(m.group(7))), cat=cat))
    return rows


def anexo_entradas(txt):
    a = txt.index("ANEXO — EXTRATO DE ENTRADAS")
    linhas = txt[a:].splitlines()
    rows = []
    for idx, l in enumerate(linhas):
        m = RE_LINHA.match(l)
        if not m:
            continue
        resto = m.group(6)
        # linhas vizinhas que não são outro lançamento (categoria/descrição quebradas)
        viz = [x.strip() for k, x in ((k, linhas[k]) for k in (idx - 1, idx + 1) if 0 <= k < len(linhas))
               if not RE_LINHA.match(x) and not ruido(x)]
        cat = None
        for alvo in (resto, " ".join([resto] + viz)):
            if "Cartão" in alvo:
                cat = ENTRADAS[1]
            elif "Pacientes – PIX" in alvo:
                cat = ENTRADAS[2]
            elif "Entrada Lucas" in alvo:
                cat = ENTRADAS[3]
            elif "Outras Entradas" in alvo:
                cat = ENTRADAS[4]
            elif "Aplicação Financeira" in alvo or "Empréstimos" in alvo or "Transferências Excluídas" in alvo:
                cat = "excluida"
            elif "Convênio/Associação" in alvo or ("Recebimento de" in alvo and "ASSOCIACAO" in alvo):
                cat = ENTRADAS[0]
            if cat:
                break
        if not cat:
            cat = "?" + " ".join([resto] + viz)
        parceira = bool(re.search(r"L[OÓ]TUS", " ".join([resto] + viz), re.I))
        # sinal preservado: devolução de PIX vem negativa e abate a categoria
        rows.append(dict(dia=int(m.group(1)), mes=int(m.group(2)), ano=int(m.group(3)),
                         valor=num(m.group(7)), cat=cat, parceira=parceira))
    return rows


# ---------------- montagem ----------------
def ler(pdf):
    txt = texto(pdf)
    meses = meses_do_relatorio(txt)
    n = len(meses)
    sai_tab = tabela_meses(txt, "ANÁLISE DETALHADA DE SAÍDAS", SAIDAS, meses)
    ent_tab = tabela_meses(txt, "ANÁLISE DETALHADA DE ENTRADAS", ENTRADAS, meses)

    # Receita real da Associação por mês
    amh = {}
    i = txt.index("RECEITA REAL DA ASSOCIAÇÃO")
    sec = txt[i:txt.index("EM RESUMO", i)]
    if n == 1:
        br = num(re.search(r"Recebido da Associação.*?(" + RE_VAL + ")", sec).group(1))
        lq = num(re.search(r"= Receita real.*?(" + RE_VAL + ")", sec).group(1))
        amh[meses[0]] = dict(bruto=abs(br), liquido=abs(lq))
    else:
        for (ano, mes) in meses:
            ab = [k for k, v in MES_ABR.items() if v == mes][0]
            m = re.search(rf"^\s*{ab}/{str(ano)[2:]}\s+(" + RE_VAL + r")\s+(" + RE_VAL + r")\s+(" + RE_VAL + ")", sec, re.M)
            amh[(ano, mes)] = dict(bruto=abs(num(m.group(1))), liquido=abs(num(m.group(3))))

    saidas = anexo_saidas(txt)
    entradas = anexo_entradas(txt)
    desconhecidas = {r["cat"] for r in entradas if r["cat"].startswith("?")}
    if desconhecidas:
        raise ValueError(f"categoria de entrada não reconhecida no anexo: {desconhecidas}")

    out = []
    for j, (ano, mes) in enumerate(meses):
        S = [r for r in saidas if (r["ano"], r["mes"]) == (ano, mes)]
        E = [r for r in entradas if (r["ano"], r["mes"]) == (ano, mes)]
        # --- conferência do anexo contra as tabelas ---
        for c in SAIDAS:
            t = sai_tab.get(c, [0] * n)[j]
            a = round(sum(r["valor"] for r in S if r["cat"] == c), 2)
            if abs(a - t) > 0.01:
                raise ValueError(f"{MESES[mes-1]}/{ano}: anexo de saídas não fecha em '{c}' ({a} x {t})")
        for c in ENTRADAS[1:]:
            t = ent_tab.get(c, [0] * n)[j]
            a = round(sum(r["valor"] for r in E if r["cat"] == c), 2)
            if abs(a - t) > 0.01:
                raise ValueError(f"{MESES[mes-1]}/{ano}: anexo de entradas não fecha em '{c}' ({a} x {t})")

        # repasses da Associação (estão no anexo de saídas como "Transferências Excluídas")
        rep = [r for r in S if r["cat"] == "Transferências Excluídas"]
        gero = round(sum(r["valor"] for r in rep if "GEROMASTER" in r["desc"].upper()), 2)
        seg = round(sum(r["valor"] for r in rep if "PANTHEON" in r["desc"].upper()), 2)
        ab = amh[(ano, mes)]
        if abs(ab["bruto"] - gero - seg - ab["liquido"]) > 0.01:
            raise ValueError(f"{MESES[mes-1]}/{ano}: repasses da Associação não fecham "
                             f"({ab['bruto']} - {gero} - {seg} != {ab['liquido']})")

        # --- reembolsos da clínica parceira: saem das entradas e abatem Fornecedores ---
        FORN = "Fornecedores de Produtos e Insumos Médicos"
        reemb = [r for r in E if r["parceira"] and r["cat"] in ENTRADAS]
        abat_ent = defaultdict(float)
        abat_forn = defaultdict(float)   # descrição do fornecedor (ou None) -> valor
        for r in reemb:
            abat_ent[r["cat"]] += r["valor"]
            # só a STIN tem vínculo confirmado (parte da Lótus na medicação comprada junto)
            mesmo_dia = [x for x in S if x["cat"] == FORN and x["dia"] == r["dia"] and x["valor"] >= r["valor"]
                         and "STIN" in x["desc"].upper()]
            alvo = max(mesmo_dia, key=lambda x: x["valor"])["desc"] if mesmo_dia else None
            abat_forn[alvo] += r["valor"]
        total_reemb = round(sum(abat_ent.values()), 2)
        if total_reemb > sai_tab.get(FORN, [0] * n)[j] + 0.01:
            raise ValueError(f"{MESES[mes-1]}/{ano}: reembolso da clínica parceira maior que o gasto com fornecedores")
        E = [r for r in E if not (r["parceira"] and r["cat"] in ENTRADAS)]

        ent = {c: round(ent_tab.get(c, [0] * n)[j] - abat_ent.get(c, 0), 2) for c in ENTRADAS}
        ent_total = round(sum(ent.values()), 2)
        cats = []
        for c in SAIDAS:
            v = sai_tab.get(c, [0] * n)[j]
            if c == FORN:
                v = round(v - total_reemb, 2)
            if v <= 0:
                continue
            por = defaultdict(lambda: [0.0, 0])
            for r in S:
                if r["cat"] == c:
                    por[r["desc"] or "—"][0] += r["valor"]
                    por[r["desc"] or "—"][1] += 1
            if c == FORN:
                for alvo, val in abat_forn.items():
                    if alvo and alvo in por:
                        por[alvo][0] -= val
                    else:
                        por["(−) Reembolso de custo dividido"][0] -= val
            det = sorted(([k, round(x[0], 2)] for k, x in por.items() if abs(x[0]) > 0.004), key=lambda z: -z[1])
            positivos = [d for d in det if d[1] > 0][:8] + [d for d in det if d[1] < 0]
            cats.append(dict(nome=c, valor=v, n=sum(1 for r in S if r["cat"] == c), pag=len(por), det=positivos))
        cats.sort(key=lambda z: -z["valor"])
        tot_out = round(sum(c["valor"] for c in cats), 2)
        if (abs(tot_out + total_reemb - sai_tab["__total__"][j]) > 0.01
                or abs(ent_total + total_reemb - ent_tab["__total__"][j]) > 0.01):
            raise ValueError(f"{MESES[mes-1]}/{ano}: totais não batem com o relatório")

        # quinzenas (Associação entra pelo líquido: TED na data, repasses descontados na data)
        def quinz(f):
            e = sum(r["valor"] for r in E if f(r["dia"]) and r["cat"] in ENTRADAS)
            e -= sum(r["valor"] for r in rep if f(r["dia"]) and ("GEROMASTER" in r["desc"].upper() or "PANTHEON" in r["desc"].upper()))
            s = sum(r["valor"] for r in S if f(r["dia"]) and r["cat"] in SAIDAS)
            s -= sum(r["valor"] for r in reemb if f(r["dia"]))
            return round(e, 2), round(s, 2)
        q1, q2 = quinz(lambda d: d <= 15), quinz(lambda d: d > 15)
        quinzenas = [dict(quinzena="1ª quinzena (01 a 15)", entradas=q1[0], saidas=q1[1], resultado=round(q1[0] - q1[1], 2)),
                     dict(quinzena=f"2ª quinzena (16 a {max([r['dia'] for r in S + E] or [30])})", entradas=q2[0], saidas=q2[1], resultado=round(q2[0] - q2[1], 2))]
        if abs(q1[0] + q2[0] - ent_total) > 0.05 or abs(q1[1] + q2[1] - tot_out) > 0.05:
            raise ValueError(f"{MESES[mes-1]}/{ano}: quinzenas não fecham com as entradas ({q1[0]+q2[0]} x {ent_total})")

        pix = [r["valor"] for r in E if r["cat"] == ENTRADAS[2]]
        car = [r["valor"] for r in E if r["cat"] == ENTRADAS[1]]
        # ticket médio: valor líquido (com devoluções) ÷ nº de recebimentos (sem contar devoluções)
        ultimo = max([r["dia"] for r in S + E] or [30])
        out.append(dict(
            ym=f"{ano}-{mes:02d}", mes=f"{MESES[mes-1]}/{ano}",
            periodo=f"01/{mes:02d}/{ano} a {ultimo:02d}/{mes:02d}/{ano}",
            entradas=ent, ent_total=ent_total, cats=cats, tot_out=tot_out,
            resultado=round(ent_total - tot_out, 2),
            amhpdf=dict(bruto=ab["bruto"], gero=gero, segunda=seg, liquido=ab["liquido"]),
            quinzenas=quinzenas,
            ticket=dict(pix=dict(n=sum(1 for v in pix if v > 0), v=round(sum(pix), 2)),
                        cartao=dict(n=sum(1 for v in car if v > 0), v=round(sum(car), 2))),
            reembolso_parceira=total_reemb,
            fonte="Relatório Financeiro Premium",
        ))
    return out


def ler_varios(pdfs):
    meses = {}
    for p in pdfs:
        for m in ler(p):
            meses[m["ym"]] = m  # relatório mais novo na lista substitui o mesmo mês
    return [meses[k] for k in sorted(meses)]


if __name__ == "__main__":
    for m in ler_varios(sys.argv[1:]):
        print(f"{m['mes']}: entradas {m['ent_total']:,.2f} | saídas {m['tot_out']:,.2f} | resultado {m['resultado']:,.2f} "
              f"| AMHPDF {m['amhpdf']} | PIX {m['ticket']['pix']} | cartão {m['ticket']['cartao']}")
        for q in m["quinzenas"]:
            print("   ", q)
