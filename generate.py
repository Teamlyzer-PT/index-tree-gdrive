"""
drive-tree: gera um indice HTML + Markdown com autenticacao Google Sign-In.
O acesso so e permitido a emails do dominio especificado.
"""

import json
import os
import sys
from datetime import datetime, timezone

from google.oauth2 import service_account
from googleapiclient.discovery import build

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
                    supportsAllDrives=True,
                    includeItemsFromAllDrives=True,
                )
                .execute()
            )

            batch = resp.get("files", [])
            files.extend(batch)

            for f in batch:
                if f["mimeType"] == "application/vnd.google-apps.folder":
                    queue.append(f["id"])

            page_token = resp.get("nextPageToken")
            if not page_token:
                break

    print(f"Total de ficheiros encontrados: {len(files)}")
    return files


def build_tree(files, root_folder_id):
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
#  HTML Dinamico com Login Google em JavaScript Seguro
# ---------------------------------------------------------------------------

FILE_ICONS = {
    "folder": '<svg class="svg-ic" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="#f59e0b" stroke-width="2"><path d="M20 20a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.9a2 2 0 0 1-1.69-.9L9.6 3.9A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2Z"/></svg>',
    "document": '<svg class="svg-ic" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="#2563eb" stroke-width="2"><path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"/><path d="M14 2v4a2 2 0 0 0 2 2h4"/></svg>',
    "spreadsheet": '<svg class="svg-ic" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="#16a34a" stroke-width="2"><rect width="18" height="18" x="3" y="3" rx="2" ry="2"/><line x1="3" x2="21" y1="9" y2="9"/><line x1="3" x2="21" y1="15" y2="15"/><line x1="9" x2="9" y1="3" y2="21"/><line x1="15" x2="15" y1="3" y2="21"/></svg>',
    "presentation": '<svg class="svg-ic" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="#ea580c" stroke-width="2"><rect width="18" height="14" x="3" y="3" rx="2"/><path d="M7 21h10"/><path d="M12 17v4"/><path d="m9 8 6 3-6 3Z"/></svg>',
    "image": '<svg class="svg-ic" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="#8b5cf6" stroke-width="2"><rect width="18" height="18" x="3" y="3" rx="2" ry="2"/><circle cx="9" cy="9" r="2"/><path d="m21 15-3.086-3.086a2 2 0 0 0-2.828 0L6 21"/></svg>',
    "video": '<svg class="svg-ic" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="#dc2626" stroke-width="2"><path d="m22 8-6 4 6 4V8Z"/><rect width="14" height="12" x="2" y="6" rx="2" ry="2"/></svg>',
    "audio": '<svg class="svg-ic" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="#06b6d4" stroke-width="2"><path d="M9 18V5l12-2v13"/><circle cx="6" cy="18" r="3"/><circle cx="18" cy="16" r="3"/></svg>',
    "pdf": '<svg class="svg-ic" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="#b91c1c" stroke-width="2"><path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z"/><polyline points="14 2 14 8 20 8"/><path d="M12 18v-6c0-1-1-1-1-1H9v6"/><path d="M9 14h2"/></svg>',
    "archive": '<svg class="svg-ic" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="#4b5563" stroke-width="2"><polyline points="21 8 21 21 3 21 3 8"/><rect width="22" height="5" x="1" y="3"/><line x1="10" x2="14" y1="12" y2="12"/></svg>',
    "code": '<svg class="svg-ic" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="#059669" stroke-width="2"><polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/></svg>',
    "default": '<svg class="svg-ic" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="#4b5563" stroke-width="2"><path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"/><path d="M14 2v4a2 2 0 0 0 2 2h4"/></svg>',
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
            html += f'<span class="m font-mono">{len(node["children"])} itens</span>'
    else:
        link = node.get("webViewLink") or f"https://drive.google.com/file/d/{node['id']}/view"
        html += f'<span class="fl"><a href="{link}" target="_blank" rel="noopener">{node["name"]}</a></span>'
        html += f'<span class="m font-mono">{format_size(node.get("size"))}</span>'

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


def generate_html(tree, company_name, updated_at, client_id, domain_lock):
    total_folders, total_files = count_items(tree)
    tree_html = "".join(render_node_html(n) for n in tree)

    return f"""<!DOCTYPE html>
<html lang="pt">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{company_name} - Índice Seguro</title>
<script src="https://accounts.google.com/gsi/client" async defer></script>
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

:root {{
  --bg: #f8fafc;
  --panel: #ffffff;
  --border: #e2e8f0;
  --text-main: #0f172a;
  --text-muted: #64748b;
  --accent: #2563eb;
  --accent-hover: #1d4ed8;
  --accent-light: #eff6ff;
  --row-hover: #f1f5f9;
}}

* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{
  background: var(--bg);
  color: var(--text-main);
  font-family: 'Inter', sans-serif;
  min-height: 100vh;
  padding: 2rem 1rem;
  display: flex;
  justify-content: center;
  align-items: flex-start;
}}

.app-container {{
  width: 100%;
  max-width: 1000px;
  background: var(--panel);
  border: 1px solid var(--border);
  border-radius: 16px;
  box-shadow: 0 4px 20px -2px rgba(15, 23, 42, 0.05);
  overflow: hidden;
  display: none; /* Escondido ate fazer login */
}}

#login-screen {{
  width: 100%;
  max-width: 420px;
  background: #ffffff;
  border: 1px solid var(--border);
  border-radius: 16px;
  padding: 3rem 2rem;
  text-align: center;
  box-shadow: 0 4px 20px -2px rgba(15, 23, 42, 0.05);
  margin-top: 10vh;
}}

.login-logo {{
  font-size: 1.8rem;
  font-weight: 700;
  margin-bottom: 0.5rem;
}}
.login-logo span {{ color: var(--text-muted); font-weight: 400; }}

.login-desc {{
  font-size: 0.9rem;
  color: var(--text-muted);
  margin-bottom: 2rem;
}}

.error-msg {{
  color: #dc2626;
  background: #fef2f2;
  border: 1px solid #fca5a5;
  padding: 0.75rem;
  border-radius: 8px;
  font-size: 0.85rem;
  margin-bottom: 1.5rem;
  display: none;
}}

header {{ padding: 2rem 2.5rem 1.5rem; border-bottom: 1px solid var(--border); display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 1rem; }}
.brand h1 {{ font-size: 1.5rem; font-weight: 700; letter-spacing: -0.025em; }}
.brand h1 span {{ color: var(--text-muted); font-weight: 400; }}
.stats {{ font-size: 0.85rem; color: var(--text-muted); text-align: right; line-height: 1.5; }}
.search-hero {{ padding: 1.5rem 2.5rem; background: #ffffff; border-bottom: 1px solid var(--border); }}
.search-wrapper {{ position: relative; width: 100%; }}
.search-wrapper input {{ width: 100%; background: var(--bg); border: 1px solid var(--border); border-radius: 10px; padding: 0.85rem 1rem 0.85rem 2.75rem; color: var(--text-main); font-size: 0.95rem; outline: none; }}
.search-wrapper input:focus {{ background: #ffffff; border-color: var(--accent); box-shadow: 0 0 0 4px var(--accent-light); }}
.search-wrapper .search-icon {{ position: absolute; left: 1rem; top: 50%; transform: translateY(-50%); color: var(--text-muted); pointer-events: none; }}
.toolbar {{ padding: 0.75rem 2.5rem; background: #fafafa; border-bottom: 1px solid var(--border); display: flex; gap: 0.5rem; align-items: center; }}
.toolbar button {{ background: #ffffff; color: #334155; border: 1px solid var(--border); padding: 0.5rem 1rem; border-radius: 6px; font-size: 0.8rem; font-weight: 500; cursor: pointer; display: flex; align-items: center; gap: 0.4rem; }}
.toolbar button:hover {{ background: var(--row-hover); }}
.toolbar button.btn-primary {{ margin-left: auto; background: var(--accent); color: #ffffff; border-color: var(--accent); }}
.tree-container {{ padding: 1.5rem 2.5rem 3rem; min-height: 400px; }}
.r {{ display: flex; align-items: center; gap: 0.6rem; padding: 0.45rem 0.6rem; border-radius: 6px; font-size: 0.9rem; }}
.r:hover {{ background: var(--row-hover); }}
.svg-ic {{ width: 18px; height: 18px; display: block; }}
.i {{ flex-shrink: 0; width: 18px; }}
.s {{ width: 18px; display: inline-block; }}
.t {{ flex-shrink: 0; width: 18px; text-align: center; cursor: pointer; color: var(--text-muted); font-size: 0.6rem; transition: transform 0.2s ease; user-select: none; }}
.t.open {{ transform: rotate(90deg); }}
.fn {{ flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-weight: 600; }}
.fl {{ flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
.fl a {{ color: #334155; text-decoration: none; }}
.fl a:hover {{ color: var(--accent); }}
.m {{ font-size: 0.75rem; color: var(--text-muted); flex-shrink: 0; }}
.font-mono {{ font-family: 'JetBrains Mono', monospace; }}
.ch {{ margin-left: 1.2rem; border-left: 1px solid var(--border); overflow: hidden; }}
.ch.collapsed {{ display: none; }}
.toast {{ position: fixed; bottom: 2rem; left: 50%; transform: translateX(-50%) translateY(20px); background: #0f172a; color: #ffffff; font-size: 0.8rem; padding: 0.6rem 1.5rem; border-radius: 8px; opacity: 0; transition: all 0.3s; pointer-events: none; }}
.toast.show {{ opacity: 1; transform: translateX(-50%) translateY(0); }}
</style>
</head>
<body>

<div id="login-screen">
  <div class="login-logo">{company_name}<span>/</span>drive</div>
  <div class="login-desc">Autentica-te com a tua conta Google profissional para aceder aos documentos.</div>
  <div id="error-box" class="error-msg"></div>
  <div style="display: flex; justify-content: center;">
    <div id="g_id_onload"
         data-client_id="{client_id}"
         data-context="signin"
         data-ux_mode="popup"
         data-callback="handleCredentialResponse"
         data-auto_select="false"
         data-close_on_tap_outside="false">
    </div>
    <div class="g_id_signin"
         data-type="standard"
         data-shape="rectangular"
         data-theme="outline"
         data-text="signin_with"
         data-size="large"
         data-logo_alignment="left">
    </div>
  </div>
</div>

<div class="app-container" id="app-content">
  <header>
    <div class="brand"><h1>{company_name}<span>/</span>drive</h1></div>
    <div class="stats">
      <strong>{total_folders}</strong> pastas &bull; <strong>{total_files}</strong> ficheiros<br>
      <span style="font-size:0.75rem;">Atualizado em: {updated_at}</span>
    </div>
  </header>

  <div class="search-hero">
    <div class="search-wrapper">
      <svg class="search-icon" xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/></svg>
      <input type="text" id="searchBox" placeholder="Pesquisar ou filtrar ficheiros por nome..." oninput="fi(this.value)">
    </div>
  </div>

  <div class="toolbar">
    <button onclick="ea()">Expandir tudo</button>
    <button onclick="ca()">Colapsar tudo</button>
    <button class="btn-primary" onclick="cm()">Copiar Link</button>
  </div>

  <div class="tree-container" id="tree">
    {tree_html}
  </div>
</div>

<div class="toast" id="toast">Link copiado com sucesso!</div>

<script>
// Descodifica o token JWT da Google no browser (sem servidor)
function decodeJwt(token) {{
  try {{
    var base64Url = token.split('.')[1];
    var base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
    var jsonPayload = decodeURIComponent(window.atob(base64).split('').map(function(c) {{
        return '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2);
    }}).join(''));
    return JSON.parse(jsonPayload);
  }} catch(e) {{ return null; }}
}}

function handleCredentialResponse(response) {{
  var payload = decodeJwt(response.credential);
  if (payload && payload.email) {{
    var email = payload.email.toLowerCase();
    var allowedDomain = "{domain_lock}".toLowerCase().trim();

    if (email.endsWith("@" + allowedDomain) || email === allowedDomain) {{
      // Sucesso! Mostra o conteudo e esconde o login
      document.getElementById('login-screen').style.display = 'none';
      document.getElementById('app-content').style.display = 'block';
      // Inicia colapsado para ficar mais limpo
      ca(); 
    }} else {{
      var err = document.getElementById('error-box');
      err.innerText = "Acesso Negado: O email " + email + " nao pertence ao dominio " + allowedDomain;
      err.style.display = 'block';
    }}
  }}
}}

function tog(e){{
  var ch = e.closest('.n').querySelector('.ch');
  if(!ch) return;
  e.classList.toggle('open');
  ch.classList.toggle('collapsed');
}}
function ea(){{
  document.querySelectorAll('.t').forEach(t => t.classList.add('open'));
  document.querySelectorAll('.ch').forEach(c => c.classList.remove('collapsed'));
}}
function ca(){{
  document.querySelectorAll('.t').forEach(t => t.classList.remove('open'));
  document.querySelectorAll('.ch').forEach(c => c.classList.add('collapsed'));
}}
function fi(q){{
  q = q.toLowerCase().trim();
  document.querySelectorAll('.n').forEach(n => {{
    if(!q){{ n.style.display = ''; return; }}
    var name = (n.dataset.name || '');
    if(name.includes(q)){{
      n.style.display = '';
      var p = n.parentElement.closest('.n');
      while(p){{
        p.style.display = '';
        var t = p.querySelector('.t');
        if(t) t.classList.add('open');
        var ch = p.querySelector('.ch');
        if(ch) ch.classList.remove('collapsed');
        p = p.parentElement.closest('.n');
      }}
    }} else {{ n.style.display = 'none'; }}
  }});
}}
function cm(){{
  navigator.clipboard.writeText(window.location.href).then(()=>{{
    var t = document.getElementById('toast');
    t.classList.add('show');
    setTimeout(()=>t.classList.remove('show'), 2000);
  }});
}}
</script>
</body>
</html>"""


def main():
    folder_id = os.environ.get("DRIVE_FOLDER_ID")
    client_id = os.environ.get("GOOGLE_CLIENT_ID") # Novo Secret
    
    if not folder_id:
        print("ERRO: variavel DRIVE_FOLDER_ID nao definida.")
        sys.exit(1)
        
    if not client_id:
        print("AVISO: GOOGLE_CLIENT_ID nao definido. O login nao vai funcionar.")
        client_id = "EM_FALTA"

    company = os.environ.get("COMPANY_NAME", "Teamlyzer")
    # Bloqueia o acesso a este dominio (ex: teamlyzer.com)
    domain_lock = os.environ.get("ALLOWED_DOMAIN", "teamlyzer.com") 
    
    output_dir = os.environ.get("OUTPUT_DIR", "public")
    os.makedirs(output_dir, exist_ok=True)

    service = get_drive_service()
    files = fetch_all_files(service, folder_id)
    tree = build_tree(files, folder_id)

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    # Gerar HTML Protegido
    html = generate_html(tree, company, now, client_id, domain_lock)
    html_path = os.path.join(output_dir, "index.html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"HTML gerado com protecao Google Sign-In: {html_path}")

    # Gerar Markdown
    md_lines = tree_to_markdown(tree)
    md = f"# {company} - Indice Drive\n\n_Atualizado: {now}_\n\n" + "\n".join(md_lines) + "\n"
    md_path = os.path.join(output_dir, "INDEX.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md)


if __name__ == "__main__":
    main()
