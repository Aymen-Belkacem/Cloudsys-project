"""Comtrade Anomalies - Etape 2 : application Streamlit (placeholder).

Cette version n'ouvre aucune connexion a une base de donnees.
Elle affiche un "status report" qui permet de verifier que la chaine
Docker -> ECR -> ECS Express Mode fonctionne de bout en bout.
"""

import json
import os
import platform
import socket
import sys
import urllib.request
from datetime import datetime, timezone

import streamlit as st

APP_NAME = "Comtrade Anomalies"
APP_VERSION = os.getenv("APP_VERSION", "dev")
APP_ENV = os.getenv("APP_ENV", "local")


@st.cache_resource
def _started_at() -> datetime:
    """Heure de demarrage du process (mise en cache pour toute la duree de vie)."""
    return datetime.now(timezone.utc)


def _ecs_task_metadata() -> dict | None:
    """Lit les metadonnees de la tache ECS si l'app tourne sur ECS/Fargate.

    ECS injecte la variable ECS_CONTAINER_METADATA_URI_V4 dans chaque conteneur.
    En local, elle est absente et la fonction renvoie None.
    """
    base_uri = os.getenv("ECS_CONTAINER_METADATA_URI_V4")
    if not base_uri:
        return None
    try:
        with urllib.request.urlopen(f"{base_uri}/task", timeout=2) as resp:
            data = json.load(resp)
        return {
            "Cluster": data.get("Cluster", "?").split("/")[-1],
            "Task ARN": data.get("TaskARN", "?"),
            "Availability Zone": data.get("AvailabilityZone", "?"),
            "Launch type": data.get("LaunchType", "?"),
            "Task definition": f'{data.get("Family", "?")}:{data.get("Revision", "?")}',
        }
    except Exception as exc:  # noqa: BLE001 - le status report ne doit jamais planter
        return {"Erreur lecture metadonnees": str(exc)}


def _format_uptime(started: datetime) -> str:
    seconds = int((datetime.now(timezone.utc) - started).total_seconds())
    hours, rest = divmod(seconds, 3600)
    minutes, secs = divmod(rest, 60)
    return f"{hours} h {minutes:02d} min {secs:02d} s"


# --------------------------------------------------------------------------- #
# Page
# --------------------------------------------------------------------------- #
st.set_page_config(page_title=APP_NAME, page_icon=":bar_chart:", layout="wide")

st.title(f"{APP_NAME} - Status report")
st.caption("Etape 2 : application Streamlit. Version placeholder, sans base de donnees.")

ecs_meta = _ecs_task_metadata()
runtime = "AWS ECS (Fargate)" if ecs_meta else "Local (Docker / poste de dev)"

col1, col2, col3, col4 = st.columns(4)
col1.metric("Statut", "OK")
col2.metric("Version", APP_VERSION)
col3.metric("Environnement", APP_ENV)
col4.metric("Uptime", _format_uptime(_started_at()))

st.subheader("Execution")
st.table(
    {
        "Parametre": [
            "Plateforme",
            "Hostname du conteneur",
            "Heure serveur (UTC)",
            "Python",
            "Streamlit",
            "OS / architecture",
        ],
        "Valeur": [
            runtime,
            socket.gethostname(),
            datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
            sys.version.split()[0],
            st.__version__,
            f"{platform.system()} / {platform.machine()}",
        ],
    }
)

if ecs_meta:
    st.subheader("Tache ECS")
    st.table({"Parametre": list(ecs_meta.keys()), "Valeur": list(ecs_meta.values())})

st.subheader("Composants de l'architecture")
st.table(
    {
        "Composant": [
            "Amazon DocumentDB (trades_matrix, reports_metadata)",
            "AWS Lambda - IA Orchestrator (etape 3)",
            "Amazon S3 - reports-pdf (etape 3)",
            "AWS Cognito (optionnel)",
        ],
        "Etat": [
            "Non connecte (DOCDB_URI defini)" if os.getenv("DOCDB_URI") else "Non connecte (placeholder)",
            "Non branche (placeholder)",
            "Non branche (placeholder)",
            "Non active",
        ],
    }
)

with st.expander("Test interactif (verifie que les WebSockets fonctionnent)"):
    st.write(
        "Si ce compteur s'incremente quand vous cliquez, la connexion WebSocket "
        "entre le navigateur et le serveur Streamlit fonctionne."
    )
    if "clicks" not in st.session_state:
        st.session_state.clicks = 0
    if st.button("Cliquer"):
        st.session_state.clicks += 1
    st.write(f"Nombre de clics : **{st.session_state.clicks}**")
