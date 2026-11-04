import json
import subprocess
from collections import Counter
from datetime import date, timedelta
from pathlib import Path
from xml.sax.saxutils import escape

user = "owainxyz"
out = Path(__file__).parent

bg = "#0d1117"
border = "#30363d"
fg = "#e6edf3"
muted = "#8b949e"
accent = "#2f81f7"
greens = ["#161b22", "#0e4429", "#006d32", "#26a641", "#39d353"]
langColors = {
    "Python": "#3572A5", "C++": "#f34b7d", "C": "#555555", "Shell": "#89e051",
    "Nix": "#7e7eff", "CSS": "#663399", "HTML": "#e34c26", "TypeScript": "#3178c6",
}
font = "-apple-system,BlinkMacSystemFont,'Segoe UI','Noto Sans',Helvetica,Arial,sans-serif"
mono = "ui-monospace,SFMono-Regular,'SF Mono',Menlo,Consolas,'Liberation Mono',monospace"


def gh(*args):
    return subprocess.run(["gh", "api", *args], capture_output=True, text=True, check=True).stdout


def graphql(query):
    return json.loads(gh("graphql", "-f", f"query={query}"))["data"]


def traffic(repo, kind):
    try:
        return json.loads(gh(f"repos/{user}/{repo}/traffic/{kind}"))
    except subprocess.CalledProcessError:
        return {"count": 0, "uniques": 0}


def card(width, height, title, body):
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">'
        f'<style>text{{font-family:{font};fill:{fg}}} .m{{fill:{muted}}} .mono{{font-family:{mono}}}</style>'
        f'<rect x="0.5" y="0.5" width="{width - 1}" height="{height - 1}" rx="6" fill="{bg}" stroke="{border}"/>'
        f'<text x="20" y="32" font-size="15" font-weight="600">{escape(title)}</text>'
        f"{body}</svg>"
    )


def human(n):
    if n >= 1000:
        return f"{n / 1000:.1f}k".replace(".0k", "k")
    return str(n)


def tiles(items, x0, y0, width, h=64):
    w = (width - 10 * (len(items) - 1)) / len(items)
    s = ""
    for i, (label, value) in enumerate(items):
        x = x0 + i * (w + 10)
        s += f'<rect x="{x:.1f}" y="{y0}" width="{w:.1f}" height="{h}" rx="6" fill="#161b22" stroke="{border}"/>'
        s += f'<text x="{x + 14:.1f}" y="{y0 + 30}" font-size="22" font-weight="600">{escape(str(value))}</text>'
        s += f'<text x="{x + 14:.1f}" y="{y0 + 50}" font-size="12" class="m">{escape(label)}</text>'
    return s


def langBar(sizes, x, y, width, legendCols=4):
    total = sum(sizes.values()) or 1
    s = f'<clipPath id="bar"><rect x="{x}" y="{y}" width="{width}" height="8" rx="4"/></clipPath><g clip-path="url(#bar)">'
    cx = x
    ordered = sorted(sizes.items(), key=lambda kv: -kv[1])
    for name, size in ordered:
        w = width * size / total
        s += f'<rect x="{cx:.2f}" y="{y}" width="{w + 0.5:.2f}" height="8" fill="{langColors.get(name, muted)}"/>'
        cx += w
    s += "</g>"
    colW = width / legendCols
    for i, (name, size) in enumerate(ordered):
        lx = x + (i % legendCols) * colW
        ly = y + 30 + (i // legendCols) * 22
        s += f'<circle cx="{lx + 5}" cy="{ly - 4}" r="5" fill="{langColors.get(name, muted)}"/>'
        s += f'<text x="{lx + 16}" y="{ly}" font-size="12">{escape(name)} <tspan class="m">{100 * size / total:.1f}%</tspan></text>'
    return s, 30 + ((len(ordered) - 1) // legendCols) * 22


data = graphql(
    f'{{user(login:"{user}"){{followers{{totalCount}} contributionsCollection{{totalCommitContributions '
    "totalPullRequestContributions contributionCalendar{totalContributions weeks{contributionDays{date contributionCount}}}} "
    "repositories(first:100,ownerAffiliations:OWNER,privacy:PUBLIC){totalCount nodes{name stargazerCount "
    "languages(first:10){edges{size node{name}}}}}}}"
)["user"]
contrib = data["contributionsCollection"]
calendar = contrib["contributionCalendar"]
repos = {r["name"]: r for r in data["repositories"]["nodes"]}
stars = sum(r["stargazerCount"] for r in repos.values())

overview = tiles(
    [
        ("contributions", human(calendar["totalContributions"])),
        ("commits", human(contrib["totalCommitContributions"])),
        ("pull requests", contrib["totalPullRequestContributions"]),
        ("public repos", data["repositories"]["totalCount"]),
        ("stars", stars),
        ("followers", data["followers"]["totalCount"]),
    ],
    20, 52, 800,
)
(out / "overview.svg").write_text(card(840, 136, "github stats", overview))

weeks = calendar["weeks"]
cell, gap = 11, 3
gx, gy = 48, 62
grid = ""
counts = sorted(d["contributionCount"] for w in weeks for d in w["contributionDays"] if d["contributionCount"])
qs = [counts[int(len(counts) * q)] for q in (0.25, 0.5, 0.75)] if counts else [1, 2, 3]
monthSeen = set()
for wi, week in enumerate(weeks):
    for d in week["contributionDays"]:
        day = date.fromisoformat(d["date"])
        n = d["contributionCount"]
        level = 0 if n == 0 else 1 + sum(n > q for q in qs)
        x = gx + wi * (cell + gap)
        y = gy + ((day.weekday() + 1) % 7) * (cell + gap)
        grid += f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" rx="2" fill="{greens[level]}" stroke="#1b1f230f"><title>{d["date"]}: {n}</title></rect>'
        if day.day <= 7 and (day.year, day.month) not in monthSeen and wi < len(weeks) - 1:
            monthSeen.add((day.year, day.month))
            grid += f'<text x="{x}" y="{gy - 8}" font-size="11" class="m">{day.strftime("%b")}</text>'
for i, label in ((1, "Mon"), (3, "Wed"), (5, "Fri")):
    grid += f'<text x="20" y="{gy + i * (cell + gap) + 10}" font-size="11" class="m">{label}</text>'
ly = gy + 7 * (cell + gap) + 16
lx = 840 - 20 - 5 * (cell + gap) - 40
grid += f'<text x="{lx - 34}" y="{ly + 10}" font-size="11" class="m">Less</text>'
for i, c in enumerate(greens):
    grid += f'<rect x="{lx + i * (cell + gap)}" y="{ly}" width="{cell}" height="{cell}" rx="2" fill="{c}"/>'
grid += f'<text x="{lx + 5 * (cell + gap) + 4}" y="{ly + 10}" font-size="11" class="m">More</text>'
grid += f'<text x="20" y="{ly + 10}" font-size="12" class="m">{calendar["totalContributions"]:,} contributions in the last year</text>'
(out / "contributions.svg").write_text(card(840, ly + 30, "contributions", grid))

allLangs = Counter()
for r in repos.values():
    for e in r["languages"]["edges"]:
        allLangs[e["node"]["name"]] += e["size"]
bar, extra = langBar(allLangs, 20, 52, 800, 4)
(out / "languages.svg").write_text(card(840, 52 + extra + 30, "languages", bar))

dates = gh(f"repos/{user}/uncord/commits", "--paginate", "--jq", ".[].commit.author.date").split()
perDay = Counter(d[:10] for d in dates)
first = date.fromisoformat(min(perDay))
last = date.today()
days = [first + timedelta(i) for i in range((last - first).days + 1)]
u = repos["uncord"]
uTraffic = traffic("uncord", "clones")
uViews = traffic("uncord", "views")
releases = len(json.loads(gh(f"repos/{user}/uncord/releases")))
body = tiles(
    [("commits", len(dates)), ("stars", u["stargazerCount"]), ("releases", releases),
     ("clones, 14d", uTraffic["count"]), ("views, 14d", uViews["count"])],
    20, 52, 800,
)
chartX, chartY, chartW, chartH = 48, 150, 772, 110
peak = max(perDay.values())
step = chartW / len(days)
body += f'<text x="20" y="{chartY - 12}" font-size="12" class="m">commits per day</text>'
for t in (0, peak // 2, peak):
    ty = chartY + chartH - chartH * t / peak
    body += f'<line x1="{chartX}" x2="{chartX + chartW}" y1="{ty:.1f}" y2="{ty:.1f}" stroke="#21262d"/>'
    body += f'<text x="{chartX - 8}" y="{ty + 4:.1f}" font-size="11" class="m" text-anchor="end">{t}</text>'
for i, d in enumerate(days):
    n = perDay.get(d.isoformat(), 0)
    if n:
        h = chartH * n / peak
        body += f'<rect x="{chartX + i * step + 1.5:.1f}" y="{chartY + chartH - h:.1f}" width="{max(step - 3, 2):.1f}" height="{h:.1f}" rx="2" fill="{greens[3]}"><title>{d}: {n}</title></rect>'
    if i % 7 == 0:
        body += f'<text x="{chartX + i * step + step / 2:.1f}" y="{chartY + chartH + 16}" font-size="11" class="m" text-anchor="middle">{d.strftime("%d %b")}</text>'
uLangs = {e["node"]["name"]: e["size"] for e in u["languages"]["edges"]}
bar, extra = langBar(uLangs, 20, chartY + chartH + 42, 800, 5)
body += bar
(out / "uncord.svg").write_text(card(840, chartY + chartH + 42 + extra + 26, "uncord", body))

ll = repos["lian-li-linux-nix"]
llTraffic = traffic("lian-li-linux-nix", "clones")
body = tiles(
    [("stars", ll["stargazerCount"]), ("clones, 14d", llTraffic["count"]), ("nix", f'{sum(e["size"] for e in ll["languages"]["edges"]) / 1000:.1f} kB')],
    20, 52, 800,
)


def node(x, y, w, label, sub, color):
    return (
        f'<rect x="{x}" y="{y}" width="{w}" height="46" rx="6" fill="#161b22" stroke="{color}"/>'
        f'<text x="{x + 12}" y="{y + 20}" font-size="13" font-weight="600" class="mono">{escape(label)}</text>'
        f'<text x="{x + 12}" y="{y + 37}" font-size="11" class="m">{escape(sub)}</text>'
    )


def arrow(x1, y1, x2, y2):
    return f'<path d="M{x1} {y1} C{(x1 + x2) / 2} {y1} {(x1 + x2) / 2} {y2} {x2} {y2}" fill="none" stroke="{border}" stroke-width="1.5" marker-end="url(#a)"/>'


fy = 160
body += f'<defs><marker id="a" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="7" markerHeight="7" orient="auto"><path d="M0 0L8 4L0 8z" fill="{muted}"/></marker></defs>'
body += f'<text x="20" y="{fy - 20}" font-size="12" class="m">what the flake builds</text>'
body += node(20, fy + 62, 160, "flake.nix", "nix profile add", accent)
body += node(250, fy + 20, 240, "lian-li-linux/", "buildRustPackage + rpath", langColors["Nix"])
body += node(250, fy + 104, 240, "module.nix", "nixos module", langColors["Nix"])
outs = [("lianli-daemon", "fans, rgb, lcd"), ("lianli-gui", "slint ui"), ("systemd --user", "daemon service"), ("udev rules", "store paths"), ("evdi", "lcd panels")]
for i, (label, sub) in enumerate(outs):
    oy = fy + i * 52 - 20
    body += node(580, oy + 12, 240, label, sub, greens[3])
    src = (490, fy + 43) if i < 2 else (490, fy + 127)
    body += arrow(*src, 578, oy + 35)
body += arrow(180, fy + 85, 248, fy + 43)
body += arrow(180, fy + 85, 248, fy + 127)
(out / "lianli.svg").write_text(card(840, fy + 5 * 52 + 6, "lian-li-linux-nix", body))
