import os
import json
import urllib.request
import urllib.error
import ssl
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs

# --- Carrega .env manualmente ---
def load_env():
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())

load_env()

PROXMOX_HOST     = os.environ["PROXMOX_HOST"]
PROXMOX_NODE     = os.environ["PROXMOX_NODE"]
PROXMOX_TOKEN_ID = os.environ["PROXMOX_TOKEN_ID"]
PROXMOX_TOKEN_SECRET = os.environ["PROXMOX_TOKEN_SECRET"]
PANEL_PORT       = int(os.environ.get("PANEL_PORT", 8080))
SECRET_KEY       = os.environ["PANEL_SECRET_KEY"]

BASE_URL = f"https://{PROXMOX_HOST}:8006/api2/json"
AUTH_HEADER = f"PVEAPIToken={PROXMOX_TOKEN_ID}={PROXMOX_TOKEN_SECRET}"
SSL_CTX = ssl._create_unverified_context()  # Proxmox usa cert self-signed por padrão

BASE_DIR = os.path.dirname(__file__)

# --- Helpers Proxmox API ---
def proxmox_request(path, method="GET", data=None):
    url = f"{BASE_URL}{path}"
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, method=method)
    req.add_header("Authorization", AUTH_HEADER)
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, context=SSL_CTX, timeout=5) as resp:
        return json.loads(resp.read())["data"]

def get_vms():
    vms = proxmox_request(f"/nodes/{PROXMOX_NODE}/qemu")
    cts = proxmox_request(f"/nodes/{PROXMOX_NODE}/lxc")
    result = []
    for vm in vms:
        result.append({"vmid": vm["vmid"], "name": vm.get("name", f"vm-{vm['vmid']}"), "type": "qemu", "status": vm["status"]})
    for ct in cts:
        result.append({"vmid": ct["vmid"], "name": ct.get("name", f"ct-{ct['vmid']}"), "type": "lxc", "status": ct["status"]})
    return sorted(result, key=lambda x: x["vmid"])

def vm_action(vmid, vmtype, action):
    # action: "start" ou "stop"
    proxmox_request(f"/nodes/{PROXMOX_NODE}/{vmtype}/{vmid}/status/{action}", method="POST")

# --- Handler HTTP ---
class Handler(BaseHTTPRequestHandler):

    def log_message(self, format, *args):
        print(f"{self.address_string()} - {format % args}")

    def send_json(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", len(body))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urlparse(self.path)
        qs = parse_qs(parsed.query)
        key = qs.get("key", [None])[0]

        # Serve o HTML
        if parsed.path in ("/", "/index.html"):
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            with open(os.path.join(BASE_DIR, "index.html"), "rb") as f:
                self.wfile.write(f.read())
            return

        # Valida token em todas as rotas de API
        if key != SECRET_KEY:
            self.send_json(403, {"error": "Forbidden"})
            return

        # Lista VMs
        if parsed.path == "/api/vms":
            try:
                self.send_json(200, get_vms())
            except Exception as e:
                self.send_json(500, {"error": str(e)})
            return

        # Desliga o host
        if parsed.path == "/api/shutdown-host":
            self.send_json(200, {"ok": True})
            os.system("/sbin/shutdown -h now")
            return

        self.send_response(404)
        self.end_headers()

    def do_POST(self):
        parsed = urlparse(self.path)
        qs = parse_qs(parsed.query)
        key = qs.get("key", [None])[0]

        if key != SECRET_KEY:
            self.send_json(403, {"error": "Forbidden"})
            return

        # /api/vm/<vmid>/<type>/start|stop
        parts = parsed.path.strip("/").split("/")
        # esperado: ["api", "vm", "<​vmid>", "<​type>", "<​action>"]
        if len(parts) == 5 and parts[0] == "api" and parts[1] == "vm":
            _, _, vmid, vmtype, action = parts
            if action not in ("start", "stop") or vmtype not in ("qemu", "lxc"):
                self.send_json(400, {"error": "Invalid"})
                return
            try:
                vm_action(vmid, vmtype, action)
                self.send_json(200, {"ok": True})
            except Exception as e:
                self.send_json(500, {"error": str(e)})
            return

        self.send_response(404)
        self.end_headers()

server = HTTPServer(("0.0.0.0", PANEL_PORT), Handler)
print(f"HomeServer Painel rodando na porta {PANEL_PORT}...")
server.serve_forever()