#!/usr/bin/env python3
import http.server
import json
import os

PORT = 8000
KB_ROOT = os.path.expanduser("~/Documents/GitHub/knowledge")

def scan_tree(path, prefix=""):
    entries = []
    try:
        items = sorted(os.listdir(path))
    except PermissionError:
        return entries
    # skip hidden dirs like .git, .claude
    items = [i for i in items if not i.startswith('.')]
    for item in items:
        full = os.path.join(path, item)
        rel = os.path.join(prefix, item) if prefix else item
        if os.path.isdir(full):
            children = scan_tree(full, rel)
            entries.append({"name": item, "path": rel, "type": "dir", "children": children})
        else:
            size = os.path.getsize(full)
            entries.append({"name": item, "path": rel, "type": "file", "size": size})
    return entries

HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Knowledge Base</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #f6f8fa; color: #1f2328; padding: 40px; max-width: 800px; margin: 0 auto; }
  h1 { color: #1f2328; margin-bottom: 4px; font-size: 22px; font-weight: 600; }
  .subtitle { color: #656d76; margin-bottom: 28px; font-size: 13px; }
  .domain { background: #fff; border: 1px solid #d0d7de; border-radius: 8px; margin-bottom: 20px; overflow: hidden; }
  .domain-header { padding: 14px 18px; border-bottom: 1px solid #d0d7de; display: flex; align-items: center; gap: 10px; }
  .domain-name { font-size: 16px; font-weight: 600; color: #0969da; }
  .badge { background: #ddf4ff; color: #0969da; padding: 2px 8px; border-radius: 10px; font-size: 11px; font-weight: 500; }
  .tree { padding: 6px 0; }
  .node { display: flex; align-items: center; padding: 3px 18px; font-size: 13px; font-family: 'SF Mono', 'Fira Code', 'Consolas', monospace; line-height: 1.6; }
  .node:hover { background: #f6f8fa; }
  .indent { display: inline-block; width: 20px; flex-shrink: 0; color: #d0d7de; }
  .pipe { color: #d0d7de; margin-right: 6px; flex-shrink: 0; }
  .icon { margin-right: 6px; flex-shrink: 0; }
  .dir-name { color: #0969da; font-weight: 500; }
  .file-name { color: #1f2328; }
  .file-name.system { color: #bf8700; font-weight: 500; }
  .file-name.md { color: #8250df; }
  .size { color: #8c959f; margin-left: auto; font-size: 11px; padding-left: 16px; }
  .refresh { position: fixed; bottom: 20px; right: 20px; background: #1f883d; color: #fff; border: none; padding: 8px 16px; border-radius: 6px; cursor: pointer; font-size: 13px; font-weight: 500; box-shadow: 0 1px 3px rgba(0,0,0,0.12); }
  .refresh:hover { background: #1a7f37; }
  .empty { color: #8c959f; font-style: italic; padding: 4px 44px; font-size: 12px; }
  .connector { color: #d0d7de; font-family: monospace; margin-right: 4px; }
</style>
</head>
<body>
<h1>~/knowledge/</h1>
<p class="subtitle">Knowledge Base File Index</p>
<div id="root"></div>
<button class="refresh" onclick="load()">Refresh</button>
<script>
function fileClass(name) {
  if (name.startsWith('_')) return 'system';
  if (name.endsWith('.md')) return 'md';
  return '';
}

function formatSize(bytes) {
  if (bytes < 1024) return bytes + ' B';
  return (bytes / 1024).toFixed(1) + ' KB';
}

function renderNode(node, depth, isLast) {
  var html = '';
  var pad = '';
  for (var i = 0; i < depth; i++) pad += '<span class="indent"></span>';

  if (node.type === 'dir') {
    html += '<div class="node">' + pad + '<span class="connector">' + (isLast ? '\u2514\u2500' : '\u251C\u2500') + '</span><span class="icon">\uD83D\uDCC1</span><span class="dir-name">' + node.name + '/</span></div>';
    if (node.children.length === 0) {
      html += '<div class="empty">' + pad + '<span class="indent"></span>(empty)</div>';
    }
    for (var i = 0; i < node.children.length; i++) {
      html += renderNode(node.children[i], depth + 1, i === node.children.length - 1);
    }
  } else {
    var cls = fileClass(node.name);
    var extra = cls ? ' ' + cls : '';
    html += '<div class="node">' + pad + '<span class="connector">' + (isLast ? '\u2514\u2500' : '\u251C\u2500') + '</span><span class="file-name' + extra + '">' + node.name + '</span><span class="size">' + formatSize(node.size) + '</span></div>';
  }
  return html;
}

function render(data) {
  var root = document.getElementById('root');
  var html = '';
  for (var d = 0; d < data.length; d++) {
    var domain = data[d];
    if (domain.type === 'file') continue;
    var count = countFiles(domain);
    html += '<div class="domain">';
    html += '<div class="domain-header"><span class="domain-name">' + domain.name + '/</span><span class="badge">' + count + ' files</span></div>';
    html += '<div class="tree">';
    if (domain.children.length === 0) {
      html += '<div class="empty">(empty)</div>';
    }
    for (var i = 0; i < domain.children.length; i++) {
      html += renderNode(domain.children[i], 0, i === domain.children.length - 1);
    }
    html += '</div></div>';
  }
  root.innerHTML = html;
}

function countFiles(node) {
  if (node.type === 'file') return 1;
  var c = 0;
  for (var i = 0; i < (node.children || []).length; i++) c += countFiles(node.children[i]);
  return c;
}

function load() {
  fetch('/api/tree').then(function(r) { return r.json(); }).then(render).catch(function(e) { document.getElementById('root').innerHTML = '<p>Error loading: ' + e + '</p>'; });
}

load();
</script>
</body>
</html>"""

class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/api/tree':
            tree = scan_tree(KB_ROOT)
            # put master first
            tree.sort(key=lambda x: (0 if x['name'] == 'master' else 1, x['name']))
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(tree).encode())
        else:
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.end_headers()
            self.wfile.write(HTML.encode())

    def log_message(self, format, *args):
        pass  # quiet

if __name__ == '__main__':
    print(f"Serving at http://localhost:{PORT}")
    http.server.HTTPServer(('', PORT), Handler).serve_forever()
