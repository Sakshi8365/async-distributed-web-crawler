import argparse
from collections import Counter
from pathlib import Path
import csv

import networkx as nx


def domain_of(url: str) -> str:
    from urllib.parse import urlparse
    try:
        host = urlparse(url).hostname or url
    except Exception:
        return url
    host = host.lower()
    if host.startswith("www."):
        host = host[4:]
    return host


def main():
    p = argparse.ArgumentParser(description="Export domain-level PNG from output/graph.csv")
    p.add_argument("--top-domains", type=int, default=80)
    p.add_argument("--min-weight", type=int, default=3)
    p.add_argument("--limit-edges", type=int, default=1200)
    args = p.parse_args()

    root = Path(__file__).resolve().parents[1]
    graph_csv = root / "output" / "graph.csv"
    if not graph_csv.exists():
        print(f"Missing file: {graph_csv}")
        return

    weights = Counter()
    with graph_csv.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            src = row.get("src"); dst = row.get("dst")
            if not src or not dst:
                continue
            a = domain_of(src); b = domain_of(dst)
            if a == b:
                continue
            weights[(a, b)] += 1

    if args.top_domains:
        deg = Counter()
        for (a, b), w in weights.items():
            deg[a] += w; deg[b] += w
        keep = set([d for d, _ in deg.most_common(args.top_domains)])
        weights = Counter({(a, b): w for (a, b), w in weights.items() if a in keep and b in keep})

    items = [(pair, w) for pair, w in weights.items() if w >= args.min_weight]
    items.sort(key=lambda x: x[1], reverse=True)
    if args.limit_edges:
        items = items[:args.limit_edges]

    G = nx.DiGraph()
    for (a, b), w in items:
        G.add_edge(a, b, weight=w)

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    pos = nx.spring_layout(G, k=0.6, iterations=60, seed=42)
    plt.figure(figsize=(14, 9), dpi=150)
    widths = [0.5 if d.get("weight", 1) <= 1 else 0.5 + min(4.0, (d.get("weight", 1) ** 0.5) * 0.6) for _, _, d in G.edges(data=True)]
    nx.draw_networkx_edges(G, pos, alpha=0.25, width=widths, arrows=False)
    nx.draw_networkx_nodes(G, pos, node_size=80, node_color="#3b82f6", alpha=0.85)
    labels = {n: n for n in G.nodes()}
    nx.draw_networkx_labels(G, pos, labels, font_size=7)
    plt.axis("off")
    plt.tight_layout()
    out = root / "output" / "graph_domain.png"
    plt.savefig(out.as_posix(), bbox_inches="tight")
    plt.close()
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
