r"""
testar_relay.py -- Confere se o relay publicado esta no ar.

So usa a biblioteca padrao (urllib), entao roda em qualquer Python sem instalar
nada. Nao mexe no seu mouse/teclado e nao atrapalha quem ja esta conectado.

Uso:
    python testar_relay.py https://seu-relay.onrender.com
    python testar_relay.py seu-relay.onrender.com
    python testar_relay.py https://seu-relay.onrender.com --ws

--ws  faz tambem um teste real de WebSocket (abre a vaga de cliente por um
      instante). Se o RemoteClient estiver conectado, ele cai e reconecta
      sozinho -- nao use durante uma sessao importante.
"""

import json
import sys
import urllib.request


def normaliza(alvo):
    alvo = (alvo or "").strip().rstrip("/")
    if not alvo:
        return None
    if "://" not in alvo:
        alvo = "https://" + alvo
    alvo = alvo.replace("wss://", "https://").replace("ws://", "http://")
    return alvo.split("/ws/")[0]


def checar_health(base):
    url = base + "/health"
    print(f"[1] GET {url}")
    try:
        with urllib.request.urlopen(url, timeout=45) as r:
            corpo = r.read().decode("utf-8", errors="replace")
            print(f"    HTTP {r.status}")
            try:
                dados = json.loads(corpo)
                print(f"    {json.dumps(dados, indent=2, ensure_ascii=False)}")
                return dados
            except Exception:
                print(f"    corpo: {corpo[:200]}")
                return None
    except Exception as e:
        print(f"    FALHOU: {type(e).__name__}: {e}")
        print("    - o servico existe? a URL esta certa?")
        print("    - se acabou de acordar, espere 60s e tente de novo")
        return None


def checar_ws(base):
    url = base.replace("https://", "wss://").replace("http://", "ws://") + "/ws/client"
    print(f"\n[2] Teste real de WebSocket em {url}")
    try:
        from websockets.sync.client import connect
    except ImportError:
        print("    pulado: modulo 'websockets' nao instalado neste Python")
        return None
    try:
        with connect(url, open_timeout=45, max_size=None, compression=None) as ws:
            print("    conectou e o relay aceitou (a vaga de cliente esta livre)")
            return True
    except Exception as e:
        print(f"    FALHOU: {type(e).__name__}: {e}")
        print("    - se for 'chave invalida' (1008): falta o RELAY_KEY no relay")
        return False


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1

    base = normaliza(sys.argv[1])
    if not base:
        print("URL vazia.")
        return 1

    print("=" * 60)
    print(f"Relay: {base}")
    print("=" * 60)

    dados = checar_health(base)
    if dados is None:
        return 1

    if "--ws" in sys.argv:
        checar_ws(base)

    print("\n" + "=" * 60)
    if dados.get("server_online"):
        print("SERVIDOR conectado. Tudo pronto para usar o cliente.")
    else:
        print("Relay OK, mas o RemoteServer NAO esta conectado.")
        print("Abra o RemoteServer.exe e confira o config.json dele.")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
