"""
SIMBA — Trace un graphique à partir des résultats du benchmark
=================================================================
Usage (après avoir lancé le benchmark avec --json) :

    python manage.py benchmark_cognitive_classifier --json benchmark_results/resultats.json
    python simbaapp/scripts/plot_benchmark_results.py benchmark_results/resultats.json

Génère un PNG (précision/rappel/F1 par code, palette SIMBA orange/blanc) prêt à
coller dans un rapport.

Ce script est volontairement indépendant de Django (pas d'import simbaapp) pour
pouvoir tourner n'importe où, y compris hors du serveur SIMBA.
"""
import sys
import json

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ORANGE = "#d64000"
ORANGE_LIGHT = "#ff7043"
DARK = "#333333"
GREY = "#aaaaaa"


def plot_benchmark(json_path, output_png=None):
    with open(json_path, encoding="utf-8") as f:
        data = json.load(f)

    per_code = data["per_code"]
    codes = list(per_code.keys())
    precision = [per_code[c]["precision"] for c in codes]
    recall = [per_code[c]["recall"] for c in codes]
    f1 = [per_code[c]["f1"] for c in codes]

    x = np.arange(len(codes))
    width = 0.26

    fig, ax = plt.subplots(figsize=(11, 5.5), dpi=200)
    ax.bar(x - width, precision, width, label="Précision", color=ORANGE_LIGHT)
    ax.bar(x, recall, width, label="Rappel", color=ORANGE)
    ax.bar(x + width, f1, width, label="F1", color="#ac3300")

    ax.set_xticks(x)
    ax.set_xticklabels(codes, fontsize=10, color=DARK)
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("Score", color=DARK)
    ax.legend(frameon=False, fontsize=9)
    ax.spines[['top', 'right']].set_visible(False)
    ax.grid(axis='y', color="#eeeeee", linewidth=0.8)
    ax.set_axisbelow(True)

    summary = data.get("summary", {})
    subtitle = (f"F1 macro = {summary.get('macro_f1', 0):.2f} · "
                f"Exact-match = {summary.get('exact_match_ratio', 0):.0%} · "
                f"{summary.get('n_examples', '?')} exemples testés")
    ax.set_title("SIMBA — Précision du classifieur cognitif par code\n" + subtitle,
                 fontsize=12.5, color=ORANGE, fontweight="bold", loc="left")

    plt.tight_layout()
    output_png = output_png or json_path.replace(".json", "") + "_chart.png"
    plt.savefig(output_png, facecolor="white")
    print(f"Graphique écrit dans {output_png}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python plot_benchmark_results.py <resultats.json> [sortie.png]")
        sys.exit(1)
    plot_benchmark(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
