from pathlib import Path
import re

ROOT=Path(__file__).resolve().parent

p=ROOT/'frontend/readability-v753.js'
s=p.read_text(encoding='utf-8')

# BUGFIX:
# app.js declares `let all=[]`, so it lives in the global lexical scope,
# but NOT as window.all. v7.5.3 checked window.all, therefore the decorator
# exited immediately and the "gemy cały mecz" UI never appeared.
if "const rows=()=>typeof all!=='undefined'&&Array.isArray(all)?all:[];" not in s:
    s=s.replace(
        "const mkey=m=>String(m?.id ?? m?.match_id ?? [m?.p1,m?.p2,m?.scheduled_time].join('|'));",
        "const mkey=m=>String(m?.id ?? m?.match_id ?? [m?.p1,m?.p2,m?.scheduled_time].join('|'));\n"
        "  const rows=()=>typeof all!=='undefined'&&Array.isArray(all)?all:[];"
    )

s=s.replace("if(!Array.isArray(window.all))return;", "if(!rows().length)return;")
s=s.replace("const m=window.all.find(x=>mkey(x)===raw);", "const m=rows().find(x=>mkey(x)===raw);")
s=s.replace(
    "if(!overlay || overlay.hidden || !Array.isArray(window.all))return null;",
    "if(!overlay || overlay.hidden || !rows().length)return null;"
)
s=s.replace(
    "return window.all.find(m=>String(m.p1)===names[0]&&String(m.p2)===names[1])||null;",
    "return rows().find(m=>String(m.p1)===names[0]&&String(m.p2)===names[1])||null;"
)

p.write_text(s,encoding='utf-8')

# bump visible version
idx=ROOT/'frontend/index.html'
x=idx.read_text(encoding='utf-8')
x=x.replace('Tenis AI v7.5.4 · Admin delete','Tenis AI v7.5.5 · Match games hotfix')
x=x.replace('LAB v7.5.4','LAB v7.5.5')
if 'v7.5.5:' not in x:
    x=x.replace(
        '<div>v7.5.4:',
        '<div>v7.5.5: poprawiono wyświetlanie liczby gemów całego meczu — błąd dostępu do danych JS. v7.5.4:'
    )
idx.write_text(x,encoding='utf-8')

# force fresh service-worker cache
sw=ROOT/'frontend/sw.js'
w=sw.read_text(encoding='utf-8')
w=re.sub(r"const C='[^']+';","const C='tenis-ai-v755-match-games-hotfix';",w,count=1)
sw.write_text(w,encoding='utf-8')

print('Tenis AI v7.5.5 match-games hotfix: OK')
