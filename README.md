# Pantheon na Mão

App do dono da Clínica Pantheon: financeiro (conta Itaú), operacional (produção, atendimentos, ranking de médicos e radiologistas), KPI (atendimentos, faturamento, pacientes, AMHPDF e satisfação), glosas AMHP e estoque — num só lugar, instalável no celular.

## Como os dados ficam protegidos
O GitHub Pages é público, então os números **não** ficam abertos no repositório: o arquivo `data.enc.json` é criptografado (AES-256) e só abre com o PIN. Quem abrir o link sem o PIN não vê nada.

**Nunca suba o `dados.json` (aberto) para o GitHub** — só o `data.enc.json`.

## Publicar no GitHub Pages
1. Repositório: `Recepcao-Convenio/pantheonapp` → https://recepcao-convenio.github.io/pantheonapp/
2. Em *Settings → Pages*, escolha *Deploy from a branch*, branch `main`, pasta `/ (root)`.

## Instalar no celular
- **iPhone (Safari):** abrir o link → Compartilhar → *Adicionar à Tela de Início*.
- **Android (Chrome):** abrir o link → menu ⋮ → *Instalar app*.

## Como os dados se atualizam
- **KPI:** lido ao vivo do site `faturamento-pantheon.github.io/kpipantheon` toda vez que o app abre (se o site não responder, usa a última cópia salva).
- **KPI → Satisfação:** lida ao vivo da planilha do formulário.
- **Estoque:** lido ao vivo (somente leitura) do Controle de Estoque (`estoque-pantheon`, documento `pantheon/estoque`).
- **Operacional e Glosas:** uma tarefa agendada diária lê a versão mais recente dos relatórios (Pantheon Analytics e Glosas Pantheon), roda `tools/atualizar.py` e publica um novo `data.enc.json` só quando algum número mudou.
- **Financeiro:** vem do *Relatório Financeiro Premium Pantheon* (PDF). A cada mês novo, rode o `tools/atualizar.py` com `--financeiro-pdf` apontando para o PDF do mês: ele acrescenta o mês sem apagar os anteriores e confere o extrato analítico contra as tabelas do relatório antes de publicar.

Para rodar a atualização à mão:
`python3 tools/atualizar.py --pin PIN --glosas glosas.html --analytics analytics.html --kpi kpi.html [--financeiro-pdf Relatorio_Financeiro_Premium_Pantheon_Mes.pdf]`

## Trocar o PIN
Rode o passo 2 acima com o PIN novo e publique o `data.enc.json`.


Ao mudar o `index.html`, troque `VERSAO` no `sw.js` (ex.: `pantheon-v2`) para os celulares atualizarem.

## Satisfação
Na primeira vez a aba pede a chave de acesso do painel de satisfação (fica salva no aparelho).
