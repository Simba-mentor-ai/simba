"""
SIMBA — Calcul des indicateurs cognitifs (temps réel)
======================================================
Reprend exactement les formules validées dans simba_dashboard.py /
"Rapport technique du dashboard" (Walid, juin 2026), mais calculées à partir
des messages réellement échangés dans SIMBA (Message.metadata['cognitive'])
plutôt qu'à partir d'un export Dedoose statique.

Un message étudiant est considéré comme "actif" (compté dans N) dès lors
qu'il a été classifié par cognitive_classifier — ce qui est le cas de tout
message role='user' envoyé après l'activation du classifieur temps réel.
"""

from .models import Message, Thread, User, Activity, Course, CourseEnrollment

# ─── Seuils (identiques à simba_dashboard.py) ────────────────────────────────
GOOD, WARN, BAD = "good", "warn", "bad"


def reliance_status(v):
    if v is None:
        return WARN, "Pas encore de données"
    if v > 0.75:
        return BAD, "Forte dépendance"
    if v > 0.40:
        return WARN, "Dépendance modérée"
    return GOOD, "Usage autonome"


def ve_status(v):
    if v < 0.03:
        return BAD, "Aucune vigilance"
    if v < 0.08:
        return WARN, "Vigilance faible"
    return GOOD, "Vigilance active"


def vs_status(v):
    if v < 0.02:
        return BAD, "Aucune vérif. source"
    if v < 0.06:
        return WARN, "Vérif. source faible"
    return GOOD, "Vérif. source active"


def se_status(v):
    if v < 0.02:
        return BAD, "Aucune auto-éval."
    if v < 0.08:
        return WARN, "Auto-éval. limitée"
    return GOOD, "Auto-éval. active"


def pq_status(v):
    if v is None or v == 0:
        return WARN, "Aucune reformulation"
    if v < 0.05:
        return WARN, "Reformulation rare"
    return GOOD, "Itération stratégique"


# ─── Récupération des messages classifiés ────────────────────────────────────
def _classified_user_messages(user, activity=None, course=None):
    """
    Retourne le queryset des messages 'actifs' (role=user, déjà classifiés)
    d'un étudiant, filtré éventuellement par activité ou par cours.
    """
    qs = Message.objects.filter(thread__user=user, role="user")
    if activity is not None:
        qs = qs.filter(thread__activity=activity)
    elif course is not None:
        qs = qs.filter(thread__activity__course=course)
    return [m for m in qs if m.metadata and "cognitive" in m.metadata]


# ─── Calcul des indicateurs pour un étudiant ─────────────────────────────────
def compute_scores_for_student(user, activity=None, course=None) -> dict:
    """
    Calcule tous les indicateurs SIMBA pour un étudiant donné, à partir des
    messages déjà classifiés en base. Retourne un dict prêt à sérialiser en
    JSON pour l'API / le dashboard.
    """
    messages = _classified_user_messages(user, activity=activity, course=course)
    N = len(messages)

    counts = {code: 0 for code in ["E", "I", "V", "S", "A", "Mb", "Md", "Pb", "Pp", "Am", "Cd", "Cs"]}
    for m in messages:
        codes = m.metadata.get("cognitive", {})
        for k in counts:
            if codes.get(k):
                counts[k] += 1

    E, I, V, S, A = counts["E"], counts["I"], counts["V"], counts["S"], counts["A"]
    Mb, Md, Pb, Pp, Am = counts["Mb"], counts["Md"], counts["Pb"], counts["Pp"], counts["Am"]
    Cd, Cs = counts["Cd"], counts["Cs"]
    M = Mb + Md

    if N == 0:
        return {
            "has_data": False,
            "N": 0,
            "counts": counts,
        }

    reliance = E / (E + I) if (E + I) > 0 else None
    verif_epistemique = V / N
    verif_source = S / N
    verification = (V + S) / N
    selfeval = (A + M) / N
    winit = (Pb + Pp) / N
    prompt_qual = Am / N

    shallow = E + Cs + A
    deep = I + V + S + M + Am + Cd
    deep_ratio = deep / (shallow + deep) if (shallow + deep) > 0 else None

    r_lvl, r_txt = reliance_status(reliance)
    ve_lvl, ve_txt = ve_status(verif_epistemique)
    vs_lvl, vs_txt = vs_status(verif_source)
    se_lvl, se_txt = se_status(selfeval)
    pq_lvl, pq_txt = pq_status(prompt_qual)

    return {
        "has_data": True,
        "N": N,
        "counts": counts,
        "indicators": {
            "reliance": reliance,
            "verif_epistemique": verif_epistemique,
            "verif_source": verif_source,
            "verification": verification,
            "selfeval": selfeval,
            "winit": winit,
            "prompt_qual": prompt_qual,
            "deep_ratio": deep_ratio,
            "shallow": shallow,
            "deep": deep,
        },
        "status": {
            "reliance": {"level": r_lvl, "text": r_txt},
            "verif_epistemique": {"level": ve_lvl, "text": ve_txt},
            "verif_source": {"level": vs_lvl, "text": vs_txt},
            "selfeval": {"level": se_lvl, "text": se_txt},
            "prompt_qual": {"level": pq_lvl, "text": pq_txt},
        },
        # Radar 5 axes, normalisé [0,1] — mêmes bornes que simba_dashboard.py
        "radar": {
            "autonomie": 1.0 - reliance if reliance is not None else 0.5,
            "vigilance_epistemique": min(verif_epistemique / 0.20, 1.0),
            "verif_source": min(verif_source / 0.10, 1.0),
            "auto_evaluation": min(selfeval / 0.30, 1.0),
            "qualite_prompts": min(prompt_qual / 0.15, 1.0),
        },
    }


# ─── Comparaison de classe (percentile, sans exposer les autres étudiants) ───
def compute_class_percentile(user, activity=None, course=None) -> dict:
    """
    Calcule, pour l'indicateur clé "autonomie" (1 - reliance), la position en
    percentile de l'étudiant par rapport aux autres étudiants inscrits au
    même cours/activité. Ne retourne QUE le percentile de l'étudiant courant
    (jamais les scores nominatifs des autres étudiants), pour respecter la
    confidentialité des pairs.
    """
    if activity is not None:
        course = activity.course
    if course is None:
        return {"available": False}

    peer_ids = CourseEnrollment.objects.filter(
        course=course, role="student"
    ).values_list("user_id", flat=True)
    peers = User.objects.filter(id__in=peer_ids)

    autonomy_values = []
    my_autonomy = None
    for peer in peers:
        scores = compute_scores_for_student(peer, activity=activity, course=course)
        if not scores["has_data"]:
            continue
        reliance = scores["indicators"]["reliance"]
        if reliance is None:
            continue
        autonomy = 1.0 - reliance
        autonomy_values.append(autonomy)
        if peer.id == user.id:
            my_autonomy = autonomy

    if my_autonomy is None or len(autonomy_values) < 2:
        return {"available": False}

    below = sum(1 for v in autonomy_values if v < my_autonomy)
    percentile = round(100 * below / (len(autonomy_values) - 1)) if len(autonomy_values) > 1 else 50

    return {
        "available": True,
        "percentile": percentile,
        "class_size": len(autonomy_values),
        "median_autonomy": sorted(autonomy_values)[len(autonomy_values) // 2],
        "my_autonomy": my_autonomy,
    }
