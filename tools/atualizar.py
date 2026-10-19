#!/usr/bin/env python3
"""
Pantheon na Mão — atualiza os dados do app a partir dos relatórios.

Lê os arquivos HTML dos relatórios (artefatos do Claude), remonta os dados
do app e grava um novo data.enc.json SOMENTE se algum número mudou.

Uso:
  python3 tools/atualizar.py --pin PIN \
      --glosas glosas.html \
      --analytics analytics.html \
      [--financeiro-pdf Relatorio_Financeiro_Premium_Pantheon_<mês>.pdf ...] \
      [--kpi kpipantheon_index.html]

Financeiro: vem do "Relatório Financeiro Premium Pantheon" (PDF). Os meses já
publicados são mantidos; um PDF novo acrescenta (ou substitui) só os meses dele.
Sem --financeiro-pdf, o Financeiro publicado fica como está.

Saída (última linha): "SEM MUDANCAS" ou "ATUALIZADO: <o que mudou>".
Regras fixas: só dados da Pantheon (nada da Lótus by Pantheon) e sem Bee Lab.
Requer: pip install cryptography
"""
import argparse
import base64
import datetime as dt
import json
import os
import re
import sys

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

RAIZ = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
ENC = os.path.join(RAIZ, "data.enc.json")
ITER = 310_000
MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho",
         "agosto", "setembro", "outubro", "novembro", "dezembro"]


def ler(caminho):
    with open(caminho, encoding="utf8") as f:
        return f.read()


def obj_js(h, marcador):
    """Lê o objeto/array JSON que vem logo depois de `marcador` no HTML."""
    i = h.find(marcador)
    if i < 0:
        raise ValueError(f"não achei {marcador!r}")
    i += len(marcador)
    while h[i] in " \t\n=":
        i += 1
    valor, _ = json.JSONDecoder().raw_decode(h, i)
    return valor


# ---------------- Operacional (Pantheon Analytics, relatório 41) ----------------
def operacional(h):
    m = re.search(r'<script type="application/json" id="data">(.*?)</script>', h, re.S)
    d = json.loads(m.group(1))
    base = dt.date(2026, 1, 1)
    nt = len(d["tipos"])
    # linha: [dia, tipo, serviço, médico solicitante, paciente, valor*100, dup, agente/radiologista, convênio]
    R = [(r[0], (base + dt.timedelta(r[0])).month - 1, r[1], r[3], r[4], r[5] / 100, r[7]) for r in d["rows"]]
    nm = max(x[1] for x in R) + 1

    def agg(rr):
        return dict(v=round(sum(x[5] for x in rr), 2), n=len(rr), pac=len({x[4] for x in rr}),
                    at=len({(x[4], x[0]) for x in rr}),
                    tipo=[round(sum(x[5] for x in rr if x[2] == t), 2) for t in range(nt)])

    months = []
    for m_ in range(nm):
        rr = [x for x in R if x[1] == m_]
        a = agg(rr)
        a["dias"] = len({x[0] for x in rr})
        months.append(a)

    medicos = []
    for i, nome in enumerate(d["medicos"]):
        if i == d["none"]:
            continue
        rr = [x for x in R if x[3] == i]
        if not rr:
            continue
        mm = []
        for m_ in range(nm):
            q = [x for x in rr if x[1] == m_]
            mm.append([round(sum(x[5] for x in q), 2), len({x[4] for x in q}), len({x[0] for x in q})])
        medicos.append(dict(nome=nome, rad=i in d["rad"], m=mm))

    radiologia = []
    for i in d["rad"]:
        rr = [x for x in R if x[6] == i]
        mm = []
        for m_ in range(nm):
            q = [x for x in rr if x[1] == m_]
            mm.append([round(sum(x[5] for x in q), 2), len({x[4] for x in q}), len({x[0] for x in q}), len(q)])
        radiologia.append(dict(nome=d["medicos"][i], m=mm))

    dias = [x[0] for x in R]
    return dict(tipos=d["tipos"], months=months, ytd=agg(R), nPacAno=d["nPac"], medicos=medicos,
                radiologia=radiologia,
                periodo=[str(base + dt.timedelta(min(dias))), str(base + dt.timedelta(max(dias)))],
                medNaoQuit=dict(n=d["meta"]["medNaoQuitN"], v=d["meta"]["medNaoQuitPg"]))


# ---------------- Glosas AMHP (somente Pantheon) ----------------
def glosas(h):
    D = obj_js(h, "const DATA=")
    out = []
    for k, v in D.items():
        if v.get("annual") or v.get("clinic") or k.startswith("l"):  # Lótus fica de fora
            continue
        T, I = v["D"]["tot"], v["D"]["items"]
        pend = [x for x in I if x[10] == "P"]
        out.append(dict(k=k, label=v["label"], cobrado=round(T["c"], 2), glosado=round(T["g"], 2),
                        repasse=round(T["r"], 2), guias=T["guias"], guiasG=T["guiasG"],
                        pendGuias=len({x[0] for x in pend}), pendValor=round(sum(x[8] for x in pend), 2)))
    return out


# ---------------- Financeiro (relatório da conta Itaú, um arquivo por mês) ----------------
def financeiro_mes(h):
    d = obj_js(h, "const DATA = ")
    d.pop("lotus_in", None)  # transferências da Lótus não entram
    per = re.search(r"(\d{2})/(\d{2})/(\d{4})\s*a\s*(\d{2}/\d{2}/\d{4})", h)
    if not per:
        raise ValueError("período não encontrado no relatório financeiro")
    d["ym"] = f"{per.group(3)}-{per.group(2)}"
    d["periodo"] = per.group(0).replace("  ", " ")
    d["mes"] = f"{MESES[int(per.group(2)) - 1].capitalize()}/{per.group(3)}"
    return d


# ---------------- KPI (cópia de reserva; o app lê o site ao vivo) ----------------
def kpi(h, anterior):
    s = h[h.find("const MONTHS"):]

    def lit(nome):
        m = re.search(r"const\s+" + nome + r"\s*=\s*", s)
        if not m:
            return None
        i = j = m.end()
        prof = 0
        while True:
            c = s[j]
            if c in "[{":
                prof += 1
            elif c in "]}":
                prof -= 1
                if prof == 0:
                    break
            j += 1
        t = s[i:j + 1]
        t = re.sub(r"([{,]\s*)([A-Za-zÀ-ÿ_][\wÀ-ÿ]*)\s*:", r'\1"\2":', t)
        t = re.sub(r",\s*([}\]])", r"\1", t)
        return json.loads(t)

    k = {n: lit(n) for n in ["MONTHS", "services", "atendimentos", "valores", "faturamento", "amhpdf", "pacientes"]}
    if not k["valores"]:
        k.pop("valores")
    cs = re.search(r'CSAT_URL\s*=\s*"([^"]+)"', h)
    k["csatUrl"] = cs.group(1) if cs else (anterior or {}).get("csatUrl")
    return k


# ---------------- Criptografia ----------------
def chave(pin, salt):
    return PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=ITER).derive(pin.encode())


def abrir_atual(pin):
    if not os.path.exists(ENC):
        return None
    e = json.load(open(ENC))
    b = base64.b64decode
    raw = AESGCM(chave(pin, b(e["salt"]))).decrypt(b(e["iv"]), b(e["ct"]), None)
    return json.loads(raw)


def gravar(dados, pin):
    raw = json.dumps(dados, ensure_ascii=False, separators=(",", ":")).encode("utf8")
    salt, iv = os.urandom(16), os.urandom(12)
    ct = AESGCM(chave(pin, salt)).encrypt(iv, raw, None)
    b64 = lambda x: base64.b64encode(x).decode()
    with open(ENC, "w") as f:
        json.dump({"v": 1, "iter": ITER, "n": len(pin), "salt": b64(salt), "iv": b64(iv), "ct": b64(ct),
                   "atualizado": dados["atualizado"]}, f)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pin", required=True)
    ap.add_argument("--glosas", required=True)
    ap.add_argument("--analytics", required=True)
    ap.add_argument("--financeiro-pdf", nargs="+", dest="financeiro_pdf")
    ap.add_argument("--financeiro", nargs="+",
                    help="(antigo) relatórios HTML do Financeiro — ignorados quando o app já usa o relatório Premium")
    ap.add_argument("--kpi")
    a = ap.parse_args()

    atual = abrir_atual(a.pin)  # falha aqui = PIN errado; nada é gravado
    novo = dict(atualizado=dt.date.today().isoformat())

    fin_atual = (atual or {}).get("financeiro") or []
    premium = any(m.get("fonte") == "Relatório Financeiro Premium" for m in fin_atual)
    if a.financeiro_pdf:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import financeiro_pdf
        fins = {m["ym"]: m for m in fin_atual if m.get("fonte") == "Relatório Financeiro Premium"}
        for m in financeiro_pdf.ler_varios(a.financeiro_pdf):
            fins[m["ym"]] = m
        novo["financeiro"] = [fins[k] for k in sorted(fins)]
    elif a.financeiro and not premium:
        fins = {}
        for f in a.financeiro:
            m = financeiro_mes(ler(f))
            fins[m["ym"]] = m
        novo["financeiro"] = [fins[k] for k in sorted(fins)]
    else:
        if a.financeiro:
            print("aviso: Financeiro já usa o Relatório Premium — relatórios HTML antigos ignorados")
        novo["financeiro"] = fin_atual
    novo["operacional"] = operacional(ler(a.analytics))
    novo["glosas"] = glosas(ler(a.glosas))
    novo["kpi"] = kpi(ler(a.kpi), (atual or {}).get("kpi")) if a.kpi else (atual or {}).get("kpi")

    # Trava de segurança: nunca publicar nada da Lótus nem do Bee Lab
    txt = json.dumps(novo, ensure_ascii=False).lower()
    if re.search(r"l[oó]tus|bee ?lab", txt):
        sys.exit("ERRO: dados da Lótus/Bee Lab encontrados — nada foi gravado.")

    mudou = []
    for sec in ["financeiro", "operacional", "glosas", "kpi"]:
        if not atual or atual.get(sec) != novo.get(sec):
            mudou.append(sec)
    if not mudou:
        print("SEM MUDANCAS")
        return
    gravar(novo, a.pin)
    resumo = []
    if "financeiro" in mudou:
        resumo.append("financeiro: " + ", ".join(m["mes"] for m in novo["financeiro"]))
    if "operacional" in mudou:
        resumo.append("operacional até " + novo["operacional"]["periodo"][1])
    if "glosas" in mudou:
        resumo.append("glosas até " + novo["glosas"][-1]["label"])
    if "kpi" in mudou:
        resumo.append("kpi até " + novo["kpi"]["MONTHS"][-1])
    print("ATUALIZADO: " + "; ".join(resumo))


if __name__ == "__main__":
    main()
