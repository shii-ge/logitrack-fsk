# LogiTrack

Projeto Flask + Tailwind CSS (via CDN) integrado ao schema `controle_acesso.sql`
(tabelas `funcionario`, `leitor`, `registros` + trigger de entrada/saída
automática). Reflete o wireframe: página inicial com atalhos e o painel
"Em progresso", página de Operadores com aprovação/exclusão de cadastros
pendentes, página de Leitores e página de Registros com o histórico completo.

## Estrutura

```
logitrack/
├── app.py            # rotas Flask e consultas ao MySQL
├── config.py          # credenciais de conexão (usa variáveis de ambiente)
├── schema.sql          # schema fornecido (funcionario, leitor, registros, trigger)
├── requirements.txt
└── templates/
    ├── base.html        # layout com Tailwind e navegação
    ├── index.html        # página inicial ("Em progresso")
    ├── operadores.html    # tabela funcionario, com aprovar/excluir
    ├── leitores.html       # tabela leitor, com aprovar/excluir
    └── registros.html      # histórico completo (JOIN funcionario + leitor)
```

## Como o schema funciona

- `funcionario`: cadastro de pessoas (id, nome, uid, pendente).
- `leitor`: dispositivos leitores de tag (id, nome, pendente).
- `registros`: cada leitura de tag em um leitor (uid, funcionario_id, leitor_id,
  timestamp, status).
- O **trigger `trg_registros_before_insert`** roda antes de cada INSERT em
  `registros` e faz tudo automaticamente:
  1. Se o `uid` lido não tiver `funcionario` cadastrado, cria um novo
     funcionário com nome placeholder (`Pendente - <uid>`) e `pendente = TRUE`.
  2. Se o `leitor_id` enviado não existir, cria um `leitor` placeholder
     também com `pendente = TRUE`.
  3. Calcula o `status` (entrada/saída) alternando com base na última leitura
     daquele `uid` naquele `leitor` — a aplicação **não precisa enviar**
     `funcionario_id` nem `status` ao inserir um registro, apenas `uid` e
     `leitor_id` (e opcionalmente `timestamp`).

Ou seja, a app Flask nunca insere diretamente em `registros` (isso é feito
pelos dispositivos leitores/firmware chamando o INSERT simples). O papel da
app é: mostrar quem está com acesso em progresso, e permitir que um
administrador aprove ou exclua os cadastros pendentes de funcionário/leitor.

## Como rodar

1. Crie o banco e as tabelas:
   ```bash
   mysql -u root -p < schema.sql
   ```

2. Instale as dependências (idealmente em um virtualenv):
   ```bash
   pip install -r requirements.txt
   ```

3. Configure a conexão com variáveis de ambiente (ou edite `config.py`):
   ```bash
   export DB_HOST=localhost
   export DB_USER=root
   export DB_PASSWORD=sua_senha
   export DB_NAME=controle_acesso
   ```

4. Execute a aplicação:
   ```bash
   python app.py
   ```

5. Acesse http://localhost:5000

## Páginas

- **Início** — para cada leitor, lista os funcionários cujo último registro
  naquele leitor tem `status = TRUE` (entrada ainda sem saída correspondente).
- **Operadores** — lista `funcionario`. Linhas pendentes aparecem destacadas
  em amarelo. Ícone de lápis (verde) abre um modal para editar nome/UID —
  salvar também tira o registro do estado `pendente`. Ícone de lixeira
  (vermelho) abre um modal de confirmação antes de excluir o funcionário.
- **Leitores** — mesma lógica de edição/exclusão via modal, para a tabela
  `leitor` (apenas o campo nome é editável).
- **Registros** — histórico completo de `registros`, com nome do funcionário
  e do leitor já resolvidos via JOIN, e selo "entrada"/"saída" conforme o
  campo `status`.

## Simulando uma leitura (para teste)

Como a app não insere em `registros`, simule uma leitura de tag diretamente
no MySQL para ver o trigger e as páginas funcionando:

```sql
INSERT INTO registros (uid, leitor_id) VALUES ('04 A1 B2 3C', 1);
```
