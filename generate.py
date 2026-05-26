"""
drive-tree: gera um indice HTML + Markdown a partir de uma pasta do Google Drive.
Usa uma Service Account para acesso sem interacao do utilizador.
Corre localmente ou via GitHub Actions.
"""

import json
import os
import sys
from datetime import datetime, timezone

from google.oauth2 import service_account
from googleapiclient.discovery import build

# ---------------------------------------------------------------------------
#  Configuracao (variaveis de ambiente)
# ---------------------------------------------------------------------------
SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]


def get_drive_service():
    creds_json = os.environ.get("GOOGLE_CREDENTIALS_JSON")
    if not creds_json:
        print("ERRO: variavel GOOGLE_CREDENTIALS_JSON nao definida.")
        sys.exit(1)

    info = json.loads(creds_json)
    creds = service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
    return build("drive", "v3", credentials=creds)


def fetch_all_files(service, folder_id):
    """Busca recursivamente todos os ficheiros dentro da pasta, com suporte a Shared Drives."""
    files = []
    queue = [folder_id]
    visited = set()

    while queue:
        current = queue.pop(0)
        if current in visited:
            continue
        visited.add(current)

        page_token = None
        while True:
            resp = (
                service.files()
                .list(
                    q=f"'{current}' in parents and trashed = false",
                    fields="nextPageToken, files(id, name, mimeType, parents, webViewLink, size, modifiedTime)",
                    pageSize=1000,
                    pageToken=page_token,
                    supportsAllDrives=True,  # Crucial para Discos Partilhados
                    includeItemsFromAllDrives=True,  # Crucial para Discos Partilhados
                )
                .execute()
            )

            batch = resp.get("files", [])
            files.extend(batch)

            # Adicionar sub-pastas a queue
            for f in batch:
                if f["mimeType"] == "application/vnd.google-apps.folder":
                    queue.append(f["id"])

            page_token = resp.get("nextPageToken")
            if not page_token:
                break

    print(f"Total de ficheiros encontrados: {len(files)}")
    return files


def build_tree(files, root_folder_id):
    """Organiza os ficheiros numa arvore."""
    by_id = {}
    for f in files:
        by_id[f["id"]] = {**f, "children": []}

    roots = []
    for f in files:
        fid = f["id"]
        parent = (f.get("parents") or [None])[0]
        if parent and parent in by_id:
            by_id[parent]["children"].append(by_id[fid])
        else:
            # Se o parent não está na lista trazida, este nó passa a ser uma raiz local
            roots.append(by_id[fid])

    def sort_nodes(nodes):
        nodes.sort(
            key=lambda n: (
                0 if n["mimeType"] == "application/vnd.google-apps.folder" else 1,
                n["name"].lower(),
            )
        )
        for n in nodes:
            sort_nodes(n["children"])

    sort_nodes(roots)
    return roots


# ---------------------------------------------------------------------------
#  Geracao de Markdown
# ---------------------------------------------------------------------------

def tree_to_markdown(nodes, indent=""):
    lines = []
    for n in nodes:
        is_folder = n["mimeType"] == "application/vnd.google-apps.folder"
        if is_folder:
            lines.append(f"{indent}- **{n['name']}/**")
            if n["children"]:
                lines.extend(tree_to_markdown(n["children"], indent + "  "))
        else:
            link = n.get("webViewLink") or f"https://drive.google.com/file/d/{n['id']}/view"
            lines.append(f"{indent}- [{n['name']}]({link})")
    return lines


# ---------------------------------------------------------------------------
#  Geracao de HTML
# ---------------------------------------------------------------------------

FILE_ICONS = {
    "folder": "&#128193;",
    "document": "&#128196;",
    "spreadsheet": "&#128202;",
    "presentation": "&#127916;",
    "image": "&#128247;",
    "video": "&#127910;",
    "audio": "&#127925;",
    "pdf": "&#128213;",
    "archive": "&#128230;",
    "code": "&#128221;",
    "default": "&#128196;",
}


def get_icon(mime):
    m = mime or ""
    if "folder" in m:
        return FILE_ICONS["folder"]
    if "document" in m or "word" in m:
        return FILE_ICONS["document"]
    if "spreadsheet" in m or "excel" in m:
        return FILE_ICONS["spreadsheet"]
    if "presentation" in m or "powerpoint" in m:
        return FILE_ICONS["presentation"]
    if "image" in m:
        return FILE_ICONS["image"]
    if "video" in m:
        return FILE_ICONS["video"]
    if "audio" in m:
        return FILE_ICONS["audio"]
    if "pdf" in m:
        return FILE_ICONS["pdf"]
    if any(k in m for k in ("zip", "archive", "compressed", "tar", "rar")):
        return FILE_ICONS["archive"]
    if any(k in m for k in ("text", "json", "xml", "script", "html", "css", "javascript")):
        return FILE_ICONS["code"]
    return FILE_ICONS["default"]


def format_size(size_str):
    if not size_str:
        return ""
    b = int(size_str)
    if b < 1024:
        return f"{b} B"
    kb = b / 1024
    if kb < 1024:
        return f"{kb:.0f} KB"
    return f"{kb / 1024:.1f} MB"


def render_node_html(node, depth=0):
    is_folder = node["mimeType"] == "application/vnd.google-apps.folder"
    has_children = bool(node["children"])
    icon = get_icon(node["mimeType"])

    html = f'<div class="n" data-name="{node["name"].lower()}">'
    html += '<div class="r">'

    if is_folder and has_children:
        html += '<span class="t open" onclick="tog(this)">&#9654;</span>'
    else:
        html += '<span class="s"></span>'

    html += f'<span class="i">{icon}</span>'

    if is_folder:
        html += f'<span class="fn">{node["name"]}</span>'
        if has_children:
            html += f'<span class="m">{len(node["children"])}</span>'
    else:
        link = node.get("webViewLink") or f"https://drive.google.com/file/d/{node['id']}/view"
        html += f'<span class="fl"><a href="{link}" target="_blank" rel="noopener">{node["name"]}</a></span>'
        html += f'<span class="m">{format_size(node.get("size"))}</span>'

    html += "</div>"

    if is_folder and has_children:
        html += '<div class="ch">'
        for c in node["children"]:
            html += render_node_html(c, depth + 1)
        html += "</div>"

    html += "</div>"
    return html


def count_items(nodes):
    folders = 0
    files = 0
    for n in nodes:
        if n["mimeType"] == "application/vnd.google-apps.folder":
            folders += 1
        else:
            files += 1
        cf, cfi = count_items(n["children"])
        folders += cf
        files += cfi
    return folders, files


def generate_html(tree, company_name, updated_at):
    total_folders, total_files = count_items(tree)
    tree_html = "".join(render_node_html(n) for n in tree)

    return f"""<!DOCTYPE html>
<html lang="pt">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{company_name} - Indice Drive</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@300;400;500;600&family=Outfit:wght@300;400;600;700&display=swap');
*{{margin:0;padding:0;box-sizing:border-box}}
:root{{
  --bg:#0e0f12;--sf:#16171c;--sh:#1e2028;--bd:#2a2c35;
  --tx:#e2e4ea;--td:#7a7e8c;--ac:#6ee7b7;--fo:#fbbf24;--lk:#93c5fd;
  --mn:'JetBrains Mono',monospace;--sn:'Outfit',sans-serif;
}}
body{{background:var(--bg);color:var(--tx);font-family:var(--sn);min-height:100vh}}
.grain{{position:fixed;inset:0;pointer-events:none;opacity:.03;
  background-image:url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E");
  z-index:9999}}
header{{padding:2.5rem 2rem 1.5rem;border-bottom:1px solid var(--bd);display:flex;align-items:center;gap:1.5rem;flex-wrap:wrap}}
header h1{{font-family:var(--mn);font-weight:600;font-size:1.4rem;letter-spacing:-.02em;color:var(--ac)}}
header h1 span{{color:var(--td);font-weight:300}}
.stats{{margin-left:auto;font-family:var(--mn);font-size:.7rem;color:var(--td);text-align:right;line-height:1.6}}
.bar{{padding:.8rem 2rem;border-bottom:1px solid var(--bd);display:flex;gap:.8rem;align-items:center;flex-wrap:wrap}}
.bar button{{background:var(--sf);color:var(--td);border:1px solid var(--bd);padding:.45rem 1rem;border-radius:5px;font-family:var(--mn);font-size:.75rem;cursor:pointer;transition:all .15s}}
.bar button:hover{{color:var(--tx);border-color:var(--td)}}
.bar input{{flex:1;min-width:180px;background:var(--sf);border:1px solid var(--bd);border-radius:5px;padding:.45rem .8rem;color:var(--tx);font-family:var(--mn);font-size:.75rem;outline:none}}
.bar input:focus{{border-color:var(--ac)}}
.bar input::placeholder{{color:var(--td)}}
.tc{{padding:1rem 1.5rem 4rem}}
.n{{animation:fi .15s ease both}}
.r{{display:flex;align-items:center;gap:.4rem;padding:.3rem .6rem;border-radius:5px;font-family:var(--mn);font-size:.8rem;color:var(--tx);transition:background .1s}}
.r:hover{{background:var(--sh)}}
.i{{flex-shrink:0;width:18px;text-align:center;font-size:.85rem}}
.s{{width:18px;display:inline-block}}
.t{{flex-shrink:0;width:18px;text-align:center;cursor:pointer;color:var(--td);font-size:.65rem;transition:transform .2s;user-select:none}}
.t.open{{transform:rotate(90deg)}}
.fn{{flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:var(--fo);font-weight:500}}
.fl{{flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}
.fl a{{color:var(--lk);text-decoration:none;transition:color .15s}}
.fl a:hover{{color:#bdd9fe;text-decoration:underline}}
.m{{font-size:.65rem;color:var(--td);flex-shrink:0;font-weight:300}}
.ch{{margin-left:1.2rem;border-left:1px solid var(--bd);overflow:hidden;transition:max-height .3s ease}}
.ch.collapsed{{max-height:0!important}}
.toast{{position:fixed;bottom:2rem;left:50%;transform:translateX(-50%) translateY(20px);background:var(--ac);color:var(--bg);font-family:var(--mn);font-size:.75rem;font-weight:600;padding:.6rem 1.4rem;border-radius:6px;opacity:0;transition:all .3s;pointer-events:none;z-index:100}}
.toast.show{{opacity:1;transform:translateX(-50%) translateY(0)}}
@keyframes fi{{from{{opacity:0;transform:translateY(4px)}}to{{opacity:1;transform:translateY(0)}}}}
</style>
</head>
<body>
<div class="grain"></div>
<header>
  <h1>{company_name}<span>/</span>drive</h1>
  <div class="stats">
    {total_folders} pastas, {total_files} ficheiros<br>
    Atualizado: {updated_at}
  </div>
</header>
<div class="bar">
  <button onclick="ea()">+ Expandir tudo</button>
  <button onclick="ca()">- Colapsar tudo</button>
  <button onclick="cm()">&#128203; Copiar link</button>
  <input type="text" placeholder="filtrar ficheiros..." oninput="fi(this.value)">
</div>
<div class="tc" id="tree">
{tree_html}
</div>
<div class="toast" id="toast">Link copiado!</div>
<script>
function tog(e){{
  var ch=e.closest('.n').querySelector('.ch');
  if(!ch)return;
  e.classList.toggle('open');
  ch.classList.toggle('collapsed');
}}
function ea(){{
  document.querySelectorAll('.t').forEach(t=>t.classList.add('open'));
  document.querySelectorAll('.ch').forEach(c=>c.classList.remove('collapsed'));
}}
function ca(){{
  document.querySelectorAll('.t').forEach(t=>t.classList.remove('open'));
  document.querySelectorAll('.ch').forEach(c=>c.classList.add('collapsed'));
}}
function fi(q){{
  q=q.toLowerCase().trim();
  document.querySelectorAll('.n').forEach(n=>{{
    if(!q){{n.style.display='';return;}}
    n.style.display=(n.dataset.name||'').includes(q)?'':'none';
  }});
}}
function cm(){{
  navigator.clipboard.writeText(window.location.href).then(()=>{{
    var t=document.getElementById('toast');
    t.classList.add('show');
    setTimeout(()=>t.classList.remove('show'),2000);
  }});
}}
</script>
</body>
</html>"""


# ---------------------------------------------------------------------------
#  Main
# ---------------------------------------------------------------------------

def main():
    folder_id = os.environ.get("DRIVE_FOLDER_ID")
    if not folder_id:
        print("ERRO: variavel DRIVE_FOLDER_ID nao definida.")
        sys.exit(1)

    company = os.environ.get("COMPANY_NAME", "Empresa")
    output_dir = os.environ.get("OUTPUT_DIR", "public")
    os.makedirs(output_dir, exist_ok=True)

    service = get_drive_service()
    files = fetch_all_files(service, folder_id)
    tree = build_tree(files, folder_id)

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    # Gerar HTML
    html = generate_html(tree, company, now)
    html_path = os.path.join(output_dir, "index.html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"HTML gerado: {html_path}")

    # Gerar Markdown
    md_lines = tree_to_markdown(tree)
    md = f"# {company} - Indice Drive\n\n_Atualizado: {now}_\n\n" + "\n".join(md_lines) + "\n"
    md_path = os.path.join(output_dir, "INDEX.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md)
    print(f"Markdown gerado: {md_path}")


if __name__ == "__main__":
    main()
