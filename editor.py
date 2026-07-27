#!/usr/bin/env python3
"""Local dev server for my-site: serves the site and writes inline edits back to the HTML files.

Read-only pages get an editor script injected on the fly, so nothing about the
editor lives in the site files and nothing can be deployed by accident.

    python3 editor.py [port]
"""
import json
import os
import re
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

ROOT = os.path.dirname(os.path.abspath(__file__))
BACKUPS = os.path.join(os.path.dirname(ROOT), "my-site-backups")
INJECT = b'<script src="/_edit.js"></script>\n</body>'
ALLOWED = re.compile(r"^(index(-ua)?|case-[a-z-]+)\.html$")


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **k):
        super().__init__(*a, directory=ROOT, **k)

    def log_message(self, fmt, *args):
        if "_save" in fmt % args:
            super().log_message(fmt, *args)

    # -- serve ---------------------------------------------------------------
    def do_GET(self):
        if self.path == "/_edit.js":
            return self._send(EDIT_JS.encode("utf-8"), "application/javascript")
        path = self.translate_path(self.path)
        if path.endswith(".html") and os.path.isfile(path):
            with open(path, "rb") as fh:
                body = fh.read()
            if b"</body>" in body:
                body = body.replace(b"</body>", INJECT, 1)
            return self._send(body, "text/html; charset=utf-8")
        return super().do_GET()

    def _send(self, body, ctype):
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    # -- save ----------------------------------------------------------------
    def do_POST(self):
        if self.path != "/_save":
            return self.send_error(404)
        try:
            n = int(self.headers.get("Content-Length", 0))
            req = json.loads(self.rfile.read(n) or b"{}")
            result = self._apply(req)
            code = 200
        except Exception as exc:                                  # noqa: BLE001
            result, code = {"ok": False, "error": str(exc)}, 400
        body = json.dumps(result, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _apply(self, req):
        name = os.path.basename(req.get("file", ""))
        if not ALLOWED.match(name):
            raise ValueError(f"refusing to write {name!r}")
        path = os.path.join(ROOT, name)
        if not os.path.isfile(path):
            raise ValueError(f"{name} does not exist")

        edits = req.get("edits") or []
        src = open(path, encoding="utf-8").read()
        applied, skipped = 0, []
        for e in edits:
            old, new = e.get("old", ""), e.get("new", "")
            if not old or old == new:
                continue
            hits = src.count(old)
            if hits != 1:                       # 0 = stale, >1 = ambiguous; never guess
                skipped.append({"old": old[:70], "hits": hits})
                continue
            src = src.replace(old, new, 1)
            applied += 1

        if applied:
            os.makedirs(BACKUPS, exist_ok=True)
            open(os.path.join(BACKUPS, name), "w", encoding="utf-8").write(
                open(path, encoding="utf-8").read())
            open(path, "w", encoding="utf-8").write(src)
        return {"ok": not skipped, "file": name, "applied": applied, "skipped": skipped}


EDIT_JS = r"""
(function(){
if(!/^(localhost|127\.|192\.168\.|10\.|172\.(1[6-9]|2\d|3[01])\.)/.test(location.hostname))return;

var ON=false, dirty=Object.create(null), n=0;

var css=document.createElement('style');
css.textContent=''
+'.ed-bar{position:fixed;left:20px;bottom:20px;z-index:200;display:flex;gap:8px;align-items:center;'
+'font:500 14px/1 Onest,sans-serif}'
+'.ed-bar button{font:inherit;padding:10px 16px;border-radius:999px;border:1px solid #111;background:#fbfaf8;'
+'color:#111;cursor:pointer}'
+'.ed-bar button.on{background:#111;color:#fff}'
+'.ed-bar .ed-save{border-color:#0000EE;color:#fff;background:#0000EE}'
+'.ed-bar .ed-save[disabled]{opacity:.35;cursor:default}'
+'.ed-bar .ed-msg{font-weight:400;color:#555;max-width:38ch}'
+'body.ed-on [data-l]{outline:1px dashed rgba(0,0,238,.35);outline-offset:2px;cursor:text}'
+'body.ed-on [data-l]:hover{outline-color:#0000EE;background:rgba(0,0,238,.04)}'
+'body.ed-on [data-l].ed-dirty{outline:1px solid #0000EE;background:rgba(0,0,238,.07)}';
document.head.appendChild(css);

var bar=document.createElement('div');
bar.className='ed-bar';
bar.innerHTML='<button type="button" class="ed-toggle">Редагувати</button>'
 +'<button type="button" class="ed-save" disabled>Зберегти</button><span class="ed-msg"></span>';
document.body.appendChild(bar);
var bToggle=bar.querySelector('.ed-toggle'), bSave=bar.querySelector('.ed-save'), msg=bar.querySelector('.ed-msg');

function srcOf(el){
  var host=el.closest('[data-src]');
  return host?host.getAttribute('data-src'):location.pathname.split('/').pop()||'index.html';
}
function key(el){return srcOf(el)+'|'+(el.dataset.edOld||'');}

function arm(el){
  if(el.dataset.edArmed)return;
  el.dataset.edArmed='1';
  el.dataset.edOld=el.innerHTML;
}
function clean(html){
  var d=document.createElement('div');
  d.innerHTML=html;
  (function walk(node){
    [].slice.call(node.children).forEach(function(c){
      walk(c);
      if(!/^(I|B|EM|STRONG|A|BR|SPAN)$/.test(c.tagName)){
        while(c.firstChild)c.parentNode.insertBefore(c.firstChild,c);
        c.parentNode.removeChild(c);
      }
    });
  })(d);
  return d.innerHTML.replace(/<br>/g,'<br/>').trim();
}

document.addEventListener('click',function(e){
  if(!ON)return;
  var el=e.target.closest('[data-l]');
  if(!el)return;
  e.preventDefault();
  arm(el);
  el.contentEditable='true';
  el.focus();
},true);

document.addEventListener('focusout',function(e){
  var el=e.target.closest?e.target.closest('[data-l]'):null;
  if(!el||el.contentEditable!=='true')return;
  el.contentEditable='false';
  var now=clean(el.innerHTML);
  if(now!==el.dataset.edOld){
    dirty[key(el)]={file:srcOf(el),old:el.dataset.edOld,'new':now};
    el.classList.add('ed-dirty');
  }else{
    delete dirty[key(el)];
    el.classList.remove('ed-dirty');
  }
  n=Object.keys(dirty).length;
  bSave.disabled=!n;
  msg.textContent=n?(n+' змін не збережено'):'';
},true);

bToggle.addEventListener('click',function(){
  ON=!ON;
  document.body.classList.toggle('ed-on',ON);
  bToggle.classList.toggle('on',ON);
  bToggle.textContent=ON?'Вимкнути':'Редагувати';
  msg.textContent=ON?'Клікни по тексту':'';
});

bSave.addEventListener('click',function(){
  var byFile={};
  Object.keys(dirty).forEach(function(k){
    var d=dirty[k];
    (byFile[d.file]=byFile[d.file]||[]).push({old:d.old,'new':d['new']});
  });
  var names=Object.keys(byFile);
  bSave.disabled=true; msg.textContent='Зберігаю…';
  Promise.all(names.map(function(f){
    return fetch('/_save',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({file:f,edits:byFile[f]})}).then(function(r){return r.json()});
  })).then(function(res){
    var ok=res.every(function(r){return r.ok});
    var applied=res.reduce(function(a,r){return a+(r.applied||0)},0);
    if(ok){
      dirty=Object.create(null);
      [].forEach.call(document.querySelectorAll('.ed-dirty'),function(el){
        el.classList.remove('ed-dirty'); el.dataset.edOld=el.innerHTML;
      });
      msg.textContent='Збережено: '+applied+' у '+names.join(', ');
    }else{
      var bad=res.filter(function(r){return !r.ok});
      msg.textContent='Частково: '+applied+' збережено, не знайшло '+
        bad.map(function(r){return r.skipped.length}).reduce(function(a,b){return a+b},0)+' фрагментів';
      bSave.disabled=false;
    }
  })['catch'](function(err){msg.textContent='Помилка: '+err; bSave.disabled=false});
});
})();
"""


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
    print(f"serving {ROOT} on http://0.0.0.0:{port} (inline editor enabled for LAN clients)")
    ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()
