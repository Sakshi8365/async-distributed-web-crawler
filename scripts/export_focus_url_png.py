import argparse
from pathlib import Path
import csv
import networkx as nx


def domain_of(url: str) -> str:
    from urllib.parse import urlparse
    host = (urlparse(url).hostname or url).lower()
    if host.startswith("www."):
        host = host[4:]
    return host


def main():
    p = argparse.ArgumentParser(description="Export focused URL-level PNG from output/graph.csv")
    p.add_argument("--focus-domain", required=True)
    p.add_argument("--limit-edges", type=int, default=800)
    args = p.parse_args()

    root = Path(__file__).resolve().parents[1]
    graph_csv = root / "output" / "graph.csv"
    if not graph_csv.exists():
        print(f"Missing file: {graph_csv}")
        return

    G = nx.DiGraph()
    count = 0
    with graph_csv.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            src = row.get("src"); dst = row.get("dst")
            if not src or not dst:
                continue
            if domain_of(src) != args.focus_domain and domain_of(dst) != args.focus_domain:
                continue
            G.add_edge(src, dst)
            count += 1
            if count >= args.limit_edges:
                break

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    pos = nx.spring_layout(G, k=0.35, iterations=50, seed=7)
    plt.figure(figsize=(14, 9), dpi=150)
    nx.draw_networkx_edges(G, pos, alpha=0.25, arrows=False)
    nx.draw_networkx_nodes(G, pos, node_size=18, node_color="#2563eb", alpha=0.9)
    plt.axis("off")
    plt.tight_layout()
    out = root / "output" / f"graph_url_{args.focus_domain}.png"
    plt.savefig(out.as_posix(), bbox_inches="tight")
    plt.close()
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
