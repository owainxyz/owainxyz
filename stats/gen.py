import json
import os
import sys
import urllib.error
import urllib.request
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


token = os.environ.get("GH_TOKEN") or open(os.path.expanduser("~/.config/ghstats/token")).read().strip()


def gh(path, data=None):
    req = urllib.request.Request(
        "https://api.github.com/" + path,
        data=json.dumps(data).encode() if data else None,
        headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json", "User-Agent": "ghstats"},
    )
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.load(r), r.headers.get("Link", "")


def graphql(query):
    return gh("graphql", {"query": query})[0]["data"]


def paged(path):
    items, page = [], 1
    while True:
        chunk = gh(f"{path}{'&' if '?' in path else '?'}per_page=100&page={page}")[0]
        items += chunk
        if len(chunk) < 100:
            return items
        page += 1


def traffic(repo, kind):
    try:
        return gh(f"repos/{user}/{repo}/traffic/{kind}")[0]
    except urllib.error.HTTPError:
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


lightMap = {
    "#0d1117": "#ffffff", "#30363d": "#d0d7de", "#e6edf3": "#1f2328", "#8b949e": "#59636e",
    "#161b22": "#f0f2f5", "#21262d": "#eaeef2", "#0e4429": "#9be9a8", "#006d32": "#40c463",
    "#26a641": "#30a14e", "#39d353": "#216e39",
}


def light(svg):
    for d, l in lightMap.items():
        svg = svg.replace(d, l)
    return svg


def build():
    svgs = {}
    data = graphql(
        f'{{user(login:"{user}"){{followers{{totalCount}} contributionsCollection{{totalCommitContributions '
        "totalPullRequestContributions contributionCalendar{totalContributions weeks{contributionDays{date contributionCount}}}} "
        "repositories(first:100,ownerAffiliations:OWNER,privacy:PUBLIC){totalCount nodes{name stargazerCount "
        "isFork languages(first:20){edges{size node{name color}}}}}}}"
    )["user"]
    contrib = data["contributionsCollection"]
    calendar = contrib["contributionCalendar"]
    repos = {r["name"]: r for r in data["repositories"]["nodes"]}
    for r in repos.values():
        for e in r["languages"]["edges"]:
            if e["node"]["color"]:
                langColors.setdefault(e["node"]["name"], e["node"]["color"])
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
    svgs["overview"] = (card(840, 136, "github stats", overview))

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
    svgs["contributions"] = (card(840, ly + 30, "contributions", grid))

    allLangs = Counter()
    for r in repos.values():
        if r["isFork"]:
            continue
        for e in r["languages"]["edges"]:
            allLangs[e["node"]["name"]] += e["size"]
    bar, extra = langBar(allLangs, 20, 52, 800, 4)
    svgs["languages"] = (card(840, 52 + extra + 30, "languages", bar))

    dates = [c["commit"]["author"]["date"] for c in paged(f"repos/{user}/uncord/commits")]
    perDay = Counter(d[:10] for d in dates)
    first = date.fromisoformat(min(perDay))
    last = date.today()
    days = [first + timedelta(i) for i in range((last - first).days + 1)]
    u = repos["uncord"]
    uTraffic = traffic("uncord", "clones")
    uViews = traffic("uncord", "views")
    rels = paged(f"repos/{user}/uncord/releases")
    body = tiles(
        [("commits", len(dates)), ("stars", u["stargazerCount"]), ("latest", rels[0]["tag_name"] if rels else "-"),
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
    svgs["uncord"] = (card(840, chartY + chartH + 42 + extra + 26, "uncord", body))

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
    outs = [("lianli-daemon", "fans, rgb, lcd"), ("lianli-gui", "tauri + vue"), ("systemd --user", "daemon service"), ("udev rules", "store paths"), ("evdi", "lcd panels")]
    for i, (label, sub) in enumerate(outs):
        oy = fy + i * 52 - 20
        body += node(580, oy + 12, 240, label, sub, greens[3])
        src = (490, fy + 43) if i < 2 else (490, fy + 127)
        body += arrow(*src, 578, oy + 35)
    body += arrow(180, fy + 85, 248, fy + 43)
    body += arrow(180, fy + 85, 248, fy + 127)
    svgs["lianli"] = (card(840, fy + 5 * 52 + 6, "lian-li-linux-nix", body))


    prs = graphql(
        f'{{search(query:"author:{user} is:pr -user:{user}",type:ISSUE,first:50){{nodes{{... on PullRequest{{'
        "title number state merged repository{nameWithOwner stargazerCount description primaryLanguage{name color}}}}}}"
    )["search"]["nodes"]
    byRepo = {}
    for pr in prs:
        if pr["state"] == "CLOSED" and not pr["merged"]:
            continue
        byRepo.setdefault(pr["repository"]["nameWithOwner"], (pr["repository"], []))[1].append(pr)
    stateColors = {"merged": "#a371f7", "open": "#3fb950"}
    body = ""
    y = 60
    for name, (repo, items) in sorted(byRepo.items(), key=lambda kv: -kv[1][0]["stargazerCount"]):
        lang = repo["primaryLanguage"] or {"name": "", "color": muted}
        body += f'<rect x="20" y="{y}" width="800" height="{46 + 24 * len(items)}" rx="6" fill="#161b22" stroke="{border}"/>'
        body += f'<text x="36" y="{y + 26}" font-size="14" font-weight="600" class="mono">{escape(name)}</text>'
        meta = f'<circle cx="{804 - 150}" cy="{y + 21}" r="5" fill="{lang["color"] or muted}"/>'
        meta += f'<text x="{804 - 140}" y="{y + 25}" font-size="12" class="m">{escape(lang["name"])}</text>'
        meta += f'<text x="804" y="{y + 25}" font-size="12" class="m" text-anchor="end">\u2605 {human(repo["stargazerCount"])}</text>'
        body += meta
        for i, pr in enumerate(sorted(items, key=lambda p: p["number"])):
            state = "merged" if pr["merged"] else "open"
            py = y + 50 + 24 * i
            body += f'<circle cx="41" cy="{py - 4}" r="4" fill="{stateColors[state]}"/>'
            body += f'<text x="54" y="{py}" font-size="12"><tspan class="m">#{pr["number"]}</tspan> {escape(pr["title"])}</text>'
            body += f'<text x="804" y="{py}" font-size="12" text-anchor="end" fill="{stateColors[state]}" style="fill:{stateColors[state]}">{state}</text>'
        y += 46 + 24 * len(items) + 12
    svgs["contributed"] = (card(840, y + 8, "contributed to", body))
    allDays = [(date.fromisoformat(d["date"]), d["contributionCount"]) for w in weeks for d in w["contributionDays"]]
    allDays = [x for x in allDays if x[0] <= date.today()]
    run = longest = 0
    longestEnd = None
    for day, n in allDays:
        run = run + 1 if n else 0
        if run > longest:
            longest, longestEnd = run, day
    current = 0
    for day, n in reversed(allDays):
        if n:
            current += 1
        elif day != date.today():
            break
    active = sum(1 for _, n in allDays if n)
    best = max(allDays, key=lambda x: x[1])
    body = tiles(
        [("current streak", f"{current}d"), ("longest streak", f"{longest}d"), ("active days", active), ("best day", best[1])],
        20, 52, 800,
    )
    body += f'<text x="20" y="140" font-size="12" class="m">longest ended {longestEnd.strftime("%d %b %Y") if longestEnd else "-"} \u00b7 best day {best[0].strftime("%d %b %Y")}</text>'
    weekdayTotals = [0] * 7
    for day, n in allDays:
        weekdayTotals[day.weekday()] += n
    wPeak = max(weekdayTotals) or 1
    for i, label in enumerate(["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]):
        bx = 20 + i * 115
        h = 70 * weekdayTotals[i] / wPeak
        body += f'<rect x="{bx}" y="{240 - h:.1f}" width="105" height="{max(h, 1):.1f}" rx="3" fill="{greens[3]}"/>'
        body += f'<text x="{bx + 52}" y="{260}" font-size="11" class="m" text-anchor="middle">{label}</text>'
        body += f'<text x="{bx + 52}" y="{234 - h:.1f}" font-size="11" text-anchor="middle">{weekdayTotals[i]}</text>'
    svgs["streak"] = card(840, 280, "streak", body)

    events = gh(f"users/{user}/events/public?per_page=40")[0]
    lines = []
    for ev in events:
        repo = ev["repo"]["name"]
        p = ev["payload"]
        when = ev["created_at"][:10]
        if ev["type"] == "PushEvent":
            msg = ""
            if p.get("commits"):
                msg = p["commits"][-1]["message"]
            elif p.get("head"):
                try:
                    msg = gh(f"repos/{repo}/commits/{p['head']}")[0]["commit"]["message"]
                except urllib.error.HTTPError:
                    pass
            lines.append(("push", repo, msg.split("\n")[0], when))
        elif ev["type"] == "PullRequestEvent" and p.get("action") in ("opened", "closed"):
            pr = p["pull_request"]
            if "title" not in pr:
                try:
                    pr = gh(pr["url"].removeprefix("https://api.github.com/"))[0]
                except urllib.error.HTTPError:
                    continue
            act = "merged" if pr.get("merged") else p["action"]
            lines.append((act, repo, f'#{pr["number"]} {pr["title"]}', when))
        elif ev["type"] == "ReleaseEvent":
            if any(k == "release" and r == repo for k, r, _, _ in lines):
                continue
            lines.append(("release", repo, p["release"]["tag_name"], when))
        elif ev["type"] == "CreateEvent" and p.get("ref_type") == "repository":
            lines.append(("new repo", repo, "", when))
        if len(lines) >= 8:
            break
    kindColors = {"push": greens[3], "merged": "#a371f7", "opened": "#3fb950", "closed": "#f85149", "release": accent, "new repo": accent}
    body = ""
    for i, (kind, repo, text, when) in enumerate(lines[:8]):
        ly = 62 + i * 26
        body += f'<circle cx="26" cy="{ly - 4}" r="4" fill="{kindColors.get(kind, muted)}"/>'
        short = text if len(text) <= 58 else text[:57] + "\u2026"
        body += f'<text x="38" y="{ly}" font-size="12"><tspan class="mono">{escape(repo.split("/")[1])}</tspan> <tspan class="m">{escape(kind)}</tspan> {escape(short)}</text>'
        body += f'<text x="820" y="{ly}" font-size="11" class="m" text-anchor="end">{date.fromisoformat(when).strftime("%d %b")}</text>'
    svgs["recent"] = card(840, 62 + len(lines[:8]) * 26 + 8, "recent", body)

    return svgs


if __name__ == "__main__":
    for name, svg in build().items():
        (out / f"{name}.svg").write_text(svg)
