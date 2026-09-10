from __future__ import annotations

import html
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import requests
import streamlit as st
from dotenv import load_dotenv
from streamlit_autorefresh import st_autorefresh


# ============================================================
# CONFIGURAÇÃO
# ============================================================

APP_DIR = Path(__file__).resolve().parent

# ============================================================
# ENV LOCAL DO DASHBOARD
# ============================================================
# O arquivo oficial é:
#   <pasta do dashboard_tv.py>/.env
#
# Portanto, o dashboard encontra as credenciais mesmo quando
# o BAT/CMD é aberto a partir de outro diretório.
ENV_FILE = APP_DIR / ".env"
if ENV_FILE.exists():
    load_dotenv(dotenv_path=ENV_FILE, override=True)

TZ = ZoneInfo("America/Sao_Paulo")

st.set_page_config(
    page_title="APS Serra · TV",
    page_icon="🪚",
    layout="wide",
    initial_sidebar_state="collapsed",
)

def cfg(name: str, default: str = "") -> str:
    """
    Lê a configuração nesta ordem:
    1. Streamlit Secrets (produção / Streamlit Community Cloud)
    2. Variáveis de ambiente ou arquivo .env local
    3. Valor padrão
    """
    try:
        if name in st.secrets:
            value = st.secrets[name]
            if value is not None and str(value).strip():
                return str(value).strip()
    except Exception:
        # Fora do Streamlit Cloud ou sem secrets.toml configurado.
        pass

    value = os.getenv(name)
    if value is not None and str(value).strip():
        return str(value).strip()

    return str(default or "").strip()


SUPABASE_URL = cfg("SUPABASE_URL").rstrip("/")

# Aceita os nomes usados tanto no Streamlit Secrets quanto no .env local.
# Prioriza a chave secreta, quando disponível.
SUPABASE_KEY = (
    cfg("SUPABASE_SECRET_KEY")
    or cfg("SUPABASE_ANON_KEY")
    or cfg("SUPABASE_KEY")
)

SUPABASE_KEY_SOURCE = (
    "SUPABASE_SECRET_KEY" if cfg("SUPABASE_SECRET_KEY")
    else "SUPABASE_ANON_KEY" if cfg("SUPABASE_ANON_KEY")
    else "SUPABASE_KEY" if cfg("SUPABASE_KEY")
    else ""
)

REFRESH_SECONDS = max(10, int(float(cfg("REFRESH_SECONDS", "30") or 30)))
MACHINES = [
    x.strip().upper()
    for x in cfg("APS_MACHINES", "SER-01,SER-02,SER-03,SER-04,SER-05").split(",")
    if x.strip()
][:5]

while len(MACHINES) < 5:
    code = f"SER-{len(MACHINES)+1:02d}"
    if code not in MACHINES:
        MACHINES.append(code)

DEMO_MODE = cfg("DEMO_MODE", "false").lower() in {"1", "true", "sim", "yes", "on"}

# Recarrega a página automaticamente para uso em TV.
st_autorefresh(interval=REFRESH_SECONDS * 1000, key="aps-serra-tv-refresh")


# ============================================================
# VISUAL
# ============================================================

CSS = r"""
<style>
:root {
  --bg:#061626;
  --panel:#0a2239;
  --panel2:#0d2a46;
  --line:#1d4e73;
  --line-soft:#173b59;
  --text:#f4f8fc;
  --muted:#82a9c8;
  --cyan:#42c2ff;
  --green:#28df88;
  --yellow:#ffc326;
  --red:#ff5f6d;
  --blue:#2098ff;
}

html, body, [class*="css"] {
  font-family: Inter, "Segoe UI", Arial, sans-serif;
}

.stApp {
  background:
    radial-gradient(circle at 50% -15%, rgba(32,152,255,.11), transparent 36%),
    linear-gradient(180deg,#061424 0%,#071a2d 100%);
  color:var(--text);
}

header[data-testid="stHeader"],
footer,
#MainMenu,
[data-testid="stToolbar"],
[data-testid="stDecoration"] {
  display:none !important;
}

div[data-testid="stElementContainer"]:has(iframe) {
  display:none !important;
  height:0 !important;
  min-height:0 !important;
  margin:0 !important;
  padding:0 !important;
}

.block-container {
  max-width:100% !important;
  padding:.15rem .4rem .2rem .4rem !important;
}

/* =========================================================
   CABEÇALHO
   ========================================================= */
.tv-header {
  display:grid;
  grid-template-columns:165px 1fr 170px;
  height:64px;
  align-items:center;
  border-bottom:1px solid var(--line);
  margin-bottom:5px;
}

.brand {
  font-size:24px;
  font-weight:950;
  letter-spacing:1px;
  line-height:.9;
}
.brand small {
  display:block;
  font-size:7px;
  letter-spacing:5px;
  margin-top:7px;
  color:#dcebf6;
}

.title { text-align:center; }
.title h1 {
  font-size:21px;
  line-height:1;
  padding:0;
  margin:0;
  letter-spacing:.3px;
  color:var(--cyan);
}
.title p {
  color:#76c9f8;
  margin:6px 0 0;
  font-size:8px;
  letter-spacing:1.4px;
}

.clock {
  border-left:1px solid var(--line);
  padding-left:12px;
  text-align:center;
}
.clock .date { font-size:9px; color:#8bd5ff; }
.clock .time { font-size:19px; font-weight:950; margin:2px 0; }
.clock .week { font-size:6.8px; color:#a9c4da; }

/* =========================================================
   5 FAIXAS
   ========================================================= */
.machine-grid {
  display:grid;
  grid-template-columns:1fr;
  gap:5px;
}

.saw-row {
  height:122px;
  display:grid;
  grid-template-columns:138px 395px 330px minmax(0,1fr);
  background:linear-gradient(90deg,rgba(10,34,57,.99),rgba(8,29,49,.99));
  border:1px solid var(--line);
  border-radius:9px;
  overflow:hidden;
  box-shadow:inset 0 1px 0 rgba(255,255,255,.025);
}

/* =========================================================
   SERRA / STATUS
   ========================================================= */
.saw-ident {
  padding:9px 10px;
  display:flex;
  flex-direction:column;
  justify-content:center;
  border-right:1px solid var(--line-soft);
}
.saw-name-line {
  display:flex;
  align-items:center;
  justify-content:space-between;
  gap:5px;
}
.saw-name {
  font-size:17px;
  font-weight:950;
  white-space:nowrap;
}
.saw-dot { font-size:11px; }

.status-pill {
  margin-top:8px;
  width:100%;
  box-sizing:border-box;
  text-align:center;
  border-radius:5px;
  padding:6px 3px;
  font-size:8px;
  font-weight:950;
  border:1px solid;
}
.status-run { background:rgba(40,223,136,.12);color:#43ee9b;border-color:#20d97f; }
.status-setup { background:rgba(255,195,38,.12);color:#ffd05b;border-color:#d79d08; }
.status-pause { background:rgba(32,152,255,.13);color:#72c9ff;border-color:#248dd9; }
.status-wait { background:rgba(118,154,181,.12);color:#e0edf6;border-color:#557995; }
.status-off { background:rgba(255,95,109,.11);color:#ff8b95;border-color:#f15261; }

/* =========================================================
   ITEM ATUAL + PRODUÇÃO
   ========================================================= */
.current-box {
  padding:8px 10px 7px;
  border-right:1px solid var(--line-soft);
  overflow:hidden;
}
.current-top {
  display:grid;
  grid-template-columns:1fr 58px;
  gap:8px;
}
.label {
  font-size:6.7px;
  color:#76acd2;
  text-transform:uppercase;
  letter-spacing:.45px;
}
.current-code {
  font-size:18px;
  font-weight:950;
  line-height:1;
  margin-top:2px;
  white-space:nowrap;
  overflow:hidden;
  text-overflow:ellipsis;
}
.current-desc {
  font-size:7.4px;
  line-height:1.13;
  color:#d9eaf5;
  margin-top:3px;
  height:17px;
  overflow:hidden;
}
.current-time {
  border-left:1px solid var(--line-soft);
  padding-left:7px;
}
.current-time b {
  display:block;
  font-size:10px;
  margin:1px 0 4px;
}
.origin {
  display:inline-block;
  margin-top:2px;
  font-size:6px;
  font-weight:900;
  color:var(--yellow);
}

.current-progress {
  height:4px;
  margin-top:4px;
  border-radius:5px;
  background:#173650;
  overflow:hidden;
}
.current-progress span {
  height:100%;
  display:block;
  background:linear-gradient(90deg,#26dd86,#48ef9d);
  border-radius:5px;
}
.current-progress.avulsa span {
  background:linear-gradient(90deg,#ffb816,#ffda66);
}

.current-metrics {
  display:grid;
  grid-template-columns:repeat(3,1fr);
  gap:5px;
  margin-top:5px;
}
.current-metric {
  background:rgba(13,42,70,.7);
  border:1px solid rgba(41,91,126,.45);
  border-radius:4px;
  padding:4px 6px;
  display:flex;
  align-items:baseline;
  justify-content:space-between;
  min-width:0;
}
.current-metric span {
  font-size:5.8px;
  color:#70a7cb;
}
.current-metric b {
  font-size:11px;
  font-weight:950;
}
.current-metric b.saldo { color:var(--yellow); }

/* =========================================================
   HISTÓRICO
   ========================================================= */
.history-box {
  padding:7px 8px;
  border-right:1px solid var(--line-soft);
  min-width:0;
}
.box-head {
  display:flex;
  align-items:center;
  justify-content:space-between;
  margin-bottom:5px;
}
.box-head strong {
  font-size:8px;
  color:#cbeaff;
  letter-spacing:.4px;
}
.box-head span {
  font-size:6px;
  color:#6fa7cc;
}

.history-list {
  display:grid;
  grid-template-rows:repeat(3,1fr);
  gap:4px;
}
.hist-row {
  height:24px;
  display:grid;
  grid-template-columns:42px minmax(0,1fr) 53px;
  gap:5px;
  align-items:center;
  padding:0 6px;
  background:rgba(14,45,73,.58);
  border:1px solid rgba(29,78,115,.65);
  border-radius:4px;
}
.hist-time {
  font-size:9px;
  font-weight:950;
  color:#5fc8ff;
}
.hist-code {
  font-size:8.5px;
  font-weight:900;
  white-space:nowrap;
  overflow:hidden;
  text-overflow:ellipsis;
}
.hist-qty {
  text-align:right;
  font-size:9px;
  font-weight:950;
  color:#fff;
}
.hist-empty {
  grid-column:1/-1;
  text-align:center;
  color:#6f94ae;
  font-size:7px;
}

/* =========================================================
   FILA COMPACTA
   ========================================================= */
.queue-box {
  padding:7px 8px;
  min-width:0;
}
.queue-list {
  display:grid;
  grid-template-rows:repeat(4,1fr);
  gap:3px;
}
.queue-row {
  height:18px;
  display:grid;
  grid-template-columns:14px 130px minmax(0,1fr) 48px;
  gap:4px;
  align-items:center;
  padding:0 5px;
  background:rgba(14,45,73,.55);
  border:1px solid rgba(29,78,115,.55);
  border-radius:3px;
}
.queue-pos {
  font-size:7px;
  font-weight:950;
  color:#55c8ff;
}
.queue-code {
  font-size:8px;
  font-weight:950;
  color:#fff;
  white-space:nowrap;
  overflow:hidden;
  text-overflow:ellipsis;
}
.queue-desc {
  font-size:6.8px;
  color:#b8d3e6;
  white-space:nowrap;
  overflow:hidden;
  text-overflow:ellipsis;
}
.queue-qty {
  text-align:right;
  font-size:8px;
  font-weight:950;
}
.queue-empty {
  grid-column:1/-1;
  text-align:center;
  font-size:6.7px;
  color:#6f94ae;
}

/* TVs menores */
@media (max-width:1400px) {
  .saw-row {
    grid-template-columns:132px 370px 305px minmax(0,1fr);
  }
  .current-code { font-size:16px; }
  .queue-row { grid-template-columns:12px 110px minmax(0,1fr) 44px; }
  .queue-code { font-size:7.3px; }
  .queue-desc { font-size:6.2px; }
}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)


# ============================================================
# UTILITÁRIOS
# ============================================================

def esc(value: Any) -> str:
    return html.escape(str(value if value is not None else ""))

def html_compact(value: str) -> str:
    """
    Streamlit usa um parser Markdown antes de entregar unsafe_allow_html.
    Se um HTML multilinha tiver linha em branco seguida de 4+ espaços,
    essa parte pode virar bloco de código e aparecer literalmente na TV.

    Compactamos apenas os blocos HTML de conteúdo, preservando o CSS.
    """
    return "".join(line.strip() for line in str(value).splitlines())

def fnum(value: Any) -> float:
    try:
        return float(value or 0)
    except Exception:
        return 0.0

def fmt_qty(value: Any) -> str:
    x = fnum(value)
    if abs(x - round(x)) < 1e-9:
        return f"{int(round(x)):,}".replace(",", ".")
    return f"{x:,.1f}".replace(",", "X").replace(".", ",").replace("X", ".")

def parse_ts(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        text = str(value).replace("Z", "+00:00")
        dt = datetime.fromisoformat(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=TZ)
        return dt.astimezone(TZ)
    except Exception:
        return None

def hhmm(value: Any) -> str:
    dt = parse_ts(value)
    return dt.strftime("%H:%M") if dt else "--:--"

def duration_text(minutes: float) -> str:
    minutes = max(0, int(round(minutes)))
    h, m = divmod(minutes, 60)
    return f"{h}h {m:02d}min" if h else f"{m}min"

def production_date(now: datetime) -> date:
    return now.date() - timedelta(days=1) if now.time() < time(6, 0) else now.date()

def machine_name(code: str) -> str:
    digits = "".join(ch for ch in str(code) if ch.isdigit())
    if digits:
        return f"SERRA {int(digits)}"
    return str(code)

def status_key(status: str, online: bool = True) -> tuple[str, str]:
    if not online:
        return "OFFLINE", "off"
    s = str(status or "").upper().replace("_", " ")
    if s in {"EM PRODUCAO", "EM PRODUÇÃO"}:
        return "EM PRODUÇÃO", "run"
    if s == "EM SETUP":
        return "EM SETUP", "setup"
    if s == "PAUSADA":
        return "PAUSADA", "pause"
    if s == "PARCIAL":
        return "PARCIAL", "partial"
    if s == "CONCLUIDA":
        return "CONCLUÍDA", "run"
    return s or "AGUARDANDO", "wait"

def color_for_pct(value: float) -> str:
    if value >= 85:
        return "#24dc83"
    if value >= 70:
        return "#ffbd1a"
    return "#ff5666"

def performance_class(value: float | None) -> str:
    if value is None:
        return ""
    if value >= 90:
        return "perf-good"
    if value >= 75:
        return "perf-mid"
    return "perf-bad"


# ============================================================
# SUPABASE
# ============================================================

class SupabaseAPI:
    def __init__(self, url: str, key: str):
        self.url = str(url or "").rstrip("/")
        self.key = str(key or "").strip()
        self.session = requests.Session()

        headers = {
            "apikey": self.key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        # Chaves JWT antigas (eyJ...) podem ser usadas também como Bearer.
        # As chaves novas sb_secret_ / sb_publishable_ funcionam pelo apikey.
        if self.key.startswith("eyJ"):
            headers["Authorization"] = f"Bearer {self.key}"

        self.session.headers.update(headers)

    @property
    def configured(self) -> bool:
        return bool(self.url and self.key)

    def rpc(self, name: str, payload: dict | None = None, timeout: int = 12):
        r = self.session.post(
            f"{self.url}/rest/v1/rpc/{name}",
            json=payload or {},
            timeout=timeout,
        )
        if r.status_code >= 400:
            raise RuntimeError(f"{name}: HTTP {r.status_code} · {r.text[:300]}")
        if not r.text.strip():
            return None
        return r.json()


def demo_payload():
    now = datetime.now(TZ)
    demo = {}
    items = ["3256", "4270", "4218", "4289", "3301"]
    descs = ["SUPORTE LATERAL", "TRAVESSA", "REFORÇO", "SUPORTE", "CHAPA FIXAÇÃO"]
    statuses = ["EM_PRODUCAO", "EM_SETUP", "EM_PRODUCAO", "PAUSADA", "AGUARDANDO"]
    starts = [now - timedelta(hours=5), now - timedelta(minutes=35), now - timedelta(hours=3),
              now - timedelta(hours=2), None]
    qtys = [(1400,2000),(120,800),(980,1200),(460,1000),(0,0)]
    for idx, machine in enumerate(MACHINES):
        orders = []
        for j in range(5):
            k = (idx+j) % len(items)
            done, planned = qtys[idx] if j == 0 else (0, [800,450,320,600,400][j-1])
            orders.append({
                "operation_id": idx*100+j+1,
                "seq": j+1,
                "op": f"OS-{idx+1:02d}{j+1:02d}",
                "item": items[k],
                "description": descs[k],
                "machine": machine,
                "planned_qty": planned,
                "done_qty": done,
                "active_execution_id": f"demo-{idx}" if j == 0 and statuses[idx] != "AGUARDANDO" else None,
                "active_inicio_em": starts[idx].isoformat() if j == 0 and starts[idx] else None,
                "active_turno": "T1",
                "status": statuses[idx] if j == 0 else "AGUARDANDO",
                "is_unplanned": False,
                "execution_source": "PROGRAMADA",
            })
        hist = []
        if starts[idx]:
            quantities = [500,450,450] if idx == 0 else ([300,350,330] if idx == 2 else [220,240])
            cursor = starts[idx]
            for q in quantities[:3]:
                end = cursor + timedelta(minutes=70)
                hist.append({
                    "id": f"h-{idx}-{q}",
                    "operacao_id": idx*100+1,
                    "maquina": machine,
                    "op": f"OS-{idx+1:02d}01",
                    "codigo_item": items[idx],
                    "descricao_item": descs[idx],
                    "status": "FINALIZADA",
                    "inicio_em": cursor.isoformat(),
                    "producao_inicio_em": cursor.isoformat(),
                    "fim_em": end.isoformat(),
                    "pausa_inicio_em": None,
                    "setup_minutos": 5 if q == quantities[0] else 0,
                    "pausa_minutos": 8,
                    "quantidade_boa": q,
                    "quantidade_refugo": 0,
                    "encerramento_tipo": "PARCIAL",
                    "proximo_passo": "CONTINUAR",
                    "turno": "T1",
                    "data_producao": production_date(now).isoformat(),
                    "origem_execucao": "PROGRAMADA",
                })
                cursor = end
            if statuses[idx] != "AGUARDANDO":
                hist.append({
                    "id": f"active-{idx}",
                    "operacao_id": idx*100+1,
                    "maquina": machine,
                    "op": f"OS-{idx+1:02d}01",
                    "codigo_item": items[idx],
                    "descricao_item": descs[idx],
                    "status": statuses[idx],
                    "inicio_em": cursor.isoformat(),
                    "producao_inicio_em": cursor.isoformat(),
                    "fim_em": None,
                    "pausa_inicio_em": (now - timedelta(minutes=20)).isoformat() if statuses[idx]=="PAUSADA" else None,
                    "setup_minutos": 0,
                    "pausa_minutos": 0,
                    "quantidade_boa": 0,
                    "quantidade_refugo": 0,
                    "turno": "T1",
                    "data_producao": production_date(now).isoformat(),
                    "origem_execucao": "PROGRAMADA",
                })
        demo[machine] = {"queue": {"plan":{"codigo_plano":"APS-DEMO"},"orders":orders}, "history":hist}
    catalog = [
        {"codigo_item":"3256","maquina":"","tempo_padrao_segundos":9.0},
        {"codigo_item":"4270","maquina":"","tempo_padrao_segundos":12.0},
        {"codigo_item":"4218","maquina":"","tempo_padrao_segundos":10.5},
        {"codigo_item":"4289","maquina":"","tempo_padrao_segundos":11.0},
        {"codigo_item":"3301","maquina":"","tempo_padrao_segundos":8.5},
    ]
    return demo, catalog


def fetch_real(api: SupabaseAPI, prod_date: date):
    results = {m: {"queue": None, "history": [], "error": None} for m in MACHINES}

    def queue_call(machine):
        return api.rpc("aps_tablet_fila_serra", {"p_maquina": machine})

    def hist_call(machine):
        # RPC nova e mais precisa para o dashboard.
        try:
            return api.rpc(
                "aps_dashboard_historico_serra",
                {"p_maquina": machine, "p_data_producao": prod_date.isoformat()},
            )
        except Exception:
            # Fallback para o APK V6 atual.
            return api.rpc("aps_tablet_historico", {"p_maquina": machine, "p_limite": 200})

    with ThreadPoolExecutor(max_workers=10) as ex:
        fut_map = {}
        for m in MACHINES:
            fut_map[ex.submit(queue_call, m)] = (m, "queue")
            fut_map[ex.submit(hist_call, m)] = (m, "history")
        for fut in as_completed(fut_map):
            machine, kind = fut_map[fut]
            try:
                results[machine][kind] = fut.result()
            except Exception as exc:
                results[machine]["error"] = str(exc)

    try:
        catalog = api.rpc("aps_dashboard_catalogo")
    except Exception:
        try:
            simple = api.rpc("aps_tablet_catalogo_itens") or []
            catalog = [
                {
                    "codigo_item": x.get("codigo_item"),
                    "maquina": "",
                    "tempo_padrao_segundos": None,
                    "descricao": x.get("descricao", ""),
                }
                for x in simple
            ]
        except Exception:
            catalog = []

    return results, catalog or []


# ============================================================
# CÁLCULOS
# ============================================================

def build_standard_map(catalog: list[dict]) -> dict[tuple[str,str], float]:
    out = {}
    for row in catalog or []:
        item = str(row.get("codigo_item") or "").strip().upper()
        machine = str(row.get("maquina") or "").strip().upper()
        sec = fnum(row.get("tempo_padrao_segundos"))
        if item and sec > 0:
            out[(item, machine)] = sec
    return out

def std_seconds(std_map, item: str, machine: str) -> float:
    key = str(item or "").strip().upper()
    mac = str(machine or "").strip().upper()
    return std_map.get((key, mac), std_map.get((key, ""), 0.0))

def open_orders(queue_data: dict | None) -> list[dict]:
    orders = (queue_data or {}).get("orders", []) or []
    rows = [dict(x) for x in orders]
    rows.sort(key=lambda x: int(fnum(x.get("seq")) or 999999))
    return rows

def current_order(queue_data: dict | None) -> dict | None:
    rows = open_orders(queue_data)
    active_status = {"EM_SETUP","EM_PRODUCAO","PAUSADA"}
    for x in rows:
        if str(x.get("status","")).upper() in active_status and x.get("active_execution_id"):
            return x
    for x in rows:
        if str(x.get("status","")).upper() != "CONCLUIDA":
            return x
    return None

def next_queue(queue_data: dict | None, current: dict | None, n=4) -> list[dict]:
    rows = [x for x in open_orders(queue_data) if str(x.get("status","")).upper() != "CONCLUIDA"]
    if not current:
        return rows[:n]
    out = []
    current_id = current.get("operation_id")
    current_unplanned = bool(current.get("is_unplanned"))
    for x in rows:
        if current_unplanned and x.get("is_unplanned"):
            continue
        if current_id is not None and x.get("operation_id") == current_id:
            continue
        out.append(x)
    return out[:n]

def history_today(rows: list[dict], prod_date: date) -> list[dict]:
    out = []
    for r in rows or []:
        dp = str(r.get("data_producao") or "")
        if dp:
            if dp[:10] != prod_date.isoformat():
                continue
        out.append(dict(r))
    return out

def current_execution_chain(history: list[dict], current: dict | None) -> list[dict]:
    """
    Retorna SOMENTE a cadeia da execução atual.

    O APK cria uma nova execução a cada parcial/continuação.
    Quando a continuação é automática, a nova linha aponta para a anterior
    em continuacao_de.

    Assim:
        parcial 1 <- parcial 2 <- execução ativa

    Se o operador encerrou o trecho para trocar de peça e alguém retomou
    posteriormente, a nova execução nasce sem pertencer à cadeia anterior.
    A eficiência então recomeça do novo início, como deve ser.
    """
    if not current:
        return []

    active_id = str(current.get("active_execution_id") or "").strip()
    if not active_id:
        return []

    by_id = {
        str(r.get("id") or "").strip(): dict(r)
        for r in (history or [])
        if str(r.get("id") or "").strip()
    }

    if active_id not in by_id:
        # Fallback defensivo para RPC antiga: tenta localizar a execução ativa
        # pelo horário de início/código.
        active_start = parse_ts(current.get("active_inicio_em"))
        item = str(current.get("item") or "").strip().upper()
        candidates = []
        for r in history or []:
            if str(r.get("status") or "").upper() not in {"EM_SETUP","EM_PRODUCAO","PAUSADA"}:
                continue
            if str(r.get("codigo_item") or "").strip().upper() != item:
                continue
            dt = parse_ts(r.get("inicio_em"))
            if dt:
                candidates.append((abs((dt - active_start).total_seconds()) if active_start else 0, dict(r)))
        if not candidates:
            return []
        candidates.sort(key=lambda x: x[0])
        active = candidates[0][1]
        active_id = str(active.get("id") or "").strip()
        if active_id:
            by_id[active_id] = active
        else:
            return [active]

    chain = []
    seen = set()
    cursor = active_id

    while cursor and cursor not in seen:
        seen.add(cursor)
        row = by_id.get(cursor)
        if not row:
            break
        chain.append(row)
        parent = str(row.get("continuacao_de") or "").strip()
        cursor = parent

    chain.reverse()
    return chain


def execution_metrics(rows: list[dict], machine: str, std_map: dict, now: datetime) -> dict:
    total = cut = pause = setup = qty = ideal = 0.0
    for r in rows:
        start = parse_ts(r.get("inicio_em"))
        if not start:
            continue
        end = parse_ts(r.get("fim_em")) or now
        if end < start:
            continue
        gross = max(0.0, (end - start).total_seconds() / 60.0)
        p = max(0.0, fnum(r.get("pausa_minutos")))
        s = max(0.0, fnum(r.get("setup_minutos")))
        status = str(r.get("status") or "").upper()

        pause_start = parse_ts(r.get("pausa_inicio_em"))
        if status == "PAUSADA" and pause_start:
            p += max(0.0, (now - pause_start).total_seconds() / 60.0)

        if status == "EM_SETUP" and not r.get("fim_em"):
            # Enquanto o setup está aberto, todo o trecho ainda é setup.
            s = max(s, gross)

        productive = max(0.0, gross - p - s)
        q = max(0.0, fnum(r.get("quantidade_boa")))
        sec = std_seconds(std_map, r.get("codigo_item"), machine)

        total += gross
        pause += min(p, gross)
        setup += min(s, gross)
        cut += productive
        qty += q
        if sec > 0 and q > 0:
            ideal += q * sec / 60.0

    eff_time = (cut / total * 100.0) if total > 0 else 0.0
    perf = (ideal / cut * 100.0) if cut > 0 and ideal > 0 else None
    rate = (qty / (cut / 60.0)) if cut > 0 else 0.0

    return {
        "total_min": total,
        "cut_min": cut,
        "pause_min": pause,
        "setup_min": setup,
        "qty": qty,
        "eff_time": max(0.0, min(100.0, eff_time)),
        "performance": perf,
        "rate": rate,
    }

def relevant_partials(chain: list[dict]) -> list[dict]:
    """Últimos parciais pertencentes à cadeia da execução atual."""
    rows = []
    for r in chain or []:
        if str(r.get("status") or "").upper() != "FINALIZADA":
            continue
        if fnum(r.get("quantidade_boa")) <= 0:
            continue
        rows.append(dict(r))

    rows.sort(key=lambda r: parse_ts(r.get("fim_em")) or datetime.min.replace(tzinfo=TZ))
    return rows[-3:]


def machine_summary(machine: str, payload: dict, std_map: dict, now: datetime, prod_date: date):
    queue = payload.get("queue") or {}
    hist = history_today(payload.get("history") or [], prod_date)
    cur = current_order(queue)
    nxt = next_queue(queue, cur, 4)

    # Métrica do DIA: usada somente no resumo geral.
    day_metrics = execution_metrics(hist, machine, std_map, now)

    # Métrica da PEÇA/TRECHO ATUAL:
    # segue somente a cadeia continuacao_de da execução que está aberta agora.
    chain = current_execution_chain(hist, cur)
    current_metrics = execution_metrics(chain, machine, std_map, now)

    partials = relevant_partials(chain)

    plan_rows = open_orders(queue)
    plan_total = sum(max(0,fnum(x.get("planned_qty"))) for x in plan_rows if not x.get("is_unplanned"))
    plan_done = sum(max(0,fnum(x.get("done_qty"))) for x in plan_rows if not x.get("is_unplanned"))

    return {
        "machine": machine,
        "online": payload.get("error") is None and payload.get("queue") is not None,
        "error": payload.get("error"),
        "queue_data": queue,
        "history": hist,
        "current": cur,
        "current_chain": chain,
        "next": nxt,
        "partials": partials,
        "metrics": current_metrics,
        "day_metrics": day_metrics,
        "plan_total": plan_total,
        "plan_done": plan_done,
    }


# ============================================================
# HTML DO DASHBOARD
# ============================================================

def queue_rows_html(rows: list[dict]) -> str:
    if not rows:
        return '<div class="empty-row">Nenhum próximo item</div>'
    body = []
    for i, x in enumerate(rows, 1):
        body.append(
            f"<tr><td style='width:9px'>{i}</td>"
            f"<td style='width:118px' title='{esc(x.get('item'))}'>{esc(x.get('item') or '—')}</td>"
            f"<td title='{esc(x.get('description'))}'>{esc(x.get('description') or '—')}</td>"
            f"<td style='width:42px'>{fmt_qty(max(0, fnum(x.get('planned_qty'))-fnum(x.get('done_qty'))))}</td></tr>"
        )
    return (
        "<table class='mini-table'><thead><tr><th>#</th><th>CÓDIGO</th><th>DESCRIÇÃO</th><th>QTD</th></tr></thead>"
        f"<tbody>{''.join(body)}</tbody></table>"
    )

def partial_rows_html(rows: list[dict]) -> str:
    if not rows:
        return '<div class="empty-row">Nenhum apontamento parcial hoje</div>'
    accum = 0.0
    body = []
    for r in rows:
        q = fnum(r.get("quantidade_boa"))
        accum += q
        body.append(
            f"<tr><td>{hhmm(r.get('fim_em'))}</td>"
            f"<td>{fmt_qty(q)}</td><td>{fmt_qty(accum)}</td></tr>"
        )
    return (
        "<table class='mini-table'><thead><tr><th>HORÁRIO</th><th>QTD</th><th>ACUMULADO*</th></tr></thead>"
        f"<tbody>{''.join(body)}</tbody></table>"
    )



def machine_history_html(rows: list[dict]) -> str:
    finished = []
    for r in rows or []:
        if str(r.get("status") or "").upper() != "FINALIZADA":
            continue
        dt = parse_ts(r.get("fim_em"))
        if not dt:
            continue
        finished.append((dt, r))

    finished.sort(key=lambda x: x[0], reverse=True)
    finished = finished[:3]

    out = []
    for dt, r in finished:
        code = str(r.get("codigo_item") or "—")
        qty = fnum(r.get("quantidade_boa"))
        out.append(
            "<div class='hist-row'>"
            f"<div class='hist-time'>{dt:%H:%M}</div>"
            f"<div class='hist-code' title='{esc(code)}'>{esc(code)}</div>"
            f"<div class='hist-qty'>{fmt_qty(qty)} pç</div>"
            "</div>"
        )

    while len(out) < 3:
        out.append(
            "<div class='hist-row'>"
            "<div class='hist-empty'>SEM APONTAMENTO</div>"
            "</div>"
        )

    return "<div class='history-list'>" + "".join(out) + "</div>"


def compact_queue_html(rows: list[dict]) -> str:
    out = []
    for i, x in enumerate((rows or [])[:4], 1):
        code = str(x.get("item") or "—")
        desc = str(x.get("description") or "SEM DESCRIÇÃO")
        qty = max(0, fnum(x.get("planned_qty")) - fnum(x.get("done_qty")))
        out.append(
            "<div class='queue-row'>"
            f"<div class='queue-pos'>{i}</div>"
            f"<div class='queue-code' title='{esc(code)}'>{esc(code)}</div>"
            f"<div class='queue-desc' title='{esc(desc)}'>{esc(desc)}</div>"
            f"<div class='queue-qty'>{fmt_qty(qty)}</div>"
            "</div>"
        )

    while len(out) < 4:
        out.append(
            "<div class='queue-row'>"
            "<div class='queue-empty'>SEM PRÓXIMO ITEM</div>"
            "</div>"
        )

    return "<div class='queue-list'>" + "".join(out) + "</div>"


def queue_strip_html(rows: list[dict]) -> str:
    cards = []
    for i, x in enumerate((rows or [])[:4], 1):
        code = str(x.get("item") or "—")
        desc = str(x.get("description") or "SEM DESCRIÇÃO")
        qty = max(0, fnum(x.get("planned_qty")) - fnum(x.get("done_qty")))
        cards.append(
            "<div class='next-card'>"
            f"<div class='next-pos'>{i}</div>"
            f"<div class='next-code' title='{esc(code)}'>{esc(code)}</div>"
            f"<div class='next-desc' title='{esc(desc)}'>{esc(desc)}</div>"
            "<div class='next-bottom'>"
            "<span>QTD</span>"
            f"<b>{fmt_qty(qty)}</b>"
            "</div>"
            "</div>"
        )

    while len(cards) < 4:
        cards.append(
            "<div class='next-card'>"
            "<div class='next-code' style='color:#587d99'>—</div>"
            "<div class='next-desc'>SEM PRÓXIMO ITEM</div>"
            "<div class='next-bottom'><span>QTD</span><b>—</b></div>"
            "</div>"
        )

    return "<div class='queue-strip'>" + "".join(cards) + "</div>"


def machine_card(s: dict) -> str:
    machine = s["machine"]
    cur = s["current"]
    online = s["online"]
    met = s["metrics"]
    connection_error = str(s.get("error") or "").strip()

    if cur:
        status, _badge = status_key(cur.get("status"), online)
        item = str(cur.get("item") or "—")
        desc = str(cur.get("description") or "SEM DESCRIÇÃO")
        start_time = hhmm(cur.get("active_inicio_em"))
        shift = str(cur.get("active_turno") or "—")

        planned = fnum(cur.get("planned_qty"))
        done = fnum(cur.get("done_qty"))
        is_unplanned = bool(cur.get("is_unplanned"))

        if is_unplanned:
            done = sum(
                fnum(r.get("quantidade_boa"))
                for r in s.get("current_chain", [])
                if str(r.get("status") or "").upper() == "FINALIZADA"
            )
            planned = 0

        saldo = max(0, planned - done)
        pct = (done / planned * 100) if planned > 0 else min(100, met.get("eff_time", 0))
        origin = "FORA DA PROGRAMAÇÃO" if is_unplanned else "PROGRAMAÇÃO OFICIAL"
        meta_value = "AVULSA" if is_unplanned else fmt_qty(planned)
        saldo_value = "—" if is_unplanned else fmt_qty(saldo)
        progress_class = "current-progress avulsa" if is_unplanned else "current-progress"
    else:
        status = "OFFLINE" if not online else "AGUARDANDO"
        item = "—"
        desc = connection_error[:85] if connection_error else "SEM PRODUÇÃO"
        start_time = "—"
        shift = "—"
        done = planned = saldo = pct = 0
        origin = "SEM ORDEM ATUAL"
        meta_value = "0"
        saldo_value = "0"
        progress_class = "current-progress"

    status_upper = str(status).upper()
    if not online:
        status_class = "status-off"
    elif "PRODU" in status_upper:
        status_class = "status-run"
    elif "SETUP" in status_upper:
        status_class = "status-setup"
    elif "PAUS" in status_upper:
        status_class = "status-pause"
    else:
        status_class = "status-wait"

    return f"""
    <div class="saw-row">

      <div class="saw-ident">
        <div class="saw-name-line">
          <div class="saw-name">🪚 {esc(machine_name(machine))}</div>
          <div class="saw-dot">{'●' if online else '⚠'}</div>
        </div>
        <div class="status-pill {status_class}">{esc(status)}</div>
      </div>

      <div class="current-box">
        <div class="current-top">
          <div>
            <div class="label">ITEM ATUAL</div>
            <div class="current-code" title="{esc(item)}">{esc(item)}</div>
            <div class="current-desc" title="{esc(desc)}">{esc(desc)}</div>
            <span class="origin">{esc(origin)}</span>
          </div>
          <div class="current-time">
            <div class="label">INÍCIO</div>
            <b>{esc(start_time)}</b>
            <div class="label">TURNO</div>
            <b>{esc(shift)}</b>
          </div>
        </div>

        <div class="{progress_class}">
          <span style="width:{max(0,min(100,pct)):.1f}%"></span>
        </div>

        <div class="current-metrics">
          <div class="current-metric"><span>PRODUZIDO</span><b>{fmt_qty(done)}</b></div>
          <div class="current-metric"><span>META</span><b>{meta_value}</b></div>
          <div class="current-metric"><span>SALDO</span><b class="saldo">{saldo_value}</b></div>
        </div>
      </div>

      <div class="history-box">
        <div class="box-head">
          <strong>ÚLTIMOS CORTES</strong>
          <span>HORA · PEÇA · QTD</span>
        </div>
        {machine_history_html(s["history"])}
      </div>

      <div class="queue-box">
        <div class="box-head">
          <strong>PRÓXIMOS DA FILA</strong>
          <span>1 → 4</span>
        </div>
        {compact_queue_html(s["next"])}
      </div>

    </div>
    """

def summary_html(summaries: list[dict]) -> str:
    # Resumo inferior continua sendo do dia produtivo completo.
    all_met = [s["day_metrics"] for s in summaries]
    total_qty = sum(m["qty"] for m in all_met)
    total_cut = sum(m["cut_min"] for m in all_met)
    total_time = sum(m["total_min"] for m in all_met)
    total_pause = sum(m["pause_min"] for m in all_met)
    total_setup = sum(m["setup_min"] for m in all_met)
    eff = (total_cut / total_time * 100) if total_time > 0 else 0

    return f"""
    <div class="summary-grid">
      <div class="summary-item">
        <div class="lab">UNIDADES APONTADAS</div>
        <div class="big">{fmt_qty(total_qty)}</div>
        <div class="sub">Somatório das 5 serras no dia produtivo</div>
      </div>
      <div class="summary-item">
        <div class="lab">TEMPO EM CORTE</div>
        <div class="big" style="color:#5bc7ff">{duration_text(total_cut)}</div>
        <div class="sub">Tempo líquido das execuções</div>
      </div>
      <div class="summary-item">
        <div class="lab">PAUSAS REGISTRADAS</div>
        <div class="big" style="color:#ff7b83">{duration_text(total_pause)}</div>
        <div class="sub">Inclui pausa aberta quando RPC V1 está instalada</div>
      </div>
      <div class="summary-item">
        <div class="lab">EFICIÊNCIA GERAL DE TEMPO</div>
        <div class="big" style="color:{color_for_pct(eff)}">{eff:.0f}%</div>
        <div class="sub">Setup total: {duration_text(total_setup)}</div>
      </div>
    </div>
    """

def plan_bars_html(summaries: list[dict]) -> str:
    rows = []
    for s in summaries:
        total = s["plan_total"]
        done = s["plan_done"]
        pct = min(100, done/total*100) if total > 0 else 0
        rows.append(
            f"<div class='bar-row'><b>{esc(machine_name(s['machine']))}</b>"
            f"<div class='bar-bg'><div class='bar-fill' style='width:{pct:.1f}%'></div></div>"
            f"<div class='bar-val'>{fmt_qty(done)} / {fmt_qty(total)} · {pct:.0f}%</div></div>"
        )
    return "<div class='bar-area'>" + "".join(rows) + "</div>"

def recent_events_html(summaries: list[dict]) -> str:
    events = []
    for s in summaries:
        for r in s["history"]:
            dt = parse_ts(r.get("fim_em")) or parse_ts(r.get("inicio_em"))
            if not dt:
                continue
            status = str(r.get("status") or "").upper()
            typ = str(r.get("encerramento_tipo") or "").upper()
            if status == "FINALIZADA":
                if typ == "PARCIAL":
                    label = "Apontamento parcial"
                elif typ == "CONCLUSAO":
                    label = "Conclusão"
                elif typ == "TROCA_FILA":
                    label = "Troca de peça"
                elif typ == "VIRADA_HORA_EXTRA":
                    label = "Virada hora extra"
                else:
                    label = "Apontamento"
                detail = f"{fmt_qty(r.get('quantidade_boa'))} un. · {r.get('codigo_item') or ''}"
            else:
                label = status.replace("_"," ").title()
                detail = str(r.get("codigo_item") or "")
            if str(r.get("origem_execucao") or "") == "FORA_PROGRAMACAO":
                label = "Avulsa · " + label
            events.append((dt, s["machine"], label, detail))

    events.sort(key=lambda x: x[0], reverse=True)
    rows = []
    for dt, machine, label, detail in events[:6]:
        rows.append(
            f"<div class='event-row'><span class='event-time'>{dt:%H:%M}</span>"
            f"<span class='event-machine'>{esc(machine_name(machine))}</span>"
            f"<span class='event-type'>{esc(label)}</span>"
            f"<span class='event-detail' title='{esc(detail)}'>{esc(detail)}</span></div>"
        )
    return "<div class='events'>" + ("".join(rows) if rows else "<div class='empty-row'>Sem eventos no dia</div>") + "</div>"


# ============================================================
# CARGA DOS DADOS
# ============================================================

now = datetime.now(TZ)
prod_date = production_date(now)
api = SupabaseAPI(SUPABASE_URL, SUPABASE_KEY)

# DEMO somente se o usuário pedir explicitamente DEMO_MODE=true.
# Credencial ausente ou erro de conexão NÃO gera dado fictício.
using_demo = DEMO_MODE

if using_demo:
    raw_data, catalog = demo_payload()
else:
    if not api.configured:
        raw_data = {
            m: {
                "queue": None,
                "history": [],
                "error": (
                    "Supabase não configurado. O dashboard procurou no .env local: "
                    "SUPABASE_URL e SUPABASE_ANON_KEY / SUPABASE_SECRET_KEY / SUPABASE_KEY."
                ),
            }
            for m in MACHINES
        }
        catalog = []
    else:
        raw_data, catalog = fetch_real(api, prod_date)

std_map = build_standard_map(catalog)

summaries = []
for machine in MACHINES:
    payload = raw_data.get(machine, {})
    # Se veio demo, a estrutura é idêntica.
    summaries.append(machine_summary(machine, payload, std_map, now, prod_date))

online_count = sum(1 for s in summaries if s["online"])
all_online = online_count == len(MACHINES)

weekday_pt = ["segunda-feira","terça-feira","quarta-feira","quinta-feira","sexta-feira","sábado","domingo"][now.weekday()]
week = now.isocalendar().week

header = f"""
<div class="tv-header">
  <div class="brand">IBERO<small>GROUP</small></div>
  <div class="title">
    <h1>APS SERRA <span>– MONITORAMENTO EM TEMPO REAL</span></h1>
    <p>ITEM ATUAL • ÚLTIMOS CORTES • PRÓXIMOS DA FILA</p>
  </div>
  <div class="clock">
    <div class="date">{now:%d/%m/%Y}</div>
    <div class="time">{now:%H:%M:%S}</div>
    <div class="week">{weekday_pt} · Semana {week}</div>
  </div>
</div>
"""
st.markdown(html_compact(header), unsafe_allow_html=True)

cards = '<div class="machine-grid">' + "".join(machine_card(s) for s in summaries) + "</div>"
st.markdown(html_compact(cards), unsafe_allow_html=True)
