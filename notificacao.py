import requests


def enviar_teams(webhook, titulo, mensagem, link_relatorio=None):

    texto = f"{titulo}\n\n{mensagem}"

    if link_relatorio:
        texto += f"\n\nRelatório: {link_relatorio}"

    payload = {
        "text": texto
    }

    r = requests.post(webhook, json=payload, timeout=30)

    print("Teams status:", r.status_code, r.text)
