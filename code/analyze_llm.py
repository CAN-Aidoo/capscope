"""Summarise Q4 runs: python analyze_llm.py runs/summary_<model>_<defense>.json ...  ->  results/llm.json

Per defense: benign utility, utility under attack, attack success rate (ASR), each with a bootstrap 95% CI
over user tasks (pairs sharing a user task are not independent); model calls, tokens and seconds per task.
Paired comparison vs 'none': difference in ASR and in benign utility, bootstrap over user tasks.
"""
import json
import os
import sys

import numpy as np

rng = np.random.default_rng(0)
B = 10000


def per_user(d, key):
    """{(suite,user): [0/1,...]} for pair-level results; benign results are one value per user."""
    out = {}
    for s, r in d["suites"].items():
        for k, v in r[key].items():
            u = k.split("|")[0]
            if not u.startswith("user_task"):
                continue
            out.setdefault((s, u), []).append(int(v))
    return out


def rate_ci(groups, keys):
    num = np.array([sum(groups[k]) for k in keys]); den = np.array([len(groups[k]) for k in keys])
    idx = rng.integers(0, len(keys), size=(B, len(keys)))
    boots = num[idx].sum(1) / den[idx].sum(1)
    return float(num.sum() / den.sum()), [float(np.percentile(boots, 2.5)), float(np.percentile(boots, 97.5))], int(den.sum())


def diff_ci(ga, gb, keys):
    a_num = np.array([sum(ga[k]) for k in keys]); b_num = np.array([sum(gb[k]) for k in keys])
    den = np.array([len(ga[k]) for k in keys])
    idx = rng.integers(0, len(keys), size=(B, len(keys)))
    boots = (a_num[idx].sum(1) - b_num[idx].sum(1)) / den[idx].sum(1)
    return float((a_num.sum() - b_num.sum()) / den.sum()), [float(np.percentile(boots, 2.5)), float(np.percentile(boots, 97.5))]


runs = {json.load(open(p))["defense"]: json.load(open(p)) for p in sys.argv[1:]}
res = {}
for dname, d in runs.items():
    tasks = sum(len(r["benign_utility"]) + len(r["attack_success"]) for r in d["suites"].values())
    u = d["usage"]
    g = {k: per_user(d, k) for k in ("benign_utility", "attacked_utility", "attack_success")}
    keys = sorted(g["attack_success"])
    res[dname] = {m: dict(zip(("rate", "ci", "n"), rate_ci(g[m], sorted(g[m])))) for m in g}
    res[dname]["per_suite_asr"] = {s: sum(r["attack_success"].values()) / max(1, len(r["attack_success"]))
                                   for s, r in d["suites"].items()}
    res[dname]["usage_per_task"] = {"model_calls": (u["calls"] + u["filter_calls"]) / tasks,
                                    "input_tokens": u["input_tokens"] / tasks, "seconds": u["seconds"] / tasks}
    if dname != "none" and "none" in runs:
        g0 = {k: per_user(runs["none"], k) for k in ("benign_utility", "attack_success")}
        common = sorted(set(keys) & set(g0["attack_success"]))
        res[dname]["asr_minus_none"] = diff_ci(g["attack_success"], g0["attack_success"], common)
        cb = sorted(set(g["benign_utility"]) & set(g0["benign_utility"]))
        res[dname]["benign_utility_minus_none"] = diff_ci(g["benign_utility"], g0["benign_utility"], cb)
os.makedirs("results", exist_ok=True)
json.dump(res, open("results/llm.json", "w"), indent=1)
for k, v in res.items():
    print(k, {m: round(v[m]["rate"], 3) for m in ("benign_utility", "attacked_utility", "attack_success")},
          {m: round(x, 2) for m, x in v["usage_per_task"].items()})
