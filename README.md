# EasyDeploy Dashboard

Dashboard local para gerenciar serviços no Easypanel — deploy com um clique, gerenciamento de domínios, criação de serviços via GitHub ou Docker.

## Pré-requisitos

- Easypanel rodando e acessível
- Token de API gerado no Easypanel: **Settings → Users → Generate API Token**
- Docker instalado (para rodar dentro do próprio Easypanel)

---

## Deploy no Easypanel (recomendado)

### 1. Suba o código para um repositório GitHub

```bash
git init
git add .
git commit -m "init easydeploy"
git remote add origin https://github.com/SEU_USUARIO/easydeploy.git
git push -u origin main
```

### 2. No Easypanel, crie um novo serviço

- **Project:** tools (ou qualquer nome)
- **Service:** easydeploy
- **Source:** GitHub → seu repositório → branch `main`
- **Port:** 8000

### 3. Configure as variáveis de ambiente no serviço

```
EASYPANEL_URL=https://painel.seudominio.com
EASYPANEL_TOKEN=seu_token_aqui
```

> Se o dashboard roda dentro do Easypanel no mesmo servidor, use:
> `EASYPANEL_URL=http://easypanel:3000`

### 4. Faça o deploy e adicione um domínio

Acesse pelo domínio configurado ou pela URL gerada pelo Easypanel.

---

## Rodar localmente (desenvolvimento)

```bash
cp .env.example .env
# edite o .env com sua URL e token

pip install -r requirements.txt
uvicorn backend.main:app --reload --port 8000
```

Acesse: http://localhost:8000

---

## Estrutura do projeto

```
easydeploy/
├── backend/
│   └── main.py          # FastAPI — consome a API do Easypanel
├── frontend/
│   └── templates/
│       └── index.html   # Dashboard HTML + JS (sem build step)
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── .env.example
```

---

## Funcionalidades

- **Listagem de serviços** com status em tempo real (rodando / parado / erro)
- **Deploy com um clique** — dispara `app.deployService` via API
- **Criar serviço** — via GitHub (com auto-deploy ativado) ou imagem Docker
- **Adicionar domínio** — configura domínio + HTTPS automaticamente
- **Parar / Iniciar / Reiniciar** serviços
- **Deletar serviço** (com confirmação)
- **Log de ações** — histórico do que foi feito pelo dashboard
- **Sincronização automática** a cada 60 segundos
- **Busca e filtro** por status

---

## Segurança

- O token fica apenas em variável de ambiente no servidor (nunca exposto no frontend)
- Todas as chamadas à API do Easypanel são feitas pelo backend Python
- O dashboard não precisa de autenticação própria pois roda em ambiente controlado
- Se quiser expor externamente, adicione autenticação HTTP Basic via Nginx

---

## Obtendo o token do Easypanel

**Via interface:**
Settings → Users → clique no usuário → Generate API Token

**Via API (token de sessão temporário):**
```bash
curl -X POST https://SEU_PAINEL:3000/api/trpc/auth.login \
  -H "Content-Type: application/json" \
  -d '{"json":{"email":"seu@email.com","password":"sua-senha"}}'
```
A resposta retorna `"token":"xxx"` — use esse valor no `.env`.

Para token permanente, após autenticar use: `users.generateApiToken`
