# 🚍 GeoServer Daily Audit — SEMOB DF

Sistema automático de auditoria diária das camadas WFS do GeoServer da SEMOB-DF.

O projeto detecta alterações estruturais, operacionais e geométricas nos dados publicados, gera um resumo inteligível para analistas e envia notificações automáticas via Microsoft Teams.

------------------------------------------------------------

🎯 OBJETIVO

Permitir que operadores e analistas acompanhem mudanças reais nos dados operacionais do transporte público sem inspeção manual diária.

O sistema detecta automaticamente:

✅ Inclusões
✅ Remoções
✅ Alterações de atributos
✅ Alterações geométricas (mudança de vértices)
✅ Variação operacional por linha ou operadora

------------------------------------------------------------

⚙️ FUNCIONALIDADES

- Auditoria automática via WFS (GeoServer)
- Hash robusto ignorando campos irrelevantes
- Detecção geométrica completa
- Resumo humano automático
- Notificação Microsoft Teams
- Snapshot histórico local
- Execução diária agendada
- Fail-proof (execução ao ligar/logar)

------------------------------------------------------------

🧠 LÓGICA DE AUDITORIA

Cada feature é normalizada:

Feature → remove campos ignorados → hash SHA256

Comparação:

Snapshot anterior VS Snapshot atual

Detecta:

Tipo            | Como
----------------|--------------------------------
Adicionado      | hash novo
Removido        | hash ausente
Alterado        | mudança em propriedades ou geometria

------------------------------------------------------------

📊 CAMADAS AUDITADAS

AUDITORIA COMPLETA

- Frota por Operadora
- Horários das Linhas
- Itinerário Espacial das Linhas
- Linhas de ônibus
- Paradas de ônibus
- Ponto de paradas 2025
- Terminais de ônibus
- Viagens Programadas por Linha

ATUALIZAÇÃO SIMPLES (SEM DIFF DETALHADO)

- Dados de movimento de passageiros
- Estações de Metrô
- Faixas Exclusivas
- Linha Metrô
- vw_teste_parada_wfs

IGNORADO

- Última posição da frota (dados dinâmicos)

------------------------------------------------------------

🧾 REGRAS ESPECIAIS DE NEGÓCIO

🚌 Frota por Operadora

Avaliação baseada em:
- operadora
- numero_veiculo
- placa_veiculo

Campo ignorado:
data_referencia

------------------------------------------------------------

🕒 Horários das Linhas

Identificador operacional principal:

cd_linha

Resumo mostra:
- viagens adicionadas
- viagens removidas

------------------------------------------------------------

📍 Itinerário Espacial

A geometria é considerada crítica.
Qualquer alteração de vértice é detectada.

------------------------------------------------------------

🔔 NOTIFICAÇÃO TEAMS

Quando há mudanças:

🚨 ALTERAÇÕES DETECTADAS — SEMOB DF

🚌 Frota por Operadora
• Operadora X: +3 veículos

🕒 Horários das Linhas
• Linha 0.123: +12 viagens

📍 Itinerário Espacial
• 4 alterações geométricas

Quando NÃO há mudanças:

✅ Auditoria GeoServer executada — nenhuma alteração detectada.

------------------------------------------------------------

📁 ESTRUTURA DO PROJETO

geoserver_daily/

├── baixar_geoserver.py
├── audit_utils.py
├── notificacao.py
├── config.json
├── rodar.bat
├── downloads/
└── README.md

------------------------------------------------------------

🚀 INSTALAÇÃO

1️⃣ Clonar repositório

git clone https://github.com/SEU_USUARIO/geoserver-daily-audit.git
cd geoserver-daily-audit

------------------------------------------------------------

2️⃣ Criar ambiente Python

python -m venv .venv

Ativar:

.venv\Scripts\activate

------------------------------------------------------------

3️⃣ Instalar dependências

pip install requests

------------------------------------------------------------

▶️ EXECUÇÃO MANUAL

python baixar_geoserver.py

------------------------------------------------------------

⏰ AGENDAMENTO AUTOMÁTICO (WINDOWS)

Usar Agendador de Tarefas:

Trigger:
- Diário — 08:00
- Ao fazer logon (fail-proof)

Ação:
rodar.bat

------------------------------------------------------------

🛡️ FAIL-PROOF

Mesmo se o computador estiver desligado às 08h:
✔ roda automaticamente no próximo logon.

------------------------------------------------------------

📦 SNAPSHOTS

Arquivos salvos em:

downloads/

Formato:

semob__Nome_da_Camada.geojson

Funcionam como baseline histórico.

------------------------------------------------------------

🔐 SEGURANÇA

- Nenhum dado é modificado no GeoServer
- Apenas leitura WFS
- Webhook Teams pode ser rotacionado sem alterar lógica

------------------------------------------------------------

🔄 FLUXO DO SISTEMA

GeoServer WFS
      ↓
Download GeoJSON
      ↓
Normalização
      ↓
Hash SHA256
      ↓
Comparação Snapshot
      ↓
Resumo Humano
      ↓
Teams

------------------------------------------------------------

📈 POSSÍVEIS EXPANSÕES FUTURAS

- Relatório HTML automático
- Dashboard de mudanças
- Histórico temporal de frota
- Integração Power BI
- Monitoramento de disponibilidade WFS
- Execução em servidor (Windows Service)

------------------------------------------------------------

👨‍💻 AUTOR

Projeto desenvolvido para auditoria operacional de dados de transporte público — SEMOB DF.

------------------------------------------------------------

📄 LICENÇA

Uso interno / institucional.
