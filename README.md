# Pantheon na Mão

App do dono da Clínica Pantheon: financeiro (conta Itaú), operacional (produção, atendimentos, ranking de médicos e radiologistas), KPI (atendimentos, faturamento, pacientes, AMHPDF e satisfação), glosas AMHP e estoque — num só lugar, instalável no celular.

## Como os dados ficam protegidos
O GitHub Pages é público, então os números **não** ficam abertos no repositório: o arquivo `data.enc.json` é criptografado (AES-256) e só abre com o PIN. Quem abrir o link sem o PIN não vê nada.

**Nunca suba o `dados.json` (aberto) para o GitHub** — só o `data.enc.json`.

## Publicar no GitHub Pages
1. Repositório: `Recepcao-Convenio/pantheonapp` → https://recepcao-convenio.github.io/pantheonapp/
2. Em *Settings → Pages*, escolha *Deploy from a branch*, branch `main`, pasta `/ (root)`.
3. O app fica em `https://SEU-USUARIO.github.io/pantheonnamao/`.

## Instalar no celular
- **iPhone (Safari):** abrir o link → Compartilhar → *Adicionar à Tela de Início*.
- **Android (Chrome):** abrir o link → menu ⋮ → *Instalar app*.

## Como os dados se atualizam
- **KPI:** lido ao vivo do site `faturamento-pantheon.github.io/kpipantheon` toda vez que o app abre (se o site não responder, usa a última cópia salva).
- **KPI → Satisfação:** lida ao vivo da planilha do formulário.
- **Estoque:** lido ao vivo (somente leitura) do Controle de Estoque (`estoque-pantheon`, documento `pantheon/estoque`).
- **Financeiro, Operacional e Glosas:** uma tarefa agendada diária lê a versão mais recente dos relatórios (Financeiro Pantheon de cada mês, Pantheon Analytics e Glosas Pantheon), roda `tools/atualizar.py` e publica um novo `data.enc.json` só quando algum número mudou.

Para rodar a atualização à mão:
`python3 tools/atualizar.py --pin PIN --glosas glosas.html --analytics analytics.html --financeiro fin_set.html [fin_out.html ...] --kpi kpi.html`

## Trocar o PIN
Rode o passo 2 acima com o PIN novo e publique o `data.enc.json`.


Ao mudar o `index.html`, troque `VERSAO` no `sw.js` (ex.: `pantheon-v2`) para os celulares atualizarem.

## Satisfação
Na primeira vez a aba pede a chave de acesso do painel de satisfação (fica salva no aparelho).
