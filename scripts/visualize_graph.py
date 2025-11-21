import csv
import os
import sys
from pathlib import Path

from pyvis.network import Network
import networkx as nx


def main():
    root = Path(__file__).resolve().parents[1]
    graph_csv = root / "output" / "graph.csv"
    if not graph_csv.exists():
        print(f"Missing file: {graph_csv}. Run a crawl first.")
        sys.exit(1)

    net = Network(height="800px", width="100%", directed=True, notebook=False)
    net.barnes_hut(gravity=-2000, spring_length=150)

    # Limit for performance in browser
    import argparse
    import csv
    import sys
    from collections import Counter, defaultdict
    from pathlib import Path
    from urllib.parse import urlparse

    from pyvis.network import Network


    def domain_of(url: str) -> str:
        try:
            host = urlparse(url).hostname or url
        except Exception:
            return url
        host = host.lower()
        if host.startswith("www."):
            host = host[4:]
        return host


    def load_edges(graph_csv: Path, focus_domain: str | None = None, limit: int | None = None):
        count = 0
        with graph_csv.open("r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                src = row.get("src")
                dst = row.get("dst")
                if not src or not dst:
                    continue
                if focus_domain:
                    dsrc = domain_of(src)
                    ddst = domain_of(dst)
                    if dsrc != focus_domain and ddst != focus_domain:
                        continue
                yield src, dst
                count += 1
                if limit and count >= limit:
                    break


    def build_url_graph(net: Network, graph_csv: Path, focus_domain: str | None, max_edges: int, physics: bool):
        nodes_seen = set()
        edges = 0
        for src, dst in load_edges(graph_csv, focus_domain=focus_domain, limit=max_edges):
            if src not in nodes_seen:
                net.add_node(src, label=src, shape="dot")
                nodes_seen.add(src)
            if dst not in nodes_seen:
                net.add_node(dst, label=dst, shape="dot")
                nodes_seen.add(dst)
            net.add_edge(src, dst)
            edges += 1
        if not physics:
            net.set_options("""
            const options = {
              physics: { enabled: false },
              interaction: { hover: true, dragNodes: true },
              nodes: { size: 8 },
              edges: { arrows: { to: { enabled: true } }, smooth: { type: 'continuous' } }
            };
            """)
        return edges, len(nodes_seen)


    def build_domain_graph(net: Network, graph_csv: Path, focus_domain: str | None, min_weight: int, max_edges: int, physics: bool, top_domains: int | None = None):
        weights = Counter()
        for src, dst in load_edges(graph_csv, focus_domain=focus_domain, limit=None):
            dsrc = domain_of(src)
            ddst = domain_of(dst)
            if dsrc == ddst:
                continue
            weights[(dsrc, ddst)] += 1

        # Rank domains by weighted degree if requested
        if top_domains:
            deg = Counter()
            for (a, b), w in weights.items():
                deg[a] += w
                deg[b] += w
            keep = set([d for d, _ in deg.most_common(top_domains)])
            weights = Counter({(a, b): w for (a, b), w in weights.items() if a in keep and b in keep})

        # Filter by weight and limit edges
        items = [(pair, w) for pair, w in weights.items() if w >= min_weight]
        items.sort(key=lambda x: x[1], reverse=True)
        if max_edges:
            items = items[:max_edges]

        nodes_seen = set()
        for (dsrc, ddst), w in items:
            if dsrc not in nodes_seen:
                net.add_node(dsrc, label=dsrc, shape="dot")
                nodes_seen.add(dsrc)
            if ddst not in nodes_seen:
                net.add_node(ddst, label=ddst, shape="dot")
                nodes_seen.add(ddst)
            net.add_edge(dsrc, ddst, value=w, title=f"weight={w}")

        if not physics:
            net.set_options("""
            const options = {
              physics: { enabled: false },
              interaction: { hover: true, dragNodes: true },
              nodes: { size: 12 },
              edges: { arrows: { to: { enabled: true } }, smoothing: true }
            };
            """)
        return len(items), len(nodes_seen)


    def main():
        parser = argparse.ArgumentParser(description="Visualize crawl graph")
        parser.add_argument("--mode", choices=["url", "domain"], default="url", help="Render raw URL graph or aggregated domain graph")
        parser.add_argument("--focus-domain", default=None, help="Only include edges where src or dst matches this domain")
        parser.add_argument("--limit-edges", type=int, default=2000, help="Max edges to include (URL mode). Domain mode also respects this after filtering.")
        parser.add_argument("--min-weight", type=int, default=2, help="Domain mode: minimum edge weight to include")
        parser.add_argument("--no-physics", action="store_true", help="Disable physics for lighter rendering")
        parser.add_argument("--top-domains", type=int, default=100, help="Domain mode: keep only the top-N domains by weighted degree")
        parser.add_argument("--export-png", action="store_true", help="Also export a static PNG for quick viewing")
        parser.add_argument("--loader", choices=["default", "minimal", "none"], default="minimal", help="Loading bar style")
        args = parser.parse_args()

        root = Path(__file__).resolve().parents[1]
        graph_csv = root / "output" / "graph.csv"
        if not graph_csv.exists():
            print(f"Missing file: {graph_csv}. Run a crawl first.")
            sys.exit(1)

        net = Network(height="800px", width="100%", directed=True, notebook=False)
        if not args.no_physics:
            net.barnes_hut(gravity=-2000, spring_length=150)

        if args.mode == "url":
            edges, nodes = build_url_graph(net, graph_csv, focus_domain=args.focus_domain, max_edges=args.limit_edges, physics=not args.no_physics)
            out_name = "graph_url.html"
        else:
            edges, nodes = build_domain_graph(
                net,
                graph_csv,
                focus_domain=args.focus_domain,
                min_weight=args.min_weight,
                max_edges=args.limit_edges,
                physics=not args.no_physics,
                top_domains=args.top_domains,
            )
            out_name = "graph_domain.html"

        out_dir = root / "output"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_html = out_dir / out_name

        # First write HTML with local assets using pyvis' safe path
        net.write_html(out_html.as_posix(), open_browser=False, notebook=False, local=True)

        # Optionally restyle the loader by in-place HTML patching
        if args.loader != "default":
            try:
                with open(out_html, "r", encoding="utf-8") as f:
                    html = f.read()
                if args.loader == "none":
                    override = """
                    <style id=\"loader-override\">#loadingBar{display:none!important}</style>
                    """
                else:
                    override = """
                    <style id=\"loader-override\">
                    #loadingBar{position:absolute;left:50%;top:20px;transform:translateX(-50%);background:transparent;box-shadow:none;width:260px}
                    #loadingBar .outerBorder{border:1px solid #e5e7eb;border-radius:8px;padding:2px;background:#fff}
                    #loadingBar #border{background:#f3f4f6;border-radius:6px;height:12px}
                    #loadingBar #bar{background:linear-gradient(90deg,#3b82f6,#06b6d4);height:12px;border-radius:6px}
                    #loadingBar #text{position:absolute;right:-44px;top:-2px;font:12px system-ui,Segoe UI,Arial;color:#374151}
                    </style>
                    """
                if "</head>" in html:
                    html = html.replace("</head>", f"{override}</head>")
                    with open(out_html, "w", encoding="utf-8") as f:
                        f.write(html)
            except Exception:
                pass

        print(f"Wrote {out_html} (edges: {edges}, nodes: {nodes}, mode: {args.mode}, loader: {args.loader})")

        # Optional: static PNG export for very large graphs
        if args.export_png:
            png_path = out_dir / ("graph_domain.png" if args.mode == "domain" else "graph_url.png")
            try:
                if args.mode == "domain":
                    # Rebuild domain items similarly to HTML pass for PNG
                    weights = Counter()
                    for src, dst in load_edges(graph_csv, focus_domain=args.focus_domain, limit=None):
                        a = domain_of(src)
                        b = domain_of(dst)
                        if a == b:
                            continue
                        weights[(a, b)] += 1
                    if args.top_domains:
                        deg = Counter()
                        for (a, b), w in weights.items():
                            deg[a] += w
                            deg[b] += w
                        keep = set([d for d, _ in deg.most_common(args.top_domains)])
                        weights = Counter({(a, b): w for (a, b), w in weights.items() if a in keep and b in keep})
                    items = [(pair, w) for pair, w in weights.items() if w >= args.min_weight]
                    items.sort(key=lambda x: x[1], reverse=True)
                    if args.limit_edges:
                        items = items[:args.limit_edges]
                    G = nx.DiGraph()
                    for (a, b), w in items:
                        G.add_edge(a, b, weight=w)
                else:
                    # URL graph PNG limited to given edges
                    G = nx.DiGraph()
                    for src, dst in load_edges(graph_csv, focus_domain=args.focus_domain, limit=args.limit_edges):
                        G.add_edge(src, dst)

                # Compute layout and draw
                pos = nx.spring_layout(G, k=0.45, iterations=50, seed=42)
                import matplotlib
                matplotlib.use("Agg")
                import matplotlib.pyplot as plt

                plt.figure(figsize=(14, 9), dpi=150)
                # Edge widths by log(weight)
                widths = []
                for u, v, d in G.edges(data=True):
                    w = d.get("weight", 1)
                    widths.append(0.5 if w <= 1 else 0.5 + min(4.0, (w ** 0.5) * 0.6))
                nx.draw_networkx_edges(G, pos, alpha=0.25, width=widths, arrows=False)
                nx.draw_networkx_nodes(G, pos, node_size=20 if args.mode == "url" else 80, node_color="#3b82f6", alpha=0.8)
                if args.mode == "domain":
                    labels = {n: n for n in G.nodes()}
                    nx.draw_networkx_labels(G, pos, labels, font_size=7)
                plt.axis("off")
                plt.tight_layout()
                plt.savefig(png_path.as_posix(), bbox_inches="tight")
                plt.close()
                print(f"Also wrote {png_path}")
            except Exception as e:
                print(f"PNG export failed: {e}")
