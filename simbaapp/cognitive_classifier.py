"""
SIMBA — Classification cognitive en temps réel
================================================
Classe chaque message étudiant (role='user') dans les codes Dedoose définis
par Morgane pour le projet SIMBA (cf. SIMBACompilationTechnicalRepport +
Rapport technique du dashboard). Le résultat est stocké directement dans
Message.metadata['cognitive'], ce qui évite toute migration de base de
données.

Utilisation typique (voir hook dans api.py::create_message_api) :

    from . import cognitive_classifier
    cognitive_classifier.classify_message_async(str(message.id))

La classification tourne dans un thread daemon pour ne jamais bloquer la
réponse HTTP de création de message (donc ne jamais bloquer le chat).
"""

import json
import logging
import threading

from django.conf import settings
from openai import OpenAI

logger = logging.getLogger(__name__)

CLASSIFIER_MODEL = "gpt-4o-mini"

# ─── Codebook (Morgane, Dedoose) ─────────────────────────────────────────────
# Clés = mêmes noms courts que dans simba_dashboard.py / cognitive_scores.py
COGNITIVE_CODES = {
    "E": {
        "label": "Aide exécutive",
        "definition": (
            "L'étudiant demande à l'IA de réaliser la tâche à sa place "
            "(rédiger, résumer, reformuler directement à sa place)."
        ),
    },
    "I": {
        "label": "Aide instrumentale",
        "definition": (
            "L'étudiant demande une méthode, une stratégie ou une marche à suivre pour AGIR "
            "lui-même (comment faire, quelle approche utiliser), en gardant le contrôle de la "
            "production. Ne pas confondre avec Pb/Pp : si l'étudiant énonce seulement son "
            "objectif ou le sujet sans demander de méthode, ce n'est PAS I. "
            "Exemples positifs : « Comment structurer mon plan ? », « Quelle méthode utiliser "
            "pour comparer ces deux pays ? »."
        ),
    },
    "V": {
        "label": "Vérification d'erreur",
        "definition": (
            "L'étudiant signale, conteste ou corrige une erreur produite par "
            "l'IA (ex. « Non ce n'est pas ce que j'avais demandé », "
            "« Cette information est incorrecte »)."
        ),
    },
    "S": {
        "label": "Demande de sources",
        "definition": (
            "L'étudiant exige une référence ou une justification pour une "
            "affirmation produite par l'IA (ex. « D'où vient cette "
            "information ? », « Cite tes sources »)."
        ),
    },
    "A": {
        "label": "Accès à l'information",
        "definition": (
            "L'étudiant utilise l'IA comme outil de mesure factuelle sur sa "
            "propre production (ex. « Est-ce que ça fait 300 mots ? », "
            "« Le texte est bien structuré ? »)."
        ),
    },
    "Mb": {
        "label": "Monitoring — compréhension basique",
        "definition": (
            "L'étudiant vérifie s'il a bien compris UN SEUL fait ou UNE SEULE notion, de façon "
            "simple et immédiate, SANS aller plus loin (pas d'implication, pas de nuance, pas de "
            "raisonnement conditionnel). Si le message s'arrête à « c'est quoi / est-ce que j'ai "
            "bien compris X », c'est Mb, PAS Md. "
            "Exemples : « C'est quoi une externalité en gros ? », « Je n'ai pas bien compris "
            "cette partie, réexplique simplement. »"
        ),
    },
    "Md": {
        "label": "Monitoring — compréhension approfondie",
        "definition": (
            "L'étudiant va au-delà d'un simple fait : il teste une implication, une nuance, un "
            "lien logique, une exception, ou se demande si un raisonnement tiendrait dans un "
            "autre contexte. Signal fort : « si je comprends bien... alors », « est-ce que ça "
            "voudrait dire que », « dans quelle mesure », un raisonnement conditionnel/hypothétique. "
            "Ne mets PAS Md pour une simple demande de définition ou de ré-explication basique "
            "(c'est Mb dans ce cas). "
            "Exemples : « Si je comprends bien, cette cause agirait aussi en sens inverse ? », "
            "« Est-ce que ce raisonnement tiendrait encore dans un autre contexte historique ? »"
        ),
    },
    "Pb": {
        "label": "Définition des buts",
        "definition": (
            "L'étudiant exprime CE QU'IL VEUT accomplir ou produire lui-même : son objectif "
            "personnel, un livrable, une contrainte de forme/longueur/délai. Signal : « mon "
            "objectif », « je veux », « j'aimerais arriver à ». Ne PAS confondre avec Pp : Pb ne "
            "décrit jamais le sujet/l'énoncé donné par l'enseignant, seulement ce que l'étudiant "
            "vise. "
            "Exemples : « Mon objectif est d'avoir un plan en trois parties pour vendredi. », "
            "« Je veux que mon introduction fasse une demi-page. »"
        ),
    },
    "Pp": {
        "label": "Définition du problème",
        "definition": (
            "L'étudiant énonce ou reformule LE SUJET, L'ÉNONCÉ ou LA QUESTION DE RECHERCHE qui "
            "lui a été donné à traiter — ce qu'on lui DEMANDE de faire, pas ce que lui veut y "
            "arriver. Signal : « le sujet », « la question », « ce que je dois "
            "démontrer/traiter/comparer ». Si le message décrit l'énoncé du travail donné par "
            "l'enseignant, c'est Pp, PAS Pb, même s'il n'y a pas de contrainte de temps ou de "
            "forme. "
            "Exemples : « Le sujet me demande de comparer les causes de la révolution "
            "industrielle en France et en Angleterre. », « Le problème que je dois traiter, "
            "c'est l'impact de l'exode rural sur l'urbanisation. »"
        ),
    },
    "Am": {
        "label": "Amélioration des prompts",
        "definition": (
            "L'étudiant reformule ou affine volontairement sa propre "
            "requête pour obtenir une meilleure réponse (itération "
            "stratégique de prompt)."
        ),
    },
    "Cd": {
        "label": "Clarification approfondie",
        "definition": (
            "L'étudiant demande de CREUSER, DÉVELOPPER ou APPROFONDIR un point déjà abordé "
            "(plus de détails, de nuances, de développement sur un sujet déjà en discussion). "
            "Signal : « développer », « approfondir », « plus en détail/en profondeur ». Ne PAS "
            "utiliser Cd si l'étudiant demande juste de répéter ou reformuler parce qu'il n'a pas "
            "compris (c'est Cs dans ce cas, même si la phrase contient un mot comme « expliquer »). "
            "Exemples : « Peux-tu m'expliquer plus en profondeur pourquoi cette cause est la plus "
            "importante ? », « Tu peux développer davantage le lien entre ces deux phénomènes ? »"
        ),
    },
    "Cs": {
        "label": "Clarification simple",
        "definition": (
            "L'étudiant demande de RÉPÉTER ou REFORMULER un propos qu'il n'a PAS COMPRIS ou PAS "
            "ENTENDU — porte sur la forme/clarté du message précédent, pas sur un contenu à "
            "explorer davantage. Signal : « répète », « reformule », « qu'est-ce que tu veux dire "
            "par », « je n'ai pas compris ce mot/cette phrase ». Différence avec Cd : Cs porte sur "
            "un message déjà pas clair ; Cd porte sur un point déjà compris qu'on veut explorer "
            "plus loin. "
            "Exemples : « Tu peux répéter stp ? », « Qu'est-ce que tu veux dire par là ? »"
        ),
    },
}

_SYSTEM_PROMPT = f"""Tu es un classifieur linguistique pour un projet de recherche en \
learning analytics (SIMBA, IRIT). Tu reçois UN SEUL message tapé par un étudiant \
à un chatbot tuteur. Tu dois indiquer, pour chacun des 12 codes ci-dessous, s'il \
s'applique à ce message précis (true/false). Un message peut activer plusieurs \
codes, ou aucun.

Codes :
{json.dumps({k: v['definition'] for k, v in COGNITIVE_CODES.items()}, ensure_ascii=False, indent=2)}

Attention, ces paires de codes sont proches et souvent confondues — relis leur \
définition avant de répondre :
- Mb vs Md : Mb = un seul fait simple, sans aller plus loin. Md = implication, nuance, \
raisonnement conditionnel.
- Pb vs Pp : Pb = ce que L'ÉTUDIANT veut accomplir (son objectif). Pp = LE SUJET/ÉNONCÉ \
donné par l'enseignant.
- Cd vs Cs : Cs = redemander de répéter/reformuler un message pas clair. Cd = creuser \
plus loin un point déjà compris.

Réponds STRICTEMENT en JSON, avec une clé par code, valeur booléenne. Aucun \
texte hors JSON."""


def _get_client() -> OpenAI:
    api_key = getattr(settings, "OPENAI_API_KEY", None)
    return OpenAI(api_key=api_key) if api_key else OpenAI()


def classify_message_sync(content: str) -> dict:
    """
    Appelle GPT-4o-mini pour classifier un message étudiant. Retourne un dict
    {code: bool} pour les 12 codes du codebook. En cas d'erreur, retourne un
    dict tout à False (fail-safe, ne bloque jamais le pipeline de chat).
    """
    fallback = {code: False for code in COGNITIVE_CODES}
    if not content or not content.strip():
        return fallback

    try:
        client = _get_client()
        response = client.chat.completions.create(
            model=CLASSIFIER_MODEL,
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": f"Message étudiant : {content}"},
            ],
            max_tokens=300,
        )
        raw = response.choices[0].message.content
        parsed = json.loads(raw)
        result = {code: bool(parsed.get(code, False)) for code in COGNITIVE_CODES}
        return result
    except Exception as e:
        logger.error(f"[cognitive_classifier] Classification failed: {e}")
        return fallback


def classify_and_store(message_id: str) -> None:
    """
    Classifie un message déjà en base (par id) et fusionne le résultat dans
    Message.metadata['cognitive']. Conçu pour tourner en tâche de fond.
    """
    # Import local pour éviter les soucis de chargement circulaire d'apps Django
    from .models import Message

    try:
        message = Message.objects.get(id=message_id)
    except Message.DoesNotExist:
        logger.warning(f"[cognitive_classifier] Message {message_id} introuvable.")
        return

    codes = classify_message_sync(message.content)

    metadata = message.metadata or {}
    metadata["cognitive"] = codes
    message.metadata = metadata
    message.save(update_fields=["metadata"])
    logger.info(f"[cognitive_classifier] Message {message_id} classifié : {codes}")


def classify_message_async(message_id: str) -> None:
    """
    Lance classify_and_store dans un thread daemon pour ne jamais ralentir la 
    réponse HTTP de création de message (donc ne jamais bloquer le chat).

    NB pour une VM de prod avec plusieurs workers Gunicorn, un vrai système de 
    tâches (Celery/RQ) serait préférable à terme ; un thread suffit pour le 
    prototype et le volume actuel de SIMBA.
    """
    thread = threading.Thread(
        target=classify_and_store, args=(message_id,), daemon=True
    )
    thread.start()