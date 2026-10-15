# Pantheon na Mão

App do dono da Clínica Pantheon: financeiro (conta Itaú), operacional (produção, atendimentos, ranking de médicos e radiologistas), KPI (atendimentos, faturamento, pacientes, AMHPDF e satisfação), glosas AMHP e estoque — num só lugar, instalável no celular.

## Como os dados ficam protegidos
O GitHub Pages é público, então os números **não** ficam abertos no repositório: o arquivo `data.enc.json` é criptografado (AES-256) e só abre com o PIN. Quem abrir o link sem o PIN não vê nada.

**Nunca suba o `dados.json` (aberto) para o GitHub** — só o `data.enc.json`.

## Publicar no GitHub Pages
1. Crie um repositório (ex.: `pantheonnamao`) e envie todos os arquivos desta pasta.
2. Em *Settings → Pages*, escolha *Deploy from a branch*, branch `main`, pasta `/ (root)`.
3. O app fica em `https://SEU-USUARIO.github.io/pantheonnamao/`.

## Instalar no celular
- **iPhone (Safari):** abrir o link → Compartilhar → *Adicionar à Tela de Início*.
- **Android (Chrome):** abrir o link → menu ⋮ → *Instalar app*.

## Atualizar os números todo mês
1. Atualize o `dados.json` (o Claude faz isso a partir dos novos relatórios).
2. Rode: `python3 tools/montar_dados.py caminho/dados.json PIN`
3. Envie o novo `data.enc.json` para o GitHub. O app pega a versão nova ao abrir.

## Trocar o PIN
Rode o passo 2 acima com o PIN novo e publique o `data.enc.json`.

## Estoque
No `index.html`, bloco `ESTOQUE` no início do script: cole o `firebaseConfig` do sistema de estoque e o nome da coleção. A aba passa a ler o estoque ao vivo (produtos abaixo do mínimo, vencimentos e lista completa).

Ao mudar o `index.html`, troque `VERSAO` no `sw.js` (ex.: `pantheon-v2`) para os celulares atualizarem.

## KPI e satisfação
Os números do KPI vêm do site `faturamento-pantheon.github.io/kpipantheon` e são atualizados junto com os outros dados.
A aba Satisfação lê as avaliações ao vivo da mesma planilha do KPI e pede a mesma chave de acesso na primeira vez (fica salva no aparelho).
