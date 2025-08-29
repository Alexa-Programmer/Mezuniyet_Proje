# app.py
from flask import Flask, request, jsonify, render_template_string
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///board.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)

class Note(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.Text, nullable=False, default="Yeni not")
    color = db.Column(db.String(20), default="#fff3b0")
    x = db.Column(db.Float, default=80)   # px
    y = db.Column(db.Float, default=80)   # px
    z = db.Column(db.Integer, default=1)  # stacking
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

def note_to_dict(n: Note):
    return {"id": n.id, "text": n.text, "color": n.color, "x": n.x, "y": n.y, "z": n.z}

@app.before_first_request
def init_db():
    db.create_all()

@app.get("/api/notes")
def get_notes():
    notes = Note.query.order_by(Note.z).all()
    return jsonify([note_to_dict(n) for n in notes])

@app.post("/api/notes")
def create_note():
    data = request.json or {}
    n = Note(
        text=data.get("text", "Yeni not"),
        color=data.get("color", "#fff3b0"),
        x=float(data.get("x", 80)),
        y=float(data.get("y", 80)),
        z=int(data.get("z", 1)),
    )
    db.session.add(n)
    db.session.commit()
    return jsonify(note_to_dict(n)), 201

@app.patch("/api/notes/<int:note_id>")
def update_note(note_id):
    n = Note.query.get_or_404(note_id)
    data = request.json or {}
    for field in ["text", "color", "x", "y", "z"]:
        if field in data:
            setattr(n, field, data[field])
    db.session.commit()
    return jsonify(note_to_dict(n))

@app.delete("/api/notes/<int:note_id>")
def delete_note(note_id):
    n = Note.query.get_or_404(note_id)
    db.session.delete(n)
    db.session.commit()
    return "", 204

HTML = r"""
<!doctype html>
<html lang="tr">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width,initial-scale=1" />
<title>Dijital Mantar Pano</title>
<style>
  :root { --bg:#f6f7fb; --card:#ffffff; --text:#222; --muted:#6b7280; --ring:#e5e7eb; }
  * { box-sizing: border-box; }
  body { margin:0; font-family: system-ui, -apple-system, Segoe UI, Roboto, Inter, sans-serif; background: var(--bg); color: var(--text); }
  header { position: sticky; top:0; z-index: 1000; backdrop-filter: blur(6px);
           background: rgba(246,247,251,.85); border-bottom:1px solid var(--ring); }
  .bar { max-width: 1100px; margin: 0 auto; display:flex; align-items:center; gap:12px; padding: 12px 16px; }
  .brand { font-weight: 700; letter-spacing:.2px; }
  button, select, input[type=color] {
    border:1px solid var(--ring); background:#fff; padding:8px 12px; border-radius:12px; cursor:pointer;
  }
  button.primary { background:#111827; color:#fff; }
  button.danger { background:#ef4444; color:#fff; border-color:#ef4444; }
  #board {
    position: relative; max-width: 1100px; margin: 16px auto; min-height: calc(100vh - 70px);
    background-image: radial-gradient(#d1d5db 1px, transparent 1px);
    background-size: 18px 18px; border:1px solid var(--ring); border-radius:18px; box-shadow: 0 15px 30px rgba(0,0,0,.05);
  }
  .note {
    position:absolute; width: 220px; min-height: 160px; padding:10px; border-radius:16px;
    box-shadow: 0 12px 24px rgba(0,0,0,.12); border:1px solid rgba(0,0,0,.06);
    user-select:none;
    transition: box-shadow .15s ease, transform .05s ease;
  }
  .note.dragging { box-shadow: 0 16px 30px rgba(0,0,0,.20); transform: scale(1.02); }
  .note .head { display:flex; align-items:center; justify-content:space-between; gap:8px; cursor:grab; margin-bottom:8px; }
  .note .head:active { cursor:grabbing; }
  .note .title { font-weight:700; font-size:14px; }
  .note .body { background: rgba(255,255,255,.35); border-radius:10px; padding:8px; min-height:98px; outline:none; }
  .note small { color: #374151; }
  .color-dot { width:16px; height:16px; border-radius:50%; border:1px solid rgba(0,0,0,.15); }
  .controls { display:flex; align-items:center; gap:8px; }
  .hint { color: var(--muted); font-size: 12px; margin-left:auto; }
</style>
</head>
<body>
<header>
  <div class="bar">
    <div class="brand">📌 Dijital Mantar Pano</div>
    <button class="primary" id="add">Yeni Not</button>
    <label>Renk <input type="color" id="color" value="#fff3b0"></label>
    <button class="danger" id="clear">Tümünü Sil</button>
    <div class="hint">Notu sürükleyerek taşı | Metne tıklayıp yaz → otomatik kaydedilir</div>
  </div>
</header>

<div id="board"></div>

<script>
const board = document.getElementById("board");
const btnAdd = document.getElementById("add");
const btnClear = document.getElementById("clear");
const colorPicker = document.getElementById("color");

const API = {
  list: () => fetch("/api/notes").then(r=>r.json()),
  create: (data) => fetch("/api/notes",{method:"POST", headers:{'Content-Type':'application/json'}, body:JSON.stringify(data)}).then(r=>r.json()),
  patch: (id, data) => fetch(`/api/notes/${id}`, {method:"PATCH", headers:{'Content-Type':'application/json'}, body:JSON.stringify(data)}).then(r=>r.json()),
  del: (id) => fetch(`/api/notes/${id}`, {method:"DELETE"})
};

function el(html){
  const t = document.createElement('template'); t.innerHTML = html.trim(); return t.content.firstChild;
}

function noteTemplate(n){
  const html = `
  <div class="note" data-id="${n.id}" style="left:${n.x}px; top:${n.y}px; background:${n.color}; z-index:${n.z}">
    <div class="head">
      <span class="title">Not #${n.id}</span>
      <div class="controls">
        <span class="color-dot" style="background:${n.color}"></span>
        <button data-action="delete" title="Sil">🗑️</button>
      </div>
    </div>
    <div class="body" contenteditable="true" spellcheck="false">${escapeHtml(n.text)}</div>
  </div>`;
  const node = el(html);
  wireNote(node, n);
  return node;
}

function escapeHtml(s){ return s.replace(/[&<>"']/g, m => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[m])); }

function wireNote(node, data){
  // Dragging
  const head = node.querySelector('.head');
  let start = null;

  head.addEventListener('mousedown', (e)=>{
    node.classList.add('dragging');
    const rect = node.getBoundingClientRect();
    start = { mouseX:e.clientX, mouseY:e.clientY, left:rect.left + window.scrollX, top:rect.top + window.scrollY };
    node.style.zIndex = Date.now(); // bring to front
    document.addEventListener('mousemove', onMove);
    document.addEventListener('mouseup', onUp, { once:true });
  });

  function onMove(e){
    if(!start) return;
    const nx = start.left + (e.clientX - start.mouseX);
    const ny = start.top + (e.clientY - start.mouseY);
    node.style.left = nx + "px";
    node.style.top = ny + "px";
  }
  async function onUp(){
    node.classList.remove('dragging');
    document.removeEventListener('mousemove', onMove);
    start = null;
    const id = node.dataset.id;
    await API.patch(id, { x: parseFloat(node.style.left), y: parseFloat(node.style.top), z: parseInt(node.style.zIndex||1) });
  }

  // Edit text with debounce autosave
  const body = node.querySelector('.body');
  let saveTimer = null;
  body.addEventListener('input', ()=>{
    clearTimeout(saveTimer);
    saveTimer = setTimeout(async ()=>{
      const id = node.dataset.id;
      await API.patch(id, { text: body.innerText });
    }, 400);
  });

  // Delete
  node.querySelector('[data-action="delete"]').addEventListener('click', async ()=>{
    const id = node.dataset.id;
    await API.del(id);
    node.remove();
  });
}

async function load(){
  board.innerHTML = "";
  const notes = await API.list();
  notes.forEach(n => board.appendChild(noteTemplate(n)));
}

btnAdd.addEventListener('click', async ()=>{
  const n = await API.create({ color: colorPicker.value, text: "Yeni not" });
  board.appendChild(noteTemplate(n));
});

btnClear.addEventListener('click', async ()=>{
  if(!confirm("Tüm notlar silinsin mi?")) return;
  const notes = await API.list();
  await Promise.all(notes.map(n => API.del(n.id)));
  await load();
});

load();
</script>
</body>
</html>
"""

@app.get("/")
def index():
    return render_template_string(HTML)

if __name__ == "__main__":
    app.run(debug=True)
