"""
relay_server.py -- Broker Relay WebSocket do Remote Control App.

Roda em qualquer host que aceite um servico Python (Render, Railway, Fly.io)
ou na propria maquina, ao lado do RemoteServer.exe (modo local / Cloudflare
Tunnel). Os dois lados (servidor e cliente) fazem conexao de SAIDA para ca:
ninguem precisa abrir porta no roteador.

Endpoints:
    /ws/server[?key=SENHA]   -> vaga do RemoteServer
    /ws/client[?key=SENHA]   -> vaga do RemoteClient
    /health                  -> 200 + JSON (health check do Render / browser)
    /                        -> pagina de status em texto

Variaveis de ambiente:
    PORT        porta de escuta (o Render injeta automaticamente)
    RELAY_KEY   senha obrigatoria. Vazio = relay aberto (use so no localhost).
"""

import asyncio
import json
import logging
import os
import time

try:
    import websockets
except ImportError:
    import subprocess
    import sys

    subprocess.check_call([sys.executable, "-m", "pip", "install", "websockets"])
    import websockets

from websockets.datastructures import Headers
from websockets.http11 import Response

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

PORT = int(os.environ.get("PORT", 8765))
RELAY_KEY = os.environ.get("RELAY_KEY", "").strip()

# max_size=None: um frame de tela ou um arquivo enviado pelo gerenciador de
# arquivos passa facil de 1 MB -- o limite padrao da lib (1 MB) derrubava a
# conexao no meio de uma transferencia grande.
MAX_MSG = None

STARTED_AT = time.time()
_stats = {"server": 0, "client": 0}

# DIAGNOSTICO: conta toda requisicao HTTP que CHEGA no app, inclusive os
# upgrades WebSocket (process_request e chamado antes do handshake).
#   - se "/ws/server" aparecer em /health -> o edge do Render entregou a conexao
#   - se nunca aparecer -> o edge esta engolindo o upgrade antes de chegar aqui
_rotas = {}

# DIAGNOSTICO 2: guarda os cabecalhos da ultima requisicao nao-health (o
# upgrade WebSocket). Se o handler nao roda mas o process_request roda, a
# diferenca esta nos cabecalhos que o proxy do Render manda.
_ultimo_req = {}

_server_ws = None
_client_ws = None
_lock = asyncio.Lock()


def _split_path(path):
    """Separa caminho e query sem depender da versao da lib."""
    path = str(path or "")
    if "?" in path:
        base, query = path.split("?", 1)
    else:
        base, query = path, ""
    params = {}
    for part in query.split("&"):
        if "=" in part:
            k, v = part.split("=", 1)
            params[k] = v
    return base, params


def _path_of(websocket):
    req = getattr(websocket, "request", None)
    raw = (
        getattr(req, "path", None)
        or getattr(websocket, "path", None)
        or getattr(websocket, "request_path", None)
        or getattr(websocket, "uri", None)
        or ""
    )
    return _split_path(raw)[0]


def _key_of(websocket):
    req = getattr(websocket, "request", None)
    raw = (
        getattr(req, "path", None)
        or getattr(websocket, "path", None)
        or getattr(websocket, "request_path", None)
        or getattr(websocket, "uri", None)
        or ""
    )
    return _split_path(raw)[1].get("key", "")


def process_request(connection, request):
    """Responde HTTP puro em /health e / -- o upgrade WebSocket segue normal."""
    path = _split_path(getattr(request, "path", ""))[0]

    # Diagnostico: registra a rota e faz barulho quando nao for health check.
    _rotas[path] = _rotas.get(path, 0) + 1
    if path not in ("/health", "/healthz"):
        try:
            _ultimo_req[path] = {
                "headers": {str(k): str(v) for k, v in dict(getattr(request, "headers", {}) or {}).items()},
                "tem_upgrade": "upgrade" in str(getattr(request, "headers", {}) or "").lower(),
                "websockets": websockets.__version__,
            }
        except Exception as e:
            _ultimo_req[path] = {"erro": repr(e)}
        logging.info(f"Requisicao vista pelo app: {path} | {_ultimo_req[path]}")

    if path in ("/health", "/healthz"):
        body = json.dumps({
            "status": "ok",
            "uptime_s": round(time.time() - STARTED_AT, 1),
            "server_online": _server_ws is not None,
            "client_online": _client_ws is not None,
            "conexoes": _stats,
            "rotas": dict(_rotas),
            "ultimo_req": _ultimo_req,
        }).encode("utf-8")
        return Response(200, "OK", Headers({
            "Content-Type": "application/json",
            "Content-Length": str(len(body)),
            "Cache-Control": "no-store",
        }), body)
    if path in ("/", ""):
        body = (
            "Remote Relay online.\n"
            f"uptime: {round(time.time() - STARTED_AT)}s\n"
            f"servidor conectado: {_server_ws is not None}\n"
            f"cliente conectado: {_client_ws is not None}\n"
            "websocket: /ws/server | /ws/client\n"
        ).encode("utf-8")
        return Response(200, "OK", Headers({
            "Content-Type": "text/plain; charset=utf-8",
            "Content-Length": str(len(body)),
        }), body)
    return None


async def handler(websocket):
    global _server_ws, _client_ws

    path = _path_of(websocket)
    logging.info(
        f"handler() CHAMADO -- path={path!r} | chave {'presente' if _key_of(websocket) else 'AUSENTE'}"
    )
    if RELAY_KEY and _key_of(websocket) != RELAY_KEY:
        logging.warning(f"Recusado (chave invalida): {websocket.remote_address}")
        await websocket.close(code=1008, reason="chave invalida")
        return

    is_server = "server" in path
    logging.info(f"Nova conexao WebSocket: {websocket.remote_address} | Path: {path}")

    async with _lock:
        if is_server:
            if _server_ws and _server_ws != websocket:
                try:
                    await _server_ws.close()
                except Exception:
                    pass
            _server_ws = websocket
            _stats["server"] += 1
            logging.info("--> Servidor Remoto (RemoteServer) registrado e pronto.")
        else:
            if _client_ws and _client_ws != websocket:
                try:
                    await _client_ws.close()
                except Exception:
                    pass
            _client_ws = websocket
            _stats["client"] += 1
            logging.info("--> Cliente (RemoteClient) registrado e conectado.")

    try:
        async for message in websocket:
            async with _lock:
                target = _client_ws if is_server else _server_ws

            if target:
                try:
                    await target.send(message)
                except Exception as ex:
                    logging.warning(f"Erro ao encaminhar mensagem: {ex}")
            else:
                if not is_server:
                    logging.warning("Cliente enviou mensagem, mas o RemoteServer nao esta conectado ao Relay.")
                else:
                    logging.warning("Servidor enviou mensagem, mas o RemoteClient nao esta conectado ao Relay.")
    except websockets.exceptions.ConnectionClosed:
        logging.info(f"Conexao encerrada: {'RemoteServer' if is_server else 'RemoteClient'}")
    except Exception:
        logging.exception("Erro inesperado no handler")
    finally:
        async with _lock:
            if is_server and _server_ws == websocket:
                _server_ws = None
                logging.info("RemoteServer desconectado.")
            elif not is_server and _client_ws == websocket:
                _client_ws = None
                logging.info("RemoteClient desconectado.")


async def main():
    logging.info(f"Iniciando Broker Relay WebSocket na porta {PORT}...")
    if not RELAY_KEY:
        logging.warning("RELAY_KEY vazio: o relay esta ABERTO. Em host publico, defina RELAY_KEY.")
    # compression=None: o trafego ja e JPEG (nao comprime) -- deflate so gastaria
    # CPU e atrasaria o frame.
    async with websockets.serve(
        handler, "0.0.0.0", PORT,
        max_size=MAX_MSG,
        compression=None,
        ping_interval=20,
        ping_timeout=20,
        process_request=process_request,
    ):
        await asyncio.Future()  # roda para sempre


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Broker Relay encerrado.")
