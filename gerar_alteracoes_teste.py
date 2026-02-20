# ============================================================
# GERADOR DE ALTERAÇÕES REALISTAS – SEMOB DF
# ============================================================

import json
import random
from pathlib import Path

DOWNLOAD_DIR = Path("downloads")


# ============================================================
# UTIL
# ============================================================

def carregar(nome):
    return json.load(open(DOWNLOAD_DIR / nome, encoding="utf-8"))


def salvar(nome, data):
    json.dump(
        data,
        open(DOWNLOAD_DIR / nome, "w", encoding="utf-8"),
        ensure_ascii=False
    )


# ============================================================
# HORÁRIOS DAS LINHAS (SEMÂNTICO)
# ============================================================

def alterar_horarios():

    arquivo = "semob__Horários das Linhas.geojson"
    data = carregar(arquivo)

    feats = data["features"]

    print("\n=== HORÁRIOS DAS LINHAS ===")

    for i in range(3):

        base = random.choice(feats)
        novo = json.loads(json.dumps(base))  # clone real

        props = novo["properties"]

        # altera horário mantendo operadora/linha
        h, m = map(int, props["hr_prevista"].split(":"))
        m = (m + random.choice([5, 10, 15])) % 60

        props["hr_prevista"] = f"{h:02d}:{m:02d}"

        feats.append(novo)

        print(
            f"✔ {props['nm_operadora']} | "
            f"Linha {props['cd_linha']} "
            f"novo horário {props['hr_prevista']}"
        )

    salvar(arquivo, data)


# ============================================================
# ITINERÁRIO (ALTERAÇÃO GEOMÉTRICA REAL)
# ============================================================

def alterar_itinerario():

    arquivo = "semob__Itinerário Espacial das Linhas.geojson"
    data = carregar(arquivo)

    print("\n=== ITINERÁRIO ESPACIAL ===")

    feat = random.choice(data["features"])

    geom = feat["geometry"]

    try:
        coords = geom["coordinates"][0]

        if len(coords) > 3:
            coords[1][0] += 0.00005
            coords[1][1] += 0.00005

            print("✔ vértice deslocado (mudança geométrica real)")

    except Exception:
        print("⚠ geometria não alterável")

    salvar(arquivo, data)


# ============================================================
# FROTA POR OPERADORA
# ============================================================

def alterar_frota():

    arquivo = "semob__Frota por Operadora.geojson"
    data = carregar(arquivo)

    print("\n=== FROTA POR OPERADORA ===")

    base = random.choice(data["features"])
    novo = json.loads(json.dumps(base))

    props = novo["properties"]

    props["numero_veiculo"] = str(
        int(props["numero_veiculo"]) + random.randint(1, 50)
    )

    props["placa_veiculo"] = "TESTE-" + str(random.randint(1000, 9999))

    data["features"].append(novo)

    print(f"✔ veículo adicionado para {props['operadora']}")

    salvar(arquivo, data)


# ============================================================
# GENÉRICO (PARADAS / TERMINAIS / LINHAS)
# ============================================================

def alterar_generico(nome):

    arquivo = nome
    data = carregar(arquivo)

    print(f"\n=== {nome} ===")

    base = random.choice(data["features"])
    novo = json.loads(json.dumps(base))

    data["features"].append(novo)

    print("✔ feature duplicada para gerar alteração")

    salvar(arquivo, data)


# ============================================================
# EXECUÇÃO
# ============================================================

print("\n=== GERANDO ALTERAÇÕES REALISTAS ===")

alterar_frota()
alterar_horarios()
alterar_itinerario()

alterar_generico("semob__Paradas de onibus.geojson")
alterar_generico("semob__Ponto de paradas 2025.geojson")
alterar_generico("semob__Viagens Programadas por Linha.geojson")

print("\n✅ Alterações geradas com contexto operacional real.")
