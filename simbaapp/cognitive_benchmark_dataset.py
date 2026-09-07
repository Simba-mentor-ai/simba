"""
SIMBA — Jeu de données "fake" pour le benchmark du classifieur cognitif
========================================================================
Chaque exemple est un message étudiant plausible, annoté à la main avec les
codes attendus (ground truth), sur le même schéma que COGNITIVE_CODES dans
cognitive_classifier.py.

Objectif : mesurer la précision réelle du classifieur GPT-4o-mini AVANT de le
brancher sur de vrais étudiants (cf. Phase 1 du plan — données "fake").

Composition du jeu de données :
- ~5 exemples "purs" par code (un seul code attendu) → mesure la capacité de
  base du classifieur à reconnaître chaque comportement isolément.
- ~10 exemples combinés (2-3 codes attendus dans le même message) → mesure la
  capacité à détecter plusieurs comportements simultanés, ce qui arrive
  souvent en pratique.
- ~15 exemples négatifs (aucun code ne devrait s'activer) → mesure le taux de
  faux positifs, tout aussi important qu'un bon rappel.

Chaque entrée : {"id": str, "text": str, "expected": {code: bool, ...}}
"""

ALL_CODES = ["E", "I", "V", "S", "A", "Mb", "Md", "Pb", "Pp", "Am", "Cd", "Cs"]


def _labels(*active):
    """Construit un dict {code: bool} avec seulement les codes actifs à True."""
    return {code: (code in active) for code in ALL_CODES}


BENCHMARK_DATASET = [
    # ═══════════════════════ E — Aide exécutive ═══════════════════════
    {"id": "E-1", "text": "Peux-tu rédiger l'introduction à ma place ?", "expected": _labels("E")},
    {"id": "E-2", "text": "Écris-moi directement la conclusion de la dissertation.", "expected": _labels("E")},
    {"id": "E-3", "text": "Résume ce chapitre pour moi, j'ai la flemme de le lire.", "expected": _labels("E")},
    {"id": "E-4", "text": "Fais le plan détaillé complet à ma place, je le recopierai.", "expected": _labels("E")},
    {"id": "E-5", "text": "Reformule ce paragraphe pour que ça sonne mieux, écris-le entièrement.", "expected": _labels("E")},

    # ═══════════════════ I — Aide instrumentale ════════════════════════
    {"id": "I-1", "text": "Comment je devrais structurer mon plan en trois parties ?", "expected": _labels("I")},
    {"id": "I-2", "text": "Quelle méthode utiliser pour comparer ces deux pays ?", "expected": _labels("I")},
    {"id": "I-3", "text": "Comment tu ferais, toi, pour aborder cette partie du sujet ?", "expected": _labels("I")},
    {"id": "I-4", "text": "Est-ce qu'il vaut mieux commencer par les causes économiques ou sociales ?", "expected": _labels("I")},
    {"id": "I-5", "text": "Quelle est la meilleure façon de présenter des statistiques dans une dissertation ?", "expected": _labels("I")},

    # ═════════════════ V — Vérification d'erreur ═══════════════════════
    {"id": "V-1", "text": "Non, ce n'est pas ce que j'avais demandé, tu t'es trompé.", "expected": _labels("V")},
    {"id": "V-2", "text": "Je crois que cette date est fausse, la révolution industrielle anglaise a commencé plus tôt.", "expected": _labels("V")},
    {"id": "V-3", "text": "Cette information est incorrecte, ce n'est pas ce que dit mon cours.", "expected": _labels("V")},
    {"id": "V-4", "text": "Attends, tu confonds cause et conséquence dans ta réponse.", "expected": _labels("V")},
    {"id": "V-5", "text": "Je ne pense pas que ce chiffre soit le bon, peux-tu vérifier ?", "expected": _labels("V")},

    # ═══════════════════ S — Demande de sources ═════════════════════════
    {"id": "S-1", "text": "D'où vient cette information exactement ?", "expected": _labels("S")},
    {"id": "S-2", "text": "Peux-tu me donner tes sources pour cette affirmation ?", "expected": _labels("S")},
    {"id": "S-3", "text": "Cite-moi l'article ou le livre d'où ça vient stp.", "expected": _labels("S")},
    {"id": "S-4", "text": "Comment je peux vérifier que ce que tu dis est vrai ?", "expected": _labels("S")},
    {"id": "S-5", "text": "Est-ce que ce chiffre vient d'une étude officielle ?", "expected": _labels("S")},

    # ═════════════ A — Accès à l'information (auto-mesure) ══════════════
    {"id": "A-1", "text": "Est-ce que mon introduction fait bien 300 mots ?", "expected": _labels("A")},
    {"id": "A-2", "text": "Ma structure en trois parties est-elle bien équilibrée ?", "expected": _labels("A")},
    {"id": "A-3", "text": "Combien de paragraphes j'ai écrits jusqu'ici ?", "expected": _labels("A")},
    {"id": "A-4", "text": "Est-ce que mon texte respecte bien la limite de deux pages ?", "expected": _labels("A")},
    {"id": "A-5", "text": "Le nombre de citations que j'ai utilisées est-il suffisant ?", "expected": _labels("A")},

    # ═════════ Mb — Monitoring : compréhension basique ═══════════════════
    {"id": "Mb-1", "text": "Je ne comprends pas bien cette partie, tu peux réexpliquer plus simplement ?", "expected": _labels("Mb")},
    {"id": "Mb-2", "text": "C'est quoi une externalité négative en gros ?", "expected": _labels("Mb")},
    {"id": "Mb-3", "text": "Je n'ai pas bien saisi la différence entre les deux notions.", "expected": _labels("Mb")},
    {"id": "Mb-4", "text": "Est-ce que j'ai bien compris : la crise vient surtout de la surproduction ?", "expected": _labels("Mb")},
    {"id": "Mb-5", "text": "Peux-tu vérifier si j'ai bien compris le principe de base ?", "expected": _labels("Mb")},

    # ═══════ Md — Monitoring : compréhension approfondie ═════════════════
    {"id": "Md-1", "text": "Si je comprends bien, cette cause agirait aussi en sens inverse, c'est bien ça ?", "expected": _labels("Md")},
    {"id": "Md-2", "text": "Est-ce que ce raisonnement tiendrait encore si on change le contexte historique ?", "expected": _labels("Md")},
    {"id": "Md-3", "text": "Du coup, ça voudrait dire que les deux phénomènes sont liés bien plus profondément que je pensais ?", "expected": _labels("Md")},
    {"id": "Md-4", "text": "Est-ce que cette nuance remet en question toute la partie que j'ai déjà écrite ?", "expected": _labels("Md")},
    {"id": "Md-5", "text": "En creusant, est-ce que cette explication contredit celle que tu m'as donnée avant ?", "expected": _labels("Md")},

    # ═══════════════ Pb — Définition des buts ═══════════════════════════
    {"id": "Pb-1", "text": "Mon objectif est d'avoir un plan complet en trois parties pour vendredi.", "expected": _labels("Pb")},
    {"id": "Pb-2", "text": "Je veux que mon introduction fasse à peu près une demi-page.", "expected": _labels("Pb")},
    {"id": "Pb-3", "text": "Mon but aujourd'hui c'est de finir la partie sur les causes économiques.", "expected": _labels("Pb")},
    {"id": "Pb-4", "text": "J'aimerais arriver à un raisonnement clair et bien structuré d'ici ce soir.", "expected": _labels("Pb")},
    {"id": "Pb-5", "text": "Ce que je veux, c'est comprendre le sujet avant de commencer à écrire.", "expected": _labels("Pb")},

    # ═══════════════ Pp — Définition du problème ═════════════════════════
    {"id": "Pp-1", "text": "Le sujet me demande de comparer les causes de la révolution industrielle en France et en Angleterre.", "expected": _labels("Pp")},
    {"id": "Pp-2", "text": "Le problème que je dois traiter, c'est l'impact de l'exode rural sur l'urbanisation.", "expected": _labels("Pp")},
    {"id": "Pp-3", "text": "En gros, ma question de recherche est : pourquoi cette crise a-t-elle eu lieu à ce moment précis ?", "expected": _labels("Pp")},
    {"id": "Pp-4", "text": "Ce que je dois démontrer, c'est le lien entre ces deux événements historiques.", "expected": _labels("Pp")},
    {"id": "Pp-5", "text": "Le sujet porte sur les conséquences sociales de l'industrialisation.", "expected": _labels("Pp")},

    # ═══════════════ Am — Amélioration des prompts ═══════════════════════
    {"id": "Am-1", "text": "En fait laisse-moi reformuler ma question plus précisément : quelles sont les causes démographiques ?", "expected": _labels("Am")},
    {"id": "Am-2", "text": "Je vais être plus précis dans ma demande : je veux seulement les causes économiques, pas sociales.", "expected": _labels("Am")},
    {"id": "Am-3", "text": "Pour être plus clair, voici une meilleure version de ma question précédente.", "expected": _labels("Am")},
    {"id": "Am-4", "text": "Je reformule : au lieu de 'explique-moi', je voudrais que tu me poses des questions.", "expected": _labels("Am")},
    {"id": "Am-5", "text": "Attends je précise ma demande initiale, j'étais trop vague.", "expected": _labels("Am")},

    # ═══════════════ Cd — Clarification approfondie ══════════════════════
    {"id": "Cd-1", "text": "Peux-tu m'expliquer plus en profondeur pourquoi cette cause est considérée comme la plus importante ?", "expected": _labels("Cd")},
    {"id": "Cd-2", "text": "Est-ce que tu peux développer davantage le lien entre ces deux phénomènes ?", "expected": _labels("Cd")},
    {"id": "Cd-3", "text": "J'aimerais une explication plus détaillée des mécanismes économiques en jeu.", "expected": _labels("Cd")},
    {"id": "Cd-4", "text": "Tu peux approfondir pourquoi cette théorie est contestée par certains historiens ?", "expected": _labels("Cd")},
    {"id": "Cd-5", "text": "Peux-tu creuser un peu plus la nuance entre ces deux notions proches ?", "expected": _labels("Cd")},

    # ═══════════════ Cs — Clarification simple ═══════════════════════════
    {"id": "Cs-1", "text": "Tu peux répéter stp ?", "expected": _labels("Cs")},
    {"id": "Cs-2", "text": "Qu'est-ce que tu veux dire par là ?", "expected": _labels("Cs")},
    {"id": "Cs-3", "text": "Tu peux reformuler ta dernière phrase, j'ai pas compris.", "expected": _labels("Cs")},
    {"id": "Cs-4", "text": "C'est quoi le mot que tu viens d'utiliser ?", "expected": _labels("Cs")},
    {"id": "Cs-5", "text": "Pardon, tu peux redire ça autrement ?", "expected": _labels("Cs")},

    # ═════════════════ Exemples combinés (2-3 codes) ═════════════════════
    {"id": "combo-1", "text": "Non ce n'est pas correct, et en plus d'où vient cette affirmation ? Tu as une source ?",
     "expected": _labels("V", "S")},
    {"id": "combo-2", "text": "Je vais reformuler ma question : comment structurer mon plan en trois parties pour respecter mon objectif de vendredi ?",
     "expected": _labels("Am", "I", "Pb")},
    {"id": "combo-3", "text": "Le sujet porte sur l'exode rural, et mon objectif est de finir l'intro ce soir. Comment je m'y prends ?",
     "expected": _labels("Pp", "Pb", "I")},
    {"id": "combo-4", "text": "Attends, je ne comprends pas bien cette partie, et en creusant, est-ce que ça remettrait en cause tout mon raisonnement ?",
     "expected": _labels("Mb", "Md")},
    {"id": "combo-5", "text": "Cette date me semble fausse, tu peux me dire d'où tu la sors ?",
     "expected": _labels("V", "S")},
    {"id": "combo-6", "text": "Est-ce que mon texte fait bien 300 mots, et est-ce que ma structure en trois parties tient la route ?",
     "expected": _labels("A")},
    {"id": "combo-7", "text": "Pour préciser ma demande : peux-tu m'expliquer plus en profondeur le mécanisme économique derrière cette crise ?",
     "expected": _labels("Am", "Cd")},
    {"id": "combo-8", "text": "Je ne suis pas sûr d'avoir compris, tu peux répéter simplement ce que tu viens de dire ?",
     "expected": _labels("Mb", "Cs")},
    {"id": "combo-9", "text": "Mon but est de bien cerner le sujet, qui porte sur les conséquences sociales de l'industrialisation. Tu peux m'aider à y voir plus clair ?",
     "expected": _labels("Pb", "Pp")},
    {"id": "combo-10", "text": "Non, je pense que tu te trompes sur ce point, et j'aimerais que tu développes davantage ton raisonnement.",
     "expected": _labels("V", "Cd")},

    # ═════════════════ Exemples négatifs (aucun code) ═════════════════════
    {"id": "neg-1", "text": "Bonjour, merci pour ton aide !", "expected": _labels()},
    {"id": "neg-2", "text": "D'accord, je vais faire ça.", "expected": _labels()},
    {"id": "neg-3", "text": "Voici mon texte : l'exode rural a débuté au XIXe siècle avec la mécanisation agricole.", "expected": _labels()},
    {"id": "neg-4", "text": "Ok super, merci beaucoup pour ta réponse.", "expected": _labels()},
    {"id": "neg-5", "text": "Je vais continuer à rédiger ma partie maintenant.", "expected": _labels()},
    {"id": "neg-6", "text": "Très bien, je note ça.", "expected": _labels()},
    {"id": "neg-7", "text": "Ça marche, à plus tard.", "expected": _labels()},
    {"id": "neg-8", "text": "Le sujet parle de l'urbanisation au XIXe siècle en Europe.", "expected": _labels()},
    {"id": "neg-9", "text": "Je continue sur ma lancée, merci.", "expected": _labels()},
    {"id": "neg-10", "text": "Parfait, j'avance bien du coup.", "expected": _labels()},
    {"id": "neg-11", "text": "Ah super, ça m'aide beaucoup pour la suite.", "expected": _labels()},
    {"id": "neg-12", "text": "Je vais passer à la partie suivante maintenant.", "expected": _labels()},
    {"id": "neg-13", "text": "Merci, c'est noté, je continue.", "expected": _labels()},
    {"id": "neg-14", "text": "Je pense avoir fini cette partie, je passe à la suite.", "expected": _labels()},
    {"id": "neg-15", "text": "Cool, ça me semble clair, merci !", "expected": _labels()},
]


def dataset_stats():
    """Petit résumé de la composition du jeu de données (nombre d'exemples par code)."""
    from collections import Counter
    counter = Counter()
    for ex in BENCHMARK_DATASET:
        for code, active in ex["expected"].items():
            if active:
                counter[code] += 1
    return {
        "total_examples": len(BENCHMARK_DATASET),
        "positive_per_code": dict(counter),
        "negative_examples": sum(1 for ex in BENCHMARK_DATASET if not any(ex["expected"].values())),
    }


if __name__ == "__main__":
    import json
    print(json.dumps(dataset_stats(), indent=2, ensure_ascii=False))
