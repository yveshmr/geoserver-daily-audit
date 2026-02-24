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
# HUMAN SUMMARY
# ============================================================

HUMAN_SUMMARY = {
    "frota": {},
    "horarios": {},
    "itinerario": {}
}

# itinerário mudou sem alterar viagens
SPATIAL_ONLY_ALERTS = {}

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
    "semob:estacoes_metro": {},
    "semob:faixas_exclusivas": {},
    "semob:linha_metro": {},
    "semob:Paradas de onibus": {"ignore_fields": ["fid"]},
    "semob:Ponto de paradas 2025": {"ignore_fields": ["fid"]},
    "semob:terminais_onibus": {"ignore_fields": ["fid"]},
    "semob:Viagens Programadas por Linha": {"ignore_fields": ["fid"]},
    "semob:Última posição da frota": {"ignore": True}
}

# ============================================================
# DOWNLOAD
# ============================================================

def request_layer(layer):

    params = dict(
        service="WFS",
        version="2.0.0",
        request="GetFeature",
        typeNames=layer,
        outputFormat="application/json"
    )

    r = requests.get(BASE_URL, params=params, timeout=120)

    if r.status_code == 200:
        return r.json()

    raise RuntimeError(f"Erro HTTP {r.status_code}")

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

    if layer == "semob:Frota por Operadora":

        for h in added:
            for f in new_index[h]:
                op = f["properties"].get("operadora","DESCONHECIDA")
                HUMAN_SUMMARY["frota"][op] = HUMAN_SUMMARY["frota"].get(op,0)+1

        for h in removed:
            for f in old_index[h]:
                op = f["properties"].get("operadora","DESCONHECIDA")
                HUMAN_SUMMARY["frota"][op] = HUMAN_SUMMARY["frota"].get(op,0)-1

    elif layer == "semob:Horários das Linhas":

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

    elif layer == "semob:Itinerário Espacial das Linhas":

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

# ============================================================
# DETECÇÃO ESPACIAL SILENCIOSA
# ============================================================

def detectar_itinerario_silencioso():

    for operadora, linhas in HUMAN_SUMMARY["itinerario"].items():

        for linha, info in linhas.items():

            houve_itinerario = info["add"] or info["rem"]

            horarios_op = HUMAN_SUMMARY["horarios"].get(operadora, {})
            horarios_linha = horarios_op.get(linha, {"add":0,"rem":0})

            houve_horario = (
                horarios_linha["add"] or
                horarios_linha["rem"]
            )

            if houve_itinerario and not houve_horario:
                SPATIAL_ONLY_ALERTS.setdefault(operadora, [])
                SPATIAL_ONLY_ALERTS[operadora].append(linha)

# ============================================================
# RESUMO HUMANO
# ============================================================

def gerar_resumo_humano():

    linhas=[]

    # FROTA
    if HUMAN_SUMMARY["frota"]:
        linhas.append("🚌 Frota por Operadora\n")
        for op,v in HUMAN_SUMMARY["frota"].items():
            if v:
                linhas.append(f"• {op}: {v:+} veículos")
        linhas.append("")

    # HORÁRIOS
    if HUMAN_SUMMARY["horarios"]:
        linhas.append("🕒 Horários das Linhas\n")

        for op,ls in HUMAN_SUMMARY["horarios"].items():

            linhas.append(op)

            for linha,info in ls.items():

                saldo = info["add"] - info["rem"]

                partes=[]
                if info["add"]:
                    partes.append(f"+{info['add']}")
                if info["rem"]:
                    partes.append(f"-{info['rem']}")

                linhas.append(
                    f"• Linha {linha}: {' | '.join(partes)} viagens (saldo {saldo:+})"
                )

            linhas.append("")

    # ITINERÁRIO
    if HUMAN_SUMMARY["itinerario"]:
        linhas.append("📍 Itinerário Espacial\n")

        for op,ls in HUMAN_SUMMARY["itinerario"].items():

            linhas.append(op)

            for linha,info in ls.items():

                qtd = min(info["add"], info["rem"])

                if qtd:
                    linhas.append(f"• Linha {linha}: {qtd} alterações")

            linhas.append("")

    # ALERTA ESPACIAL SILENCIOSO
    if SPATIAL_ONLY_ALERTS:

        linhas.append("⚠️ Alteração espacial sem mudança de viagens\n")

        for op,lista in SPATIAL_ONLY_ALERTS.items():
            linhas.append(op)
            for linha in lista:
                linhas.append(f"• Linha {linha}")
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

    detectar_itinerario_silencioso()

    resumo=gerar_resumo_humano()

    enviar_teams(resumo)

    log("Fim da auditoria")

# ============================================================

if __name__=="__main__":
    main()