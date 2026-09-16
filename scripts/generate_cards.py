"""Generate profile cards from public GitHub repository metadata.

Run with Python 3.11+ and Pillow. SVGs are committed so viewing the profile
does not depend on a third-party card server.
"""

import html
import json
import os
from pathlib import Path
import urllib.request

from PIL import ImageFont


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "assets" / "cards"
REPOS = ["LiberCoders/FeatureBench", "potatoQi/HarborStar", "potatoQi/LumaRing"]
WIDTH = 480
PADDING = 24
DESCRIPTION_SIZE = 15
LINE_HEIGHT = 22
STATS_SIZE = 14
LANGUAGE_COLORS = {"Python": "#3572a5", "Swift": "#f05138"}
THEMES = {
    "dark": dict(bg="#0d1117", border="#3d444d", title="#4493f8",
                 text="#a6adb6", star="#e3b341", fork="#3fb950"),
    "light": dict(bg="#ffffff", border="#d1d9e0", title="#0969da",
                  text="#59636e", star="#9a6700", fork="#1a7f37"),
}


def font(size):
    # Liberation Sans is metrically compatible with Arial.
    for path in (
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
    ):
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    raise RuntimeError("Install Liberation Sans fonts to measure card text.")


def wrap(text, face, max_width):
    lines = []
    line = ""
    for word in text.split():
        candidate = f"{line} {word}".strip()
        if face.getlength(candidate) <= max_width:
            line = candidate
            continue
        if line:
            lines.append(line)
        line = ""
        for char in word:
            if face.getlength(line + char) > max_width and line:
                lines.append(line)
                line = ""
            line += char
    if line:
        lines.append(line)
    return lines or [""]


def fetch(repo):
    headers = {"User-Agent": "potatoQi-profile-cards", "Accept": "application/vnd.github+json"}
    if os.environ.get("GH_TOKEN"):
        headers["Authorization"] = "Bearer " + os.environ["GH_TOKEN"]
    request = urllib.request.Request(f"https://api.github.com/repos/{repo}", headers=headers)
    with urllib.request.urlopen(request, timeout=30) as response:
        data = json.load(response)
    if data.get("private") or data.get("full_name", "").lower() != repo.lower():
        raise ValueError(f"Expected public repository {repo}")
    return data


def icon(kind, x, y, color):
    shapes = {
        "star": '<path d="M9 1.5 11.3 6.2 16.5 7 12.7 10.7 13.6 16 9 13.5 4.4 16 5.3 10.7 1.5 7 6.7 6.2Z"/>',
        "fork": '<circle cx="4" cy="3.5" r="2"/><circle cx="14" cy="3.5" r="2"/><circle cx="9" cy="15" r="2"/><path d="M4 5.5v2A2.5 2.5 0 0 0 6.5 10H9m5-4.5v2a2.5 2.5 0 0 1-2.5 2.5H9v3"/>',
        "repo": '<path d="M3 2h12v12H5a2 2 0 0 0 0 4h10v-4M3 2v14a2 2 0 0 1 2-2M6 2v9"/>',
    }
    return (f'<g transform="translate({x:g},{y:g})" fill="none" stroke="{color}" '
            f'stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">{shapes[kind]}</g>')


def render(data, theme):
    colors = THEMES[theme]
    face = font(DESCRIPTION_SIZE)
    stats_face = font(STATS_SIZE)
    # A small margin allows for platform font-rendering differences.
    lines = wrap(data.get("description") or "", face, WIDTH - 2 * PADDING - 8)
    baseline = 64
    stats_y = baseline + (len(lines) - 1) * LINE_HEIGHT + 38
    height = stats_y + 22
    title = html.escape(data["name"])
    description = html.escape(data.get("description") or "")
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{height}" viewBox="0 0 {WIDTH} {height}" role="img" aria-labelledby="title desc">',
        f'<title id="title">{title}</title>',
        f'<desc id="desc">{description}. Stars: {data["stargazers_count"]}. Forks: {data["forks_count"]}.</desc>',
        '<style>text{font-family:Arial,"Liberation Sans",sans-serif}</style>',
        f'<rect x=".5" y=".5" width="{WIDTH - 1}" height="{height - 1}" rx="4.5" fill="{colors["bg"]}" stroke="{colors["border"]}"/>',
        icon("repo", PADDING, 20, colors["text"]),
        f'<text x="50" y="35" font-size="18" font-weight="600" fill="{colors["title"]}">{title}</text>',
    ]
    for index, line in enumerate(lines):
        parts.append(f'<text x="{PADDING}" y="{baseline + index * LINE_HEIGHT}" font-size="{DESCRIPTION_SIZE}" fill="{colors["text"]}">{html.escape(line)}</text>')
    x = float(PADDING)
    language = data.get("language")
    if language:
        color = LANGUAGE_COLORS.get(language, colors["text"])
        parts.append(f'<circle cx="{x + 6}" cy="{stats_y - 5}" r="6" fill="{color}"/>')
        parts.append(f'<text x="{x + 20}" y="{stats_y}" font-size="{STATS_SIZE}" fill="{colors["text"]}">{html.escape(language)}</text>')
        x += 20 + stats_face.getlength(language) + 22
    for kind, key in (("star", "stargazers_count"), ("fork", "forks_count")):
        count = data[key]
        if not count:
            continue
        value = f"{count:,}"
        parts.append(icon(kind, x, stats_y - 14, colors[kind]))
        parts.append(f'<text x="{x + 24:g}" y="{stats_y}" font-size="{STATS_SIZE}" fill="{colors["text"]}">{value}</text>')
        x += 24 + stats_face.getlength(value) + 22
    parts.append("</svg>\n")
    return "\n".join(parts)


def main():
    # Fetch and render everything first; failures leave existing cards intact.
    results = {}
    for repo in REPOS:
        data = fetch(repo)
        for theme in THEMES:
            results[f"{data['name']}-{theme}.svg"] = render(data, theme)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    for name, contents in results.items():
        (OUTPUT / name).write_text(contents, encoding="utf-8")
        print(f"Generated {name}")


if __name__ == "__main__":
    main()
