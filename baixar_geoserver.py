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

AUDIT_REPORT = []

HUMAN_SUMMARY = {
    "frota": {},
    "horarios_add": {},
    "horarios_rem": {},
    "itinerario": 0,
    "generic": {}
}


# ============================================================
# TEAMS
# ============================================================

TEAMS_WEBHOOK = "https://urbimobilidade.webhook.office.com/webhookb2/cb40e1b8-96c0-43da-b152-c6b3d14e17b1@dc1693df-d65a-491e-bced-e17803feaf5e/IncomingWebhook/ce4abed999cc4e0caea27b24af384458/d258e1f9-33a4-4a37-8492-3fa227388e4e/V2tUfmwhLr7y9YxuLLcyHWGbbE5h1xQAT-cl0pCz2j9-U1"


# ============================================================
# TEAMS – ENVIO INTELIGENTE (HEARTBEAT + SEVERIDADE)
# ============================================================

def enviar_teams(resumo_humano):

    agora = datetime.now().strftime("%d/%m/%Y %H:%M")

    # --------------------------------------------------------
    # CLASSIFICAÇÃO AUTOMÁTICA
    # --------------------------------------------------------

    total_frota = sum(abs(v) for v in HUMAN_SUMMARY["frota"].values())
    total_viagens = (
        sum(HUMAN_SUMMARY["horarios_add"].values()) +
        sum(HUMAN_SUMMARY["horarios_rem"].values())
    )
    total_itinerario = HUMAN_SUMMARY["itinerario"]
    total_generic = sum(
        v["added"] + v["removed"]
        for v in HUMAN_SUMMARY["generic"].values()
    )

    houve_mudanca = any([
        total_frota,
        total_viagens,
        total_itinerario,
        total_generic
    ])

    # ---- definição nível ----

    if total_viagens >= 50 or total_frota >= 20 or total_itinerario >= 10:
        nivel = "CRITICO"
        cor = "attention"     # vermelho Teams
        emoji = "🔴"

    elif houve_mudanca:
        nivel = "ATENCAO"
        cor = "warning"       # amarelo Teams
        emoji = "🟡"

    else:
        nivel = "NORMAL"
        cor = "good"          # verde Teams
        emoji = "🟢"

    # --------------------------------------------------------
    # TEXTO PRINCIPAL
    # --------------------------------------------------------

    if resumo_humano:
        corpo = resumo_humano
    else:
        corpo = (
            "Nenhuma alteração detectada nas camadas monitoradas.\n"
            "Sistema funcionando normalmente."
        )

    titulo = f"{emoji} Auditoria GeoServer SEMOB-DF — {nivel}"

    # --------------------------------------------------------
    # ADAPTIVE CARD (mensagem rica Teams)
    # --------------------------------------------------------

    payload = {
        "type": "message",
        "attachments": [
            {
                "contentType": "application/vnd.microsoft.card.adaptive",
                "content": {
                    "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                    "type": "AdaptiveCard",
                    "version": "1.4",
                    "body": [

                        {
                            "type": "TextBlock",
                            "text": titulo,
                            "weight": "Bolder",
                            "size": "Large",
                            "color": cor
                        },

                        {
                            "type": "TextBlock",
                            "text": f"Execução: {agora}",
                            "spacing": "Small",
                            "isSubtle": True
                        },

                        {
                            "type": "TextBlock",
                            "text": corpo,
                            "wrap": True,
                            "spacing": "Medium"
                        }
                    ]
                }
            }
        ]
    }

    # --------------------------------------------------------
    # ENVIO
    # --------------------------------------------------------

    try:
        r = requests.post(
            TEAMS_WEBHOOK,
            json=payload,
            timeout=30
        )

        log(f"Teams enviado | status={r.status_code} | nível={nivel}")

    except Exception as e:
        log(f"Falha ao enviar Teams: {e}")



# ============================================================
# CONFIGURAÇÃO DAS CAMADAS
# ============================================================

LAYERS = {

    "semob:Frota por Operadora": {"ignore_fields": ["data_referencia", "fid"]},
    "semob:Horários das Linhas": {"ignore_fields": ["fid"]},
    "semob:Itinerário Espacial das Linhas": {"ignore_fields": ["fid"]},
    "semob:Linhas de onibus": {"ignore_fields": ["fid"]},
    "semob:Paradas de onibus": {"ignore_fields": ["fid"]},
    "semob:Ponto de paradas 2025": {"ignore_fields": ["fid"]},
    "semob:Terminais de ônibus": {"ignore_fields": ["fid"]},
    "semob:Viagens Programadas por Linha": {"ignore_fields": ["fid"]},

    # sem auditoria detalhada
    "semob:Dados de movimento de passageiros (Quantitativo e Financeiro)": {},
    "semob:Estações de  Metrô": {},
    "semob:Faixas Exclusivas - DF": {},
    "semob:Linha Metrô": {},
    "semob:vw_teste_parada_wfs": {},

    # ignorado
    "semob:Última posição da frota": {"ignore": True}
}

# ============================================================
# UTILIDADES
# ============================================================

def log(msg):
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {msg}")


def request_layer(layer):

    params = {
        "service": "WFS",
        "version": "2.0.0",
        "request": "GetFeature",
        "typeNames": layer,
        "outputFormat": "application/json"
    }

    r = requests.get(BASE_URL, params=params, timeout=120)

    if r.status_code != 200:
        raise RuntimeError(f"{r.status_code} Client Error")

    return r.json()


# ============================================================
# HASH ROBUSTO
# ============================================================

def normalize_feature(feature, ignore_fields):

    props = feature.get("properties", {}).copy()

    for f in ignore_fields:
        props.pop(f, None)

    return {
        "properties": props,
        "geometry": feature.get("geometry")
    }


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
# RESUMO HUMANO
# ============================================================

def update_human_summary(layer, added, removed, new_index, old_index):

    # =========================================================
    # FROTA POR OPERADORA (regra especial)
    # =========================================================
    if layer == "semob:Frota por Operadora":

        for h in added:
            for feat in new_index[h]:
                op = feat["properties"].get("operadora", "DESCONHECIDA")
                HUMAN_SUMMARY["frota"].setdefault(op, 0)
                HUMAN_SUMMARY["frota"][op] += 1

        for h in removed:
            for feat in old_index[h]:
                op = feat["properties"].get("operadora", "DESCONHECIDA")
                HUMAN_SUMMARY["frota"].setdefault(op, 0)
                HUMAN_SUMMARY["frota"][op] -= 1

        return

    # =========================================================
    # HORÁRIOS DAS LINHAS (regra especial)
    # =========================================================
    if layer == "semob:Horários das Linhas":

        for h in added:
            for feat in new_index[h]:
                linha = feat["properties"].get("cd_linha", "??")
                HUMAN_SUMMARY["horarios_add"].setdefault(linha, 0)
                HUMAN_SUMMARY["horarios_add"][linha] += 1

        for h in removed:
            for feat in old_index[h]:
                linha = feat["properties"].get("cd_linha", "??")
                HUMAN_SUMMARY["horarios_rem"].setdefault(linha, 0)
                HUMAN_SUMMARY["horarios_rem"][linha] += 1

        return

    # =========================================================
    # ITINERÁRIO ESPACIAL (regra especial)
    # =========================================================
    if layer == "semob:Itinerário Espacial das Linhas":
        if added or removed:
            HUMAN_SUMMARY["itinerario"] += len(added) + len(removed)
        return

    # =========================================================
    # FALLBACK AUTOMÁTICO (todas as outras camadas)
    # =========================================================
    if added or removed:

        HUMAN_SUMMARY["generic"][layer] = {
            "added": len(added),
            "removed": len(removed)
        }



def gerar_resumo_humano():

    linhas = []

    # =====================================================
    # FROTA
    # =====================================================
    if HUMAN_SUMMARY["frota"]:
        linhas.append("🚌 Frota por Operadora")

        for op, v in HUMAN_SUMMARY["frota"].items():
            if v != 0:
                sinal = "+" if v > 0 else ""
                linhas.append(f"• {op}: {sinal}{v} veículos")

        linhas.append("")

    # =====================================================
    # HORÁRIOS
    # =====================================================
    if HUMAN_SUMMARY["horarios_add"] or HUMAN_SUMMARY["horarios_rem"]:

        linhas.append("🕒 Horários das Linhas")

        for l, q in HUMAN_SUMMARY["horarios_add"].items():
            linhas.append(f"• Linha {l}: +{q} viagens")

        for l, q in HUMAN_SUMMARY["horarios_rem"].items():
            linhas.append(f"• Linha {l}: -{q} viagens")

        linhas.append("")

    # =====================================================
    # ITINERÁRIO
    # =====================================================
    if HUMAN_SUMMARY["itinerario"] > 0:
        linhas.append("📍 Itinerário Espacial")
        linhas.append(
            f"• {HUMAN_SUMMARY['itinerario']} alterações geométricas"
        )
        linhas.append("")

    # =====================================================
    # CAMADAS GENÉRICAS (NOVO)
    # =====================================================
    if HUMAN_SUMMARY["generic"]:

        linhas.append("📊 Outras Alterações Detectadas")

        for layer, info in HUMAN_SUMMARY["generic"].items():

            nome = layer.replace("semob:", "")

            linhas.append(f"• {nome}: "
                          f"+{info['added']} | -{info['removed']}")

        linhas.append("")

    # =====================================================
    return "\n".join(linhas) if linhas else None



# ============================================================
# AUDITORIA
# ============================================================

def audit_layer(layer, new_data):

    ignore_fields = LAYERS[layer].get("ignore_fields", [])

    file_path = DOWNLOAD_DIR / f"{layer.replace(':','__')}.geojson"

    if not file_path.exists():
        json.dump(new_data, open(file_path,"w",encoding="utf-8"), ensure_ascii=False)
        log(f"{layer}: snapshot inicial criado")
        return

    old_data = json.load(open(file_path,encoding="utf-8"))

    old_index = build_index(old_data, ignore_fields)
    new_index = build_index(new_data, ignore_fields)

    added = set(new_index) - set(old_index)
    removed = set(old_index) - set(new_index)

    update_human_summary(layer, added, removed, new_index, old_index)

    log(f"{layer}: {len(added)} adicionados | {len(removed)} removidos | 0 alterados")

    if added or removed:

        AUDIT_REPORT.append(f"\n=== {layer} ===")

        for h in list(added)[:20]:
            AUDIT_REPORT.append(f"+ {h}")

        for h in list(removed)[:20]:
            AUDIT_REPORT.append(f"- {h}")

    json.dump(new_data, open(file_path,"w",encoding="utf-8"), ensure_ascii=False)


# ============================================================
# EXECUÇÃO
# ============================================================

def main():

    log("Início da auditoria")

    for layer, cfg in LAYERS.items():

        if cfg.get("ignore"):
            log(f"{layer}: IGNORADO")
            continue

        try:
            data = request_layer(layer)

            if "ignore_fields" in cfg:
                audit_layer(layer, data)
            else:
                log(f"{layer}: atualizado (sem auditoria detalhada)")

        except Exception as e:
            log(f"{layer}: ERRO {e}")

    resumo_humano = gerar_resumo_humano()

    if resumo_humano:
        mensagem = "🚨 ALTERAÇÕES DETECTADAS — SEMOB DF\n\n" + resumo_humano
    else:
        mensagem = "✅ Auditoria GeoServer executada — nenhuma alteração detectada."

    enviar_teams(resumo_humano)

    log("Fim da auditoria")


# ============================================================

if __name__ == "__main__":
    main()
