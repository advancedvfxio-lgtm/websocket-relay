# Publicar o Relay no Render Free

Esta pasta tem **tudo** o que o Render precisa — nada mais, nada menos.
São 7 arquivos e nenhum deles é o app (o app fica no projeto, não sobe pra nuvem).

| Arquivo | Serve para |
|---|---|
| `relay_server.py` | o relay. É a única coisa que roda na nuvem |
| `requirements.txt` | só `websockets` — é o que o Render instala |
| `Procfile` | diz ao Render como iniciar |
| `render.yaml` | blueprint: o Render preenche tudo sozinho |
| `.gitignore` | evita subir lixo (`__pycache__`, logs) |
| `testar_relay.py` | confere se o relay subiu, do seu PC |
| `publicar.bat` | faz `git init` + `commit` + `push` pra você |

---

## Passo A — Criar o repositório no GitHub

1. https://github.com/new
2. **Repository name:** `remote-relay`
3. Marque **Public** ou **Private** (tanto faz, o Render lê os dois)
4. ⚠️ **NÃO marque** "Add a README file", nem .gitignore, nem license.
   O repositório tem que nascer **vazio**.
5. **Create repository** → copie a URL que aparece
   (`https://github.com/SEU-USUARIO/remote-relay.git`)

---

## Passo B — Subir os arquivos

**Opção 1 (automática):** dê dois cliques em `publicar.bat`, cole a URL do
repositório e aperte Enter. Ele faz o resto e avisa se algo falhar.
Se aparecer uma janela pedindo login do GitHub, entre normalmente — é o Git.

**Opção 2 (eu faço):** me mande a URL do repositório e eu faço o
`git init` + `commit` + `push` por aqui. Você não digita nada.

**Opção 3 (manual):** no GitHub, em *Add file → Upload files*, arraste os 7
arquivos desta pasta (sem a pasta em si) e clique em *Commit changes*.

---

## Passo C — Deploy no Render

1. https://dashboard.render.com → **New** → **Web Service**
2. **Connect a repository** → escolha o `remote-relay` que você criou
3. Preencha exatamente assim:

| Campo | Valor |
|---|---|
| **Name** | `remote-relay` (ou o que quiser) |
| **Language / Runtime** | `Python 3` |
| **Region** | a mais perto (Ohio ou Oregon) |
| **Branch** | `main` |
| **Build Command** | `pip install -r requirements.txt` |
| **Start Command** | `python relay_server.py` |
| **Instance Type** | **Free** |
| **Health Check Path** | `/health` |

4. Desça até **Environment Variables** → **Add Environment Variable**:

| Key | Value |
|---|---|
| `RELAY_KEY` | uma senha sua (ex.: 24 caracteres aleatórios) |
| `PYTHON_VERSION` | `3.13.7` |

5. **Create Web Service**. O primeiro deploy leva ~2 minutos.
6. Quando aparecer **Live**, copie a URL no topo da página:
   `https://remote-relay-xxxx.onrender.com`

> ⚠️ **Se o build falhar:** o motivo quase sempre é o `requirements.txt` errado.
> O desta pasta tem **só** `websockets`. O da raiz do projeto tem `pystray` e
> `pynput`, que dependem de X11 e **não instalam no Linux**.

---

## Passo D — Conferir que subiu

No seu PC:

```bash
C:\Python314\python.exe testar_relay.py https://remote-relay-xxxx.onrender.com
```

Ou simplesmente abra a URL no navegador: tem que aparecer
**"Remote Relay online."**

Se o `testar_relay.py` disser `server_online: false`, é porque o
`RemoteServer.exe` ainda não está rodando ou o `config.json` dele está sem a URL.

---

## Passo E — Apontar os exes (o passo que faz funcionar)

Crie um arquivo `config.json` **na pasta do exe** (`dist/`), igual para os dois:

```json
{
  "relay_host": "remote-relay-xxxx.onrender.com",
  "relay_key": "a-mesma-senha-que-voce-pôs-no-RELAY_KEY",
  "auto_connect": false,
  "reconnect_max_seconds": 30,
  "keepalive_seconds": 600
}
```

- **`relay_host`**: só o host. Sem `wss://`, sem `/ws/server` — o programa
  completa sozinho.
- **`relay_key`**: tem que ser **idêntica** à do Render. Se errar, o relay recusa
  a conexão (código 1008).
- **`auto_connect`**: `true` faz o cliente conectar sozinho ao abrir.
- **`keepalive_seconds`**: só o servidor usa. **Não passe de 720 (12 min)** — o
  Render derruba com 15 min sem tráfego. 600 (10 min) é o recomendado.

Feche e reabra os dois exes. No cliente, o campo **Host** já vem preenchido.

---

## Problemas comuns

| Sintoma | Causa |
|---|---|
| Build falhou no Render | apontou para o `requirements.txt` da raiz |
| Cliente diz "chave inválida" | `relay_key` diferente do `RELAY_KEY` |
| Primeira conexão demora ~40s | Render acordando da hibernação. O auto-reconnect resolve sozinho |
| "server_online: false" | `RemoteServer.exe` fechado ou sem a URL no `config.json` |
| Relay dorme e cai | normal no Free após ~15 min sem tráfego; o keep-alive + auto-reconnect cuidam disso |

**Limite do plano Free:** 750 h/mês. Um serviço ligado 24/7 consome ~730 h —
cabe, mas só dá para **um** serviço Free na conta.

**Segurança:** a URL é pública. Quem descobrir pode controlar o PC. É para isso
que existe a `RELAY_KEY` — não deixe vazia em host público.
