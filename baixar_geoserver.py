# ============================================================
# GEOSERVER DAILY AUDIT – SEMOB DF
# ============================================================

import requests
import json
import hashlib
from pathlib import Path
from datetime import datetime

BASE_URL = "https://geoserver.semob.df.gov.br/geoserver/semob/ows"

DOWNLOAD_DIR = Path("downloads")
DOWNLOAD_DIR.mkdir(exist_ok=True)

# ============================================================
# HUMAN SUMMARY (estrutura única)
# ============================================================

HUMAN_SUMMARY = {
    "frota": {},
    "horarios": {},
    "itinerario": {},
    "generic": {}
}

# ============================================================
# TEAMS WEBHOOK
# ============================================================

TEAMS_WEBHOOK = "https://urbimobilidade.webhook.office.com/webhookb2/cb40e1b8-96c0-43da-b152-c6b3d14e17b1@dc1693df-d65a-491e-bced-e17803feaf5e/IncomingWebhook/ce4abed999cc4e0caea27b24af384458/d258e1f9-33a4-4a37-8492-3fa227388e4e/V2tUfmwhLr7y9YxuLLcyHWGbbE5h1xQAT-cl0pCz2j9-U1"

# ============================================================
# LOG
# ============================================================

def log(msg):
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {msg}")

# ============================================================
# TEAMS
# ============================================================

def enviar_teams(resumo_humano):

    agora = datetime.now().strftime("%d/%m/%Y %H:%M")

    total_frota = sum(abs(v) for v in HUMAN_SUMMARY["frota"].values())

    total_viagens = sum(
        abs(v["add"]) + abs(v["rem"])
        for op in HUMAN_SUMMARY["horarios"].values()
        for v in op.values()
    )

    total_itinerario = sum(
        abs(v["add"]) + abs(v["rem"])
        for op in HUMAN_SUMMARY["itinerario"].values()
        for v in op.values()
    )

    houve_mudanca = any([
        total_frota,
        total_viagens,
        total_itinerario
    ])

    if total_viagens >= 50 or total_frota >= 20:
        nivel, cor, emoji = "CRITICO", "attention", "🔴"
    elif houve_mudanca:
        nivel, cor, emoji = "ATENCAO", "warning", "🟡"
    else:
        nivel, cor, emoji = "NORMAL", "good", "🟢"

    corpo = resumo_humano or (
        "Nenhuma alteração detectada nas camadas monitoradas.\n"
        "Sistema funcionando normalmente."
    )

    payload = {
        "type": "message",
        "attachments": [{
            "contentType": "application/vnd.microsoft.card.adaptive",
            "content": {
                "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                "type": "AdaptiveCard",
                "version": "1.4",
                "body": [
                    {
                        "type": "TextBlock",
                        "text": f"{emoji} Auditoria GeoServer SEMOB-DF — {nivel}",
                        "weight": "Bolder",
                        "size": "Large",
                        "color": cor
                    },
                    {
                        "type": "TextBlock",
                        "text": f"Execução: {agora}",
                        "isSubtle": True
                    },
                    {
                        "type": "TextBlock",
                        "text": corpo,
                        "wrap": True
                    }
                ]
            }
        }]
    }

    try:
        r = requests.post(TEAMS_WEBHOOK, json=payload, timeout=30)
        log(f"Teams enviado | status={r.status_code} | nível={nivel}")
    except Exception as e:
        log(f"Falha Teams: {e}")

# ============================================================
# CAMADAS
# ============================================================

LAYERS = {
    "semob:Frota por Operadora": {"ignore_fields": ["data_referencia","fid"]},
    "semob:Horários das Linhas": {"ignore_fields": ["fid"]},
    "semob:Itinerário Espacial das Linhas": {"ignore_fields": ["fid"]},

    # -------- nomes técnicos corretos (GeoServer) --------
    "semob:estacoes_metro": {},
    "semob:faixas_exclusivas": {},
    "semob:linha_metro": {},

    "semob:Paradas de onibus": {"ignore_fields": ["fid"]},
    "semob:Ponto de paradas 2025": {"ignore_fields": ["fid"]},

    "semob:terminais_onibus": {"ignore_fields": ["fid"]},

    "semob:Viagens Programadas por Linha": {"ignore_fields": ["fid"]},

    # ignorado
    "semob:Última posição da frota": {"ignore": True}
}

# ============================================================
# DOWNLOAD
# ============================================================

def request_layer(layer):

    base_params = dict(
        service="WFS",
        version="2.0.0",
        request="GetFeature",
        typeNames=layer,
        outputFormat="application/json"
    )

    r = requests.get(BASE_URL, params=base_params, timeout=120)

    # -------------------------
    # SUCESSO DIRETO
    # -------------------------
    if r.status_code == 200:
        return r.json()

    # -------------------------
    # TENTATIVA COM SORTBY
    # -------------------------
    log(f"{layer}: tentando resolver erro 400 automaticamente...")

    try:

        desc_params = dict(
            service="WFS",
            version="2.0.0",
            request="DescribeFeatureType",
            typeNames=layer
        )

        desc = requests.get(BASE_URL, params=desc_params, timeout=60)

        text = desc.text

        # tenta achar primeiro campo simples
        import re

        campos = re.findall(r'name="([^"]+)" type=', text)

        # ignora geometria
        candidatos = [
            c for c in campos
            if c.lower() not in ["geom", "geometry", "the_geom"]
        ]

        if not candidatos:
            raise RuntimeError("nenhum campo elegível para sortBy")

        campo_sort = candidatos[0]

        log(f"{layer}: usando sortBy automático -> {campo_sort}")

        base_params["sortBy"] = f"{campo_sort} A"

        r2 = requests.get(BASE_URL, params=base_params, timeout=120)

        if r2.status_code != 200:
            raise RuntimeError(f"{r2.status_code} Client Error")

        return r2.json()

    except Exception as e:
        raise RuntimeError(f"400 Client Error (auto-sort falhou): {e}")


# ============================================================
# HASH
# ============================================================

def normalize_feature(feature, ignore_fields):

    props = feature.get("properties", {}).copy()

    for f in ignore_fields:
        props.pop(f, None)

    return {"properties": props, "geometry": feature.get("geometry")}


def feature_hash(feature):
    txt = json.dumps(feature, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(txt.encode()).hexdigest()


def build_index(fc, ignore_fields):

    index = {}

    for feat in fc.get("features", []):
        norm = normalize_feature(feat, ignore_fields)
        h = feature_hash(norm)
        index.setdefault(h, []).append(norm)

    return index

# ============================================================
# HELPERS
# ============================================================

def _add_operadora_linha(container, operadora, linha, campo):

    container.setdefault(operadora, {})
    container[operadora].setdefault(linha, {"add":0,"rem":0})
    container[operadora][linha][campo] += 1

# ============================================================
# HUMAN SUMMARY UPDATE
# ============================================================

def update_human_summary(layer, added, removed, new_index, old_index):

    # ---------------- FROTA ----------------
    if layer == "semob:Frota por Operadora":

        for h in added:
            for f in new_index[h]:
                op = f["properties"].get("operadora","DESCONHECIDA")
                HUMAN_SUMMARY["frota"][op] = HUMAN_SUMMARY["frota"].get(op,0)+1

        for h in removed:
            for f in old_index[h]:
                op = f["properties"].get("operadora","DESCONHECIDA")
                HUMAN_SUMMARY["frota"][op] = HUMAN_SUMMARY["frota"].get(op,0)-1

        return

    # ---------------- HORÁRIOS ----------------
    if layer == "semob:Horários das Linhas":

        for h in added:
            for f in new_index[h]:
                p=f["properties"]
                _add_operadora_linha(
                    HUMAN_SUMMARY["horarios"],
                    p.get("nm_operadora","DESCONHECIDA"),
                    p.get("cd_linha","??"),
                    "add"
                )

        for h in removed:
            for f in old_index[h]:
                p=f["properties"]
                _add_operadora_linha(
                    HUMAN_SUMMARY["horarios"],
                    p.get("nm_operadora","DESCONHECIDA"),
                    p.get("cd_linha","??"),
                    "rem"
                )
        return

    # ---------------- ITINERÁRIO ----------------
    if layer == "semob:Itinerário Espacial das Linhas":

        for h in added:
            for f in new_index[h]:
                p=f["properties"]
                _add_operadora_linha(
                    HUMAN_SUMMARY["itinerario"],
                    p.get("nm_operadora","DESCONHECIDA"),
                    p.get("cd_linha","??"),
                    "add"
                )

        for h in removed:
            for f in old_index[h]:
                p=f["properties"]
                _add_operadora_linha(
                    HUMAN_SUMMARY["itinerario"],
                    p.get("nm_operadora","DESCONHECIDA"),
                    p.get("cd_linha","??"),
                    "rem"
                )
        return

# ============================================================
# IMPACTO OPERACIONAL
# ============================================================

def detectar_impacto_operacional():

    alertas=[]

    for op,linhas in HUMAN_SUMMARY["horarios"].items():
        for linha,info in linhas.items():

            if info["rem"]>=10:
                alertas.append(
                    f"{op}\n• Linha {linha}: −{info['rem']} viagens"
                )

    return "\n\n".join(alertas) if alertas else None

# ============================================================
# RESUMO HUMANO
# ============================================================

def gerar_resumo_humano():

    linhas=[]

    if HUMAN_SUMMARY["frota"]:
        linhas.append("🚌 Frota por Operadora\n")
        for op,v in HUMAN_SUMMARY["frota"].items():
            if v:
                linhas.append(f"• {op}: {v:+} veículos")
        linhas.append("")

    if HUMAN_SUMMARY["horarios"]:
        linhas.append("🕒 Horários das Linhas\n")

        for op,ls in HUMAN_SUMMARY["horarios"].items():
            linhas.append(f"{op}:")

            for linha,info in ls.items():
                partes=[]
                if info["add"]: partes.append(f"+{info['add']} viagens")
                if info["rem"]: partes.append(f"-{info['rem']} viagens")

                linhas.append(f"• Linha {linha}: {' | '.join(partes)}")

            linhas.append("")

    if HUMAN_SUMMARY["itinerario"]:
        linhas.append("📍 Itinerário Espacial\n")

        for op,ls in HUMAN_SUMMARY["itinerario"].items():
            linhas.append(f"{op}:")
            for linha,info in ls.items():
                linhas.append(
                    f"• Linha {linha}: +{info['add']} | -{info['rem']} alterações"
                )
            linhas.append("")

    return "\n".join(linhas) if linhas else None

# ============================================================
# AUDITORIA
# ============================================================

def audit_layer(layer,new_data):

    ignore_fields=LAYERS[layer].get("ignore_fields",[])
    file_path=DOWNLOAD_DIR/f"{layer.replace(':','__')}.geojson"

    if not file_path.exists():
        json.dump(new_data,open(file_path,"w",encoding="utf-8"),ensure_ascii=False)
        log(f"{layer}: snapshot inicial criado")
        return

    old_data=json.load(open(file_path,encoding="utf-8"))

    old_index=build_index(old_data,ignore_fields)
    new_index=build_index(new_data,ignore_fields)

    added=set(new_index)-set(old_index)
    removed=set(old_index)-set(new_index)

    update_human_summary(layer,added,removed,new_index,old_index)

    log(f"{layer}: {len(added)} adicionados | {len(removed)} removidos")

    json.dump(new_data,open(file_path,"w",encoding="utf-8"),ensure_ascii=False)

# ============================================================
# EXECUÇÃO
# ============================================================

def main():

    log("Início da auditoria")

    for layer,cfg in LAYERS.items():

        if cfg.get("ignore"):
            log(f"{layer}: IGNORADO")
            continue

        try:
            data=request_layer(layer)
            audit_layer(layer,data)

        except Exception as e:
            log(f"{layer}: ERRO {e}")

    resumo=gerar_resumo_humano()
    impacto=detectar_impacto_operacional()

    mensagem=""

    if impacto:
        mensagem+="🚨 IMPACTO OPERACIONAL DETECTADO\n\n"+impacto+"\n\n"

    if resumo:
        mensagem+=resumo

    enviar_teams(mensagem)

    log("Fim da auditoria")

# ============================================================

if __name__=="__main__":
    main()
