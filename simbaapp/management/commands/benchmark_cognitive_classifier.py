"""
SIMBA — Benchmark du classifieur cognitif
==========================================
Mesure la précision réelle de cognitive_classifier.classify_message_sync()
sur un jeu de données étiqueté à la main (voir data/cognitive_benchmark_dataset.json).

Usage :
    python manage.py benchmark_cognitive_classifier
    python manage.py benchmark_cognitive_classifier --limit 20
    python manage.py benchmark_cognitive_classifier --verbose
    python manage.py benchmark_cognitive_classifier --output rapport.md

IMPORTANT : cette commande appelle réellement l'API OpenAI (GPT-4o-mini) pour
chaque message du jeu de test — elle a donc besoin d'une clé OPENAI_API_KEY
valide et d'un accès réseau à api.openai.com. Comptez environ 74 appels par
exécution complète (quelques centimes, en gpt-4o-mini).
"""

import json
import os
import time
from collections import defaultdict
from pathlib import Path

from django.core.management.base import BaseCommand

from simbaapp.cognitive_classifier import classify_message_sync, COGNITIVE_CODES

ALL_CODES = list(COGNITIVE_CODES.keys())  # ['E','I','V','S','A','Mb','Md','Pb','Pp','Am','Cd','Cs']

DATASET_PATH = os.path.join(os.path.dirname(__file__), "data", "cognitive_benchmark_dataset.json")


class Command(BaseCommand):
    help = "Benchmark le classifieur cognitif SIMBA (précision/rappel/F1 par code) sur un jeu de données étiqueté."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=None,
                             help="Ne tester que les N premiers exemples (pratique pour itérer vite / limiter le coût API).")
        parser.add_argument("--verbose", action="store_true",
                             help="Affiche chaque exemple mal classé (texte, attendu, prédit).")
        parser.add_argument("--output", type=str, default=None,
                             help="Chemin d'un fichier .md où écrire le rapport complet (en plus de la sortie console).")
        parser.add_argument("--json", type=str, default=None,
                             help="Chemin d'un fichier .json où écrire les métriques + résultats bruts "
                                  "(pratique pour tracer un graphique ensuite).")
        parser.add_argument("--dataset", type=str, default=DATASET_PATH,
                             help="Chemin vers un jeu de données JSON alternatif (même format).")

    def handle(self, *args, **options):
        dataset_path = options["dataset"]
        limit = options["limit"]
        verbose = options["verbose"]
        output_path = options["output"]

        with open(dataset_path, encoding="utf-8") as f:
            dataset = json.load(f)
        if limit:
            dataset = dataset[:limit]

        self.stdout.write(self.style.NOTICE(
            f"Benchmark du classifieur cognitif sur {len(dataset)} exemples "
            f"({dataset_path})...\n"
        ))

        # confusion[code] = {"tp":..,"fp":..,"fn":..,"tn":..}
        confusion = {code: {"tp": 0, "fp": 0, "fn": 0, "tn": 0} for code in ALL_CODES}
        exact_matches = 0
        hamming_correct = 0
        hamming_total = 0
        api_errors = 0
        mismatches = []  # for --verbose / report
        per_example_time = []

        for i, item in enumerate(dataset, start=1):
            text = item["text"]
            expected_raw = item.get("expected", {})
            expected = {code: bool(expected_raw.get(code, False)) for code in ALL_CODES}

            t0 = time.time()
            try:
                predicted = classify_message_sync(text)
            except Exception as e:
                api_errors += 1
                predicted = {code: False for code in ALL_CODES}
                self.stdout.write(self.style.ERROR(f"  [{item['id']}] Erreur API: {e}"))
            elapsed = time.time() - t0
            per_example_time.append(elapsed)

            example_correct = True
            for code in ALL_CODES:
                y_true = expected[code]
                y_pred = bool(predicted.get(code, False))
                hamming_total += 1
                if y_true == y_pred:
                    hamming_correct += 1
                else:
                    example_correct = False

                if y_true and y_pred:
                    confusion[code]["tp"] += 1
                elif not y_true and y_pred:
                    confusion[code]["fp"] += 1
                elif y_true and not y_pred:
                    confusion[code]["fn"] += 1
                else:
                    confusion[code]["tn"] += 1

            if example_correct:
                exact_matches += 1
            else:
                mismatches.append({
                    "id": item["id"], "text": text,
                    "expected": [c for c in ALL_CODES if expected[c]],
                    "predicted": [c for c in ALL_CODES if predicted.get(c)],
                })

            marker = self.style.SUCCESS("OK") if example_correct else self.style.WARNING("MISS")
            self.stdout.write(f"  [{i:>3}/{len(dataset)}] {item['id']:<5} {marker}  ({elapsed:.2f}s)")

        # ── Métriques agrégées ────────────────────────────────────────────
        per_code_metrics = {}
        macro_p, macro_r, macro_f1 = [], [], []
        for code in ALL_CODES:
            c = confusion[code]
            tp, fp, fn = c["tp"], c["fp"], c["fn"]
            precision = tp / (tp + fp) if (tp + fp) > 0 else float("nan")
            recall = tp / (tp + fn) if (tp + fn) > 0 else float("nan")
            f1 = (2 * precision * recall / (precision + recall)
                  if precision == precision and recall == recall and (precision + recall) > 0 else float("nan"))
            support = tp + fn
            per_code_metrics[code] = {
                "precision": precision, "recall": recall, "f1": f1, "support": support,
                "tp": tp, "fp": fp, "fn": fn,
            }
            if precision == precision:
                macro_p.append(precision)
            if recall == recall:
                macro_r.append(recall)
            if f1 == f1:
                macro_f1.append(f1)

        macro_precision = sum(macro_p) / len(macro_p) if macro_p else float("nan")
        macro_recall = sum(macro_r) / len(macro_r) if macro_r else float("nan")
        macro_f1_avg = sum(macro_f1) / len(macro_f1) if macro_f1 else float("nan")
        hamming_accuracy = hamming_correct / hamming_total if hamming_total else float("nan")
        exact_match_ratio = exact_matches / len(dataset) if dataset else float("nan")
        avg_latency = sum(per_example_time) / len(per_example_time) if per_example_time else 0

        # ── Rapport console ───────────────────────────────────────────────
        self.stdout.write("\n" + self.style.NOTICE("=" * 78))
        self.stdout.write(self.style.NOTICE("RÉSULTATS PAR CODE"))
        self.stdout.write(self.style.NOTICE("=" * 78))
        header = f"{'Code':<5}{'Label':<32}{'Précision':>10}{'Rappel':>10}{'F1':>8}{'Support':>9}"
        self.stdout.write(header)
        self.stdout.write("-" * len(header))
        for code in ALL_CODES:
            m = per_code_metrics[code]
            label = COGNITIVE_CODES[code]["label"][:31]
            p_str = f"{m['precision']:.2f}" if m['precision'] == m['precision'] else "n/a"
            r_str = f"{m['recall']:.2f}" if m['recall'] == m['recall'] else "n/a"
            f1_str = f"{m['f1']:.2f}" if m['f1'] == m['f1'] else "n/a"
            self.stdout.write(f"{code:<5}{label:<32}{p_str:>10}{r_str:>10}{f1_str:>8}{m['support']:>9}")

        self.stdout.write("\n" + self.style.NOTICE("RÉSUMÉ GLOBAL"))
        self.stdout.write(f"  Exemples testés          : {len(dataset)}")
        self.stdout.write(f"  Erreurs API               : {api_errors}")
        self.stdout.write(f"  Exact match (les 12 codes tous corrects) : {exact_match_ratio:.1%}")
        self.stdout.write(f"  Hamming accuracy (par code, en moyenne)  : {hamming_accuracy:.1%}")
        self.stdout.write(f"  Précision macro (moyenne sur les codes)  : {macro_precision:.2f}")
        self.stdout.write(f"  Rappel macro (moyenne sur les codes)     : {macro_recall:.2f}")
        self.stdout.write(f"  F1 macro (moyenne sur les codes)         : {macro_f1_avg:.2f}")
        self.stdout.write(f"  Latence moyenne / message                : {avg_latency:.2f}s")

        if mismatches:
            self.stdout.write("\n" + self.style.WARNING(f"{len(mismatches)} exemple(s) mal classé(s) :"))
            if verbose:
                for m in mismatches:
                    self.stdout.write(f"  [{m['id']}] \"{m['text']}\"")
                    self.stdout.write(f"        attendu  : {m['expected'] or '(aucun code)'}")
                    self.stdout.write(f"        prédit   : {m['predicted'] or '(aucun code)'}")
            else:
                self.stdout.write("  (relancez avec --verbose pour voir le détail de chaque erreur)")

        # ── Rapport Markdown (optionnel) ──────────────────────────────────
        if output_path:
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            self._write_markdown_report(output_path, dataset, per_code_metrics, exact_match_ratio,
                                         hamming_accuracy, macro_precision, macro_recall, macro_f1_avg,
                                         api_errors, avg_latency, mismatches)
            self.stdout.write(self.style.SUCCESS(f"\nRapport détaillé écrit dans {output_path}"))

        # ── Rapport JSON (optionnel) ───────────────────────────────────────
        if options["json"]:
            Path(options["json"]).parent.mkdir(parents=True, exist_ok=True)
            json_report = {
                "summary": {
                    "n_examples": len(dataset),
                    "api_errors": api_errors,
                    "exact_match_ratio": exact_match_ratio,
                    "hamming_accuracy": hamming_accuracy,
                    "macro_precision": macro_precision,
                    "macro_recall": macro_recall,
                    "macro_f1": macro_f1_avg,
                    "avg_latency_seconds": avg_latency,
                },
                "per_code": per_code_metrics,
                "mismatches": mismatches,
            }
            with open(options["json"], "w", encoding="utf-8") as f:
                json.dump(json_report, f, ensure_ascii=False, indent=2)
            self.stdout.write(self.style.SUCCESS(f"Résultats JSON écrits dans {options['json']}"))

    def _write_markdown_report(self, path, dataset, per_code_metrics, exact_match_ratio,
                                hamming_accuracy, macro_precision, macro_recall, macro_f1_avg,
                                api_errors, avg_latency, mismatches):
        lines = []
        lines.append("# Benchmark du classifieur cognitif SIMBA\n")
        lines.append(f"- Exemples testés : {len(dataset)}")
        lines.append(f"- Erreurs API : {api_errors}")
        lines.append(f"- Exact match (12 codes tous corrects) : {exact_match_ratio:.1%}")
        lines.append(f"- Hamming accuracy (par code, en moyenne) : {hamming_accuracy:.1%}")
        lines.append(f"- Précision macro : {macro_precision:.2f}")
        lines.append(f"- Rappel macro : {macro_recall:.2f}")
        lines.append(f"- F1 macro : {macro_f1_avg:.2f}")
        lines.append(f"- Latence moyenne / message : {avg_latency:.2f}s\n")
        lines.append("## Détail par code\n")
        lines.append("| Code | Label | Précision | Rappel | F1 | Support | FP | FN |")
        lines.append("|---|---|---|---|---|---|---|---|")
        for code, m in per_code_metrics.items():
            label = COGNITIVE_CODES[code]["label"]
            p_str = f"{m['precision']:.2f}" if m['precision'] == m['precision'] else "n/a"
            r_str = f"{m['recall']:.2f}" if m['recall'] == m['recall'] else "n/a"
            f1_str = f"{m['f1']:.2f}" if m['f1'] == m['f1'] else "n/a"
            lines.append(f"| {code} | {label} | {p_str} | {r_str} | {f1_str} | {m['support']} | {m['fp']} | {m['fn']} |")

        if mismatches:
            lines.append("\n## Exemples mal classés\n")
            for m in mismatches:
                lines.append(f"- **[{m['id']}]** \"{m['text']}\"")
                lines.append(f"  - attendu : {m['expected'] or '(aucun code)'}")
                lines.append(f"  - prédit : {m['predicted'] or '(aucun code)'}")

        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))