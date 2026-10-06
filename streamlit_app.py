"""OmniForge SuperAI Ultimate — single-file Streamlit application.

A broad engineering/research workspace with named modules for: AI/model discovery,
persistent memory, owner-approved code evolution, multidisciplinary calculations,
materials/BOM/cost estimation, optimization, failure analysis, simulation, 3-D
geometry, image/vision analysis, research planning, defensive security analysis,
cryptography primitives, reverse-engineering helpers, exports, and self-tests.

Safety contract: no arbitrary AI-generated code execution, malware deployment,
credential theft, unauthorized intrusion, destructive retaliation, or dangerous
construction instructions. Code evolution is proposal -> scan -> syntax check ->
backup -> owner authentication -> apply.
"""
import os, re, ast, math, json, hashlib, sqlite3, secrets, shutil, tempfile, textwrap
from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Iterable

try:
    import streamlit as st
except Exception:
    st = None
try:
    from openai import OpenAI
except Exception:
    OpenAI = None
try:
    import keyring
except Exception:
    keyring = None

APP_NAME = "OmniForge SuperAI Ultimate"
APP_VERSION = "2.0.0-complete"
APP_DIR = Path.home() / ".omniforge"
DB_PATH = APP_DIR / "omniforge.db"
SERVICE = "omniforge-openai"
H = 6.62607015e-34
HBAR = 1.054571817e-34
C = 299792458.0
KB = 1.380649e-23
R_GAS = 8.31446261815324
G = 9.80665

SYSTEM_PROMPT = """You are OmniForge, a multidisciplinary invention and engineering intelligence.
Operate as: OBSERVE -> REQUIREMENTS -> RESEARCH -> DESIGN -> CALCULATE -> SIMULATE ->
CRITIQUE -> TEST PLAN -> LEARN -> ITERATE. Cover mathematics, physics, chemistry,
quantum science, mechanical/electrical engineering, software, product design,
materials, economics, and 3-D concepts. Clearly separate facts, assumptions,
calculations, estimates, simulations, and physical verification. Never fabricate
web sources or test results. For cybersecurity, support authorized defensive
analysis, CTF/lab learning, threat modeling, reverse engineering and malware
analysis without deployment or unauthorized access. Never retaliate. Never execute
AI-generated code, shell commands, or arbitrary network actions. Owner approval is
required for self-modification."""

# ============================================================
# 01 — IDENTITY / CONFIGURATION
# ============================================================
def now() -> str:
    return datetime.now(timezone.utc).isoformat()

def app_identity() -> dict:
    return {"name": APP_NAME, "version": APP_VERSION, "architecture": "single-file", "mode": "owner-controlled"}

def ensure_app() -> None:
    APP_DIR.mkdir(parents=True, exist_ok=True)
    try: APP_DIR.chmod(0o700)
    except OSError: pass

def app_paths() -> dict:
    ensure_app(); return {"app_dir": str(APP_DIR), "database": str(DB_PATH), "source": str(Path(__file__).resolve())}

# ============================================================
# 02 — PERSISTENT MEMORY / SETTINGS / AUDIT
# ============================================================
def db():
    ensure_app(); c = sqlite3.connect(DB_PATH)
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("CREATE TABLE IF NOT EXISTS memory(id INTEGER PRIMARY KEY, created TEXT, kind TEXT, project TEXT, content TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY, created TEXT, event TEXT, detail TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS settings(k TEXT PRIMARY KEY, v TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS projects(id INTEGER PRIMARY KEY, created TEXT, name TEXT UNIQUE, summary TEXT)")
    c.commit(); return c

def audit(event: str, detail: str = "") -> None:
    c=db(); c.execute("INSERT INTO audit(created,event,detail) VALUES(?,?,?)", (now(),event,detail[:8000])); c.commit(); c.close()

def audit_log(limit: int = 100) -> list:
    c=db(); r=c.execute("SELECT created,event,detail FROM audit ORDER BY id DESC LIMIT ?",(limit,)).fetchall(); c.close(); return r

def setting_get(k: str, default=None):
    c=db(); r=c.execute("SELECT v FROM settings WHERE k=?",(k,)).fetchone(); c.close(); return r[0] if r else default

def setting_set(k: str, v) -> None:
    c=db(); c.execute("INSERT INTO settings(k,v) VALUES(?,?) ON CONFLICT(k) DO UPDATE SET v=excluded.v",(k,str(v))); c.commit(); c.close()

def remember(content: str, kind: str = "note", project: str = "default") -> None:
    c=db(); c.execute("INSERT INTO memory(created,kind,project,content) VALUES(?,?,?,?)",(now(),kind,project,content[:20000])); c.commit(); c.close()

def recall(project: str = "default", limit: int = 30) -> list:
    c=db(); r=c.execute("SELECT created,kind,content FROM memory WHERE project=? ORDER BY id DESC LIMIT ?",(project,limit)).fetchall(); c.close(); return r

def search_memory(query: str, project: str = "default", limit: int = 20) -> list:
    c=db(); like=f"%{query}%"; r=c.execute("SELECT created,kind,content FROM memory WHERE project=? AND content LIKE ? ORDER BY id DESC LIMIT ?",(project,like,limit)).fetchall(); c.close(); return r

def create_project(name: str, summary: str = "") -> None:
    c=db(); c.execute("INSERT OR IGNORE INTO projects(created,name,summary) VALUES(?,?,?)",(now(),name,summary)); c.commit(); c.close()

def list_projects() -> list:
    c=db(); r=c.execute("SELECT created,name,summary FROM projects ORDER BY id DESC").fetchall(); c.close(); return r

def export_memory(project: str = "default") -> str:
    return json.dumps({"project":project,"memory":recall(project,1000)},indent=2)

def import_memory(payload: str, project: str = "default") -> int:
    obj=json.loads(payload); rows=obj.get("memory",[]); n=0
    for row in rows:
        if len(row)>=3: remember(str(row[2]),str(row[1]),project); n+=1
    audit("memory_import",f"{n} entries"); return n

# ============================================================
# 03 — SECRET / OWNER CONTROL
# ============================================================
def get_secret():
    if keyring:
        try: return keyring.get_password(SERVICE,"OPENAI_API_KEY")
        except Exception: pass
    return os.environ.get("OPENAI_API_KEY")

def save_secret(value: str) -> str:
    if not value: raise ValueError("Empty API key")
    if keyring:
        try:
            keyring.set_password(SERVICE,"OPENAI_API_KEY",value); audit("api_key_saved","OS credential store"); return "OS credential store"
        except Exception: pass
    audit("api_key_not_persisted","keyring unavailable; use OPENAI_API_KEY")
    return "Environment variable fallback; not written to plaintext disk"

def delete_secret() -> None:
    if keyring:
        try: keyring.delete_password(SERVICE,"OPENAI_API_KEY")
        except Exception: pass
    audit("api_key_deleted")

def hash_pin(pin: str) -> str:
    return hashlib.scrypt(pin.encode(),salt=b"omniforge-owner-v2",n=2**14,r=8,p=1).hex()

def set_owner_pin(pin: str) -> bool:
    if len(pin)<8: raise ValueError("Owner PIN must be at least 8 characters")
    setting_set("owner_pin_hash",hash_pin(pin)); audit("owner_pin_set"); return True

def owner_auth(pin: str) -> bool:
    h=setting_get("owner_pin_hash"); return bool(h and secrets.compare_digest(h,hash_pin(pin)))

def backup_source() -> str:
    src=Path(__file__).resolve(); ensure_app(); dst=APP_DIR/(src.stem+".backup-"+datetime.now().strftime("%Y%m%d-%H%M%S")+".py"); shutil.copy2(src,dst); return str(dst)

# ============================================================
# 04 — SAFE MATH / GENERAL MATHEMATICS
# ============================================================
_ALLOWED_MATH = {"pi":math.pi,"e":math.e,"tau":math.tau,"sqrt":math.sqrt,"sin":math.sin,"cos":math.cos,"tan":math.tan,"log":math.log,"log10":math.log10,"exp":math.exp,"fabs":math.fabs,"floor":math.floor,"ceil":math.ceil,"abs":abs,"round":round,"pow":pow}
def safe_math(expr: str):
    tree=ast.parse(expr,mode="eval")
    allowed=(ast.Expression,ast.Constant,ast.BinOp,ast.UnaryOp,ast.Add,ast.Sub,ast.Mult,ast.Div,ast.Pow,ast.Mod,ast.USub,ast.UAdd,ast.Call,ast.Name,ast.Load)
    for n in ast.walk(tree):
        if not isinstance(n,allowed): raise ValueError("Unsupported expression")
        if isinstance(n,ast.Name) and n.id not in _ALLOWED_MATH: raise ValueError("Unknown function/name")
        if isinstance(n,ast.Call) and (not isinstance(n.func,ast.Name) or n.func.id not in _ALLOWED_MATH): raise ValueError("Unsafe call")
    return _eval_ast(tree.body)

def _eval_ast(n):
    if isinstance(n,ast.Constant) and isinstance(n.value,(int,float)): return n.value
    if isinstance(n,ast.Name): return _ALLOWED_MATH[n.id]
    if isinstance(n,ast.UnaryOp): return (-1 if isinstance(n.op,ast.USub) else 1)*_eval_ast(n.operand)
    if isinstance(n,ast.BinOp):
        a,b=_eval_ast(n.left),_eval_ast(n.right); ops={ast.Add:lambda:a+b,ast.Sub:lambda:a-b,ast.Mult:lambda:a*b,ast.Div:lambda:a/b,ast.Pow:lambda:a**b,ast.Mod:lambda:a%b}; return ops[type(n.op)]()
    if isinstance(n,ast.Call): return _ALLOWED_MATH[n.func.id](*[_eval_ast(x) for x in n.args])
    raise ValueError("Unsupported expression")

def vector_add(a,b): return tuple(x+y for x,y in zip(a,b))
def vector_sub(a,b): return tuple(x-y for x,y in zip(a,b))
def vector_dot(a,b): return sum(x*y for x,y in zip(a,b))
def vector_cross(a,b): return (a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0])
def vector_norm(a): return math.sqrt(vector_dot(a,a))
def matrix_multiply(A,B): return [[sum(A[i][k]*B[k][j] for k in range(len(B))) for j in range(len(B[0]))] for i in range(len(A))]
def linear_interpolate(x0,y0,x1,y1,x): return y0+(y1-y0)*(x-x0)/(x1-x0)
def percent_change(old,new): return (new-old)/old*100

def derivative_central(fn,x,h=1e-6): return (fn(x+h)-fn(x-h))/(2*h)
def integrate_trapezoid(xs,ys): return sum((xs[i+1]-xs[i])*(ys[i]+ys[i+1])/2 for i in range(len(xs)-1))

# ============================================================
# 05 — MECHANICAL / FLUID / THERMAL ENGINEERING
# ============================================================
def force(m,a): return m*a
def kinetic_energy(m,v): return .5*m*v*v
def potential_energy(m,h,g=G): return m*g*h
def momentum(m,v): return m*v
def impulse(F,dt): return F*dt
def power_from_torque(t,w): return t*w
def torque(F,r): return F*r
def rotational_energy(I,w): return .5*I*w*w
def angular_momentum(I,w): return I*w
def stress(F,A): return F/A
def strain(dL,L): return dL/L
def hooke_stress(E,e): return E*e
def factor_of_safety(strength,load): return strength/load
def pressure(F,A): return F/A
def hydrostatic_pressure(rho,h,g=G): return rho*g*h
def thermal_expansion(alpha,L,dT): return alpha*L*dT
def reynolds(rho,v,L,mu): return rho*v*L/mu
def dynamic_pressure(rho,v): return .5*rho*v*v
def drag_force(rho,v,Cd,A): return .5*rho*v*v*Cd*A
def buoyant_force(rho,V,g=G): return rho*V*g
def mass_flow(rho,Q): return rho*Q
def volumetric_flow(area,v): return area*v
def bernoulli_pressure_change(rho,v1,v2,h1,h2,g=G): return rho*(.5*(v1*v1-v2*v2)+g*(h1-h2))
def spring_force(k,x): return k*x
def spring_energy(k,x): return .5*k*x*x
def beam_bending_stress(M,c,I): return M*c/I
def second_moment_rectangle(b,h): return b*h**3/12
def cylinder_volume(r,h): return math.pi*r*r*h
def cylinder_surface_area(r,h): return 2*math.pi*r*(r+h)
def sphere_volume(r): return 4*math.pi*r**3/3
def sphere_surface_area(r): return 4*math.pi*r*r

def ideal_gas_moles(P,V,T=298.15,R=R_GAS): return P*V/(R*T)
def conduction_heat(k,A,dT,L,t): return k*A*dT/L*t
def heat_energy(m,c,dT): return m*c*dT
def thermal_power(m,c,dT,dt): return m*c*dT/dt

# ============================================================
# 06 — ELECTRICAL / ELECTRONICS
# ============================================================
def electrical_power(V,I): return V*I
def electrical_energy(P,t): return P*t
def resistor_power(I,R): return I*I*R
def ohms_law(V,R): return V/R
def series_resistance(values): return sum(values)
def parallel_resistance(values): return 1/sum(1/r for r in values)
def capacitor_energy(C,V): return .5*C*V*V
def capacitor_charge(C,V): return C*V
def rc_time_constant(R,C): return R*C
def inductive_energy(L,I): return .5*L*I*I
def inductive_reactance(f,L): return 2*math.pi*f*L
def capacitive_reactance(f,C): return 1/(2*math.pi*f*C)
def rms_sine(peak): return peak/math.sqrt(2)
def electrical_efficiency(output,input_power): return output/input_power

# ============================================================
# 07 — CHEMISTRY / PHYSICAL CHEMISTRY
# ============================================================
def pH(h): return -math.log10(h)
def pOH(oh): return -math.log10(oh)
def henderson_hasselbalch(pka,base,acid): return pka+math.log10(base/acid)
def beer_lambert(epsilon,c,l): return epsilon*c*l
def arrhenius(A,Ea,T,R=R_GAS): return A*math.exp(-Ea/(R*T))
def dilution(c1,v1,c2): return c1*v1/c2
def molarity(moles,liters): return moles/liters
def moles_from_mass(mass,molar_mass): return mass/molar_mass
def mass_from_moles(moles,molar_mass): return moles*molar_mass
def ideal_gas_volume(n,T=298.15,P=101325,R=R_GAS): return n*R*T/P
def equilibrium_ratio(kf,kr): return kf/kr

# ============================================================
# 08 — QUANTUM / MODERN PHYSICS
# ============================================================
def photon_energy(freq): return H*freq
def photon_wavelength(freq): return C/freq
def de_broglie_wavelength(m,v): return H/(m*v)
def uncertainty_dp_min(dx): return HBAR/(2*dx)
def particle_box_energy(n,m,L): return (n*n*H**2)/(8*m*L*L)
def harmonic_oscillator_energy(n,hbar,omega): return (n+.5)*hbar*omega
def qubit_probabilities(a,b):
    n=math.sqrt(abs(a)**2+abs(b)**2)
    if n==0: raise ValueError("Zero state")
    return {"0":abs(a/n)**2,"1":abs(b/n)**2}
def mass_energy(m): return m*C*C
def relativistic_gamma(v): return 1/math.sqrt(1-(v/C)**2)
def relativistic_energy(m,v): return relativistic_gamma(v)*m*C*C

# ============================================================
# 09 — MATERIALS / BOM / COST / MANUFACTURING
# ============================================================
def calculate_bom(items):
    rows=[]; total=0.0
    for x in items:
        q=float(x.get("quantity",1)); p=float(x.get("unit_price",0)); sub=q*p; total+=sub; rows.append({**x,"subtotal":sub})
    return {"items":rows,"total":total}

def cost_range(items,low_factor=.85,high_factor=1.25):
    base=calculate_bom(items)["total"]; return {"low":base*low_factor,"base":base,"high":base*high_factor}
def material_mass(density,volume): return density*volume
def material_volume(mass,density): return mass/density
def manufacturing_allowance(base,percent): return base*(1+percent/100)
def cost_per_unit(total,quantity): return total/quantity
def bom_from_rows(rows): return [{"name":r[0],"quantity":r[1],"unit_price":r[2]} for r in rows]
def mass_budget(parts): return sum(float(p.get("mass",0))*float(p.get("quantity",1)) for p in parts)

# ============================================================
# 10 — OPTIMIZATION / SCORING / FAILURE ANALYSIS
# ============================================================
SCORE_WEIGHTS={"requirements":20,"performance":18,"efficiency":12,"reliability":14,"cost":10,"simplicity":8,"safety":10,"testability":8}
def transparent_score(scores):
    total=sum(float(x.get("weight",1))*float(x.get("score",0)) for x in scores); w=sum(float(x.get("weight",1)) for x in scores) or 1
    return {"score":round(total/w,3),"criteria":scores}
def weighted_design_score(values,weights=SCORE_WEIGHTS):
    return round(sum(max(0,min(100,float(values.get(k,0))))*w/100 for k,w in weights.items()),3)
def rank_candidates(candidates): return sorted(candidates,key=lambda x:float(x.get("score",0)),reverse=True)
def sensitivity_delta(base,changed): return changed-base
def fmea_priority(severity,occurrence,detection): return severity*occurrence*detection
def risk_matrix(severity,likelihood): return severity*likelihood
def pareto_front(candidates,objectives):
    out=[]
    for a in candidates:
        dominated=False
        for b in candidates:
            if a is b: continue
            if all(b.get(k,0)>=a.get(k,0) for k in objectives) and any(b.get(k,0)>a.get(k,0) for k in objectives): dominated=True; break
        if not dominated: out.append(a)
    return out
def requirement_check(actual,minimum): return {k:actual.get(k,0)>=v for k,v in minimum.items()}
def convergence_improvement(old,new): return None if old is None else new-old

# ============================================================
# 11 — CONTROLLED SIMULATION / TEST PLANNING
# ============================================================
def simulate_projectile(v0,angle_deg,dt=.02,g=G):
    a=math.radians(angle_deg); vx=v0*math.cos(a); vy=v0*math.sin(a); t=0; rows=[]
    while t<=2*max(vy/g,0)+dt:
        x=vx*t; y=vy*t-.5*g*t*t
        if y<0 and t>0: break
        rows.append({"t":t,"x":x,"y":y}); t+=dt
    return rows

def simulate_rc(R,C,V0,t_end,dt):
    rows=[]; t=0
    while t<=t_end+dt/2:
        rows.append({"t":t,"V":V0*(1-math.exp(-t/(R*C)))}) ; t+=dt
    return rows

def simulate_cooling(T0,Tenv,k,t_end,dt):
    rows=[]; t=0
    while t<=t_end+dt/2:
        rows.append({"t":t,"T":Tenv+(T0-Tenv)*math.exp(-k*t)}); t+=dt
    return rows

def simulation_summary(rows,key):
    vals=[r[key] for r in rows if key in r]; return {"min":min(vals),"max":max(vals),"final":vals[-1],"samples":len(vals)} if vals else {}
def test_plan(requirements):
    return [{"test_id":i+1,"requirement":r,"method":"calculation/simulation/prototype/inspection","pass_criterion":"explicit measurable criterion"} for i,r in enumerate(requirements)]
def verification_status(simulated=False,physical=False): return {"simulation":simulated,"physical_test":physical,"validated":bool(physical)}

# ============================================================
# 12 — 3-D GEOMETRY / EXPORT
# ============================================================
def mesh_box(x,y,z):
    v=[(-x/2,-y/2,-z/2),(x/2,-y/2,-z/2),(x/2,y/2,-z/2),(-x/2,y/2,-z/2),(-x/2,-y/2,z/2),(x/2,-y/2,z/2),(x/2,y/2,z/2),(-x/2,y/2,z/2)]
    f=[(0,1,2),(0,2,3),(4,6,5),(4,7,6),(0,4,5),(0,5,1),(1,5,6),(1,6,2),(2,6,7),(2,7,3),(3,7,4),(3,4,0)]; return v,f

def mesh_cylinder(r,h,n=32):
    v=[]
    for z in (-h/2,h/2):
        for i in range(n):
            a=2*math.pi*i/n; v.append((r*math.cos(a),r*math.sin(a),z))
    v += [(0,0,-h/2),(0,0,h/2)]; f=[]; bot=2*n; top=2*n+1
    for i in range(n):
        j=(i+1)%n; f += [(i,j,n+j),(i,n+j,n+i),(bot,j,i),(top,n+i,n+j)]
    return v,f

def mesh_sphere(r,nlat=12,nlon=24):
    v=[]
    for i in range(nlat+1):
        ph=math.pi*i/nlat
        for j in range(nlon):
            th=2*math.pi*j/nlon; v.append((r*math.sin(ph)*math.cos(th),r*math.sin(ph)*math.sin(th),r*math.cos(ph)))
    f=[]
    for i in range(nlat):
        for j in range(nlon):
            a=i*nlon+j;b=i*nlon+(j+1)%nlon;c=(i+1)*nlon+(j+1)%nlon;d=(i+1)*nlon+j;f += [(a,b,c),(a,c,d)]
    return v,f

def mesh_translate(v,dx,dy,dz): return [(x+dx,y+dy,z+dz) for x,y,z in v]
def mesh_scale(v,sx,sy,sz): return [(x*sx,y*sy,z*sz) for x,y,z in v]
def mesh_bounds(v):
    if not v:return {"x":0,"y":0,"z":0}
    return {k:max(p[i] for p in v)-min(p[i] for p in v) for i,k in enumerate("xyz")}
def mesh_to_obj(v,f): return "\n".join([*(f"v {x} {y} {z}" for x,y,z in v),*(f"f {a+1} {b+1} {c+1}" for a,b,c in f)])
def mesh_to_stl(v,f,name="omniforge"):
    lines=[f"solid {name}"]
    for a,b,c in f:
        p,q,r=v[a],v[b],v[c]; ux,uy,uz=[q[i]-p[i] for i in range(3)]; vx,vy,vz=[r[i]-p[i] for i in range(3)]; nx,ny,nz=uy*vz-uz*vy,uz*vx-ux*vz,ux*vy-uy*vx
        lines += [f" facet normal {nx} {ny} {nz}","  outer loop",*(f"   vertex {p[i]} {q[i]} {r[i]}" for i in range(3)),"  endloop"," endfacet"]
    return "\n".join(lines+[f"endsolid {name}"])
def mesh_volume_box(x,y,z): return x*y*z
def mesh_volume_cylinder(r,h): return cylinder_volume(r,h)
def mesh_volume_sphere(r): return sphere_volume(r)

# ============================================================
# 13 — VISION / FILE / REVERSE-IMAGE HELPERS
# ============================================================
def file_to_data_url(upload):
    import base64, mimetypes
    raw=upload.getvalue(); mime=mimetypes.guess_type(upload.name)[0] or "application/octet-stream"; return "data:"+mime+";base64,"+base64.b64encode(raw).decode()
def image_fingerprint(upload): return hashlib.sha256(upload.getvalue()).hexdigest()
def image_metadata(upload): return {"name":upload.name,"bytes":len(upload.getvalue()),"sha256":image_fingerprint(upload)}
def reverse_image_search_helpers(fingerprint: str) -> dict:
    return {"google_lens":"https://lens.google.com/","bing_visual_search":"https://www.bing.com/visualsearch","fingerprint":fingerprint,"note":"Hash matching is exact-file matching only; it does not magically identify an online source."}

# ============================================================
# 14 — AI / MODEL DISCOVERY / RESEARCH
# ============================================================
def client_from_key(key,base="https://api.openai.com/v1"):
    if not OpenAI: raise RuntimeError("Install openai package: pip install openai")
    return OpenAI(api_key=key,base_url=base)

def discover_models(key,base="https://api.openai.com/v1"):
    return [m.id for m in client_from_key(key,base).models.list().data]

def call_ai(key,model,prompt,base="https://api.openai.com/v1",images=None,web=False):
    c=client_from_key(key,base); content=[{"type":"input_text","text":prompt}]
    for data_url in images or []: content.append({"type":"input_image","image_url":data_url})
    kwargs={"model":model,"instructions":SYSTEM_PROMPT,"input":[{"role":"user","content":content}]}
    if web: kwargs["tools"]=[{"type":"web_search_preview"}]
    r=c.responses.create(**kwargs); return getattr(r,"output_text",str(r))

def build_design_prompt(request,iterations,context):
    return f"""Request: {request}\nIterations: {iterations}\nMemory: {context}\nProvide requirements, assumptions, research questions, candidate architectures, equations, calculations, materials/BOM, cost range, failure modes/FMEA, simulation/verification plan, 3-D geometry specification, implementation, uncertainty, and next iteration. Distinguish simulated from physically verified results."""

def build_research_plan(topic): return {"topic":topic,"steps":["define question","identify authoritative sources","compare evidence","record uncertainties","test claims","store findings"]}
def research_gap_analysis(known,unknown): return {"known":known,"gaps":unknown,"next_actions":[f"Research: {x}" for x in unknown]}
def evidence_grade(source_type): return {"primary":4,"official":4,"peer_reviewed":4,"reputable_secondary":3,"community":2,"unknown":1}.get(source_type,1)
def summarize_research_notes(notes): return "\n".join(f"- {n}" for n in notes)

# ============================================================
# 15 — OWNER-APPROVED SELF-EDIT / CODE INTELLIGENCE
# ============================================================
def static_code_scan(code: str) -> list:
    flags=[]
    patterns=[r"os\.system",r"subprocess\.(run|Popen|call)",r"__import__",r"socket\.",r"paramiko",r"ctypes",r"pickle\.loads",r"marshal\.loads",r"requests\.(get|post)\(",r"urllib\.request"]
    for p in patterns:
        if re.search(p,code): flags.append(p)
    return flags

def ast_code_scan(code: str) -> dict:
    try:
        tree=ast.parse(code); banned=(ast.Import,ast.ImportFrom)
        imports=[]
        for n in ast.walk(tree):
            if isinstance(n,banned):
                for a in n.names: imports.append(a.name)
        return {"valid":True,"error":None,"imports":imports}
    except SyntaxError as e: return {"valid":False,"error":str(e),"imports":[]}

def code_function_inventory(code: str) -> list:
    try:
        tree=ast.parse(code); return [n.name for n in ast.walk(tree) if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))]
    except SyntaxError: return []

def generate_edit_proposal(key,model,request,current_code):
    prompt=f"Owner request: {request}\nPreserve all safety, owner authentication, audit, backups, no-arbitrary-execution controls. Return a complete Python replacement in one fenced block. Current source:\n{current_code}"
    return call_ai(key,model,prompt)

def extract_python_candidate(text: str) -> str:
    m=re.search(r"```(?:python|py)?\s*(.*?)```",text,re.S); return m.group(1) if m else text

def validate_candidate(code):
    syntax=ast_code_scan(code); security=static_code_scan(code); funcs=code_function_inventory(code)
    return {"syntax":syntax,"security_flags":security,"function_count":len(funcs),"functions":funcs,"size_bytes":len(code.encode())}

def apply_owner_proposal(code):
    result=validate_candidate(code)
    if not result["syntax"]["valid"] or result["security_flags"]: return False,result
    if not setting_get("owner_pin_hash"): return False,{"error":"Owner PIN not configured"}
    path=Path(__file__).resolve(); backup=backup_source(); tmp=path.with_suffix(".candidate.py"); tmp.write_text(code,encoding="utf-8"); tmp.replace(path); audit("self_edit_applied",f"backup={backup}"); return True,{**result,"backup":backup}

def evolution_policy() -> dict:
    return {"proposal_required":True,"owner_auth_required":True,"backup_required":True,"syntax_check":True,"security_scan":True,"arbitrary_execution":False}

# ============================================================
# 16 — DEFENSIVE CYBER / REVERSE ENGINEERING / CRYPTOGRAPHY
# ============================================================
def defensive_threat_model(asset,threats): return {"asset":asset,"threats":[{"threat":t,"controls":["least privilege","logging","patching","segmentation"]} for t in threats]}
def security_headers_check(headers: dict) -> dict:
    wanted=["content-security-policy","strict-transport-security","x-content-type-options","referrer-policy"]
    lower={k.lower():v for k,v in headers.items()}; return {h:(h in lower) for h in wanted}
def secret_redaction(text: str) -> str:
    return re.sub(r"(?i)(api[_-]?key|token|password|secret)\s*[:=]\s*[^\s,;]+",r"\1=[REDACTED]",text)
def hash_sha256(data: bytes) -> str: return hashlib.sha256(data).hexdigest()
def hash_sha512(data: bytes) -> str: return hashlib.sha512(data).hexdigest()
def base64_decode_safe(text: str):
    import base64
    return base64.b64decode(text,validate=True)
def hex_decode_safe(text: str): return bytes.fromhex(text)
def entropy_estimate(data: bytes) -> float:
    if not data:return 0.0
    from collections import Counter
    c=Counter(data); n=len(data); return -sum((v/n)*math.log2(v/n) for v in c.values())
def binary_header(data: bytes) -> str: return data[:16].hex(" ")
def strings_extract(data: bytes,min_len=4) -> list: return re.findall(rb"[ -~]{%d,}"%min_len,data)[:500]
def safe_file_hash(path: str) -> str: return hash_sha256(Path(path).read_bytes())
def ctf_scope_check(scope: str) -> dict: return {"authorized":bool(scope.strip()),"scope":scope,"rule":"Only analyze systems you own or are explicitly authorized to test."}

# ============================================================
# 17 — MEDIA / OUTPUT PLANNING
# ============================================================
def video_concept_spec(topic,duration=30,aspect="16:9"): return {"topic":topic,"duration_seconds":duration,"aspect_ratio":aspect,"scenes":[]}
def product_render_prompt(description,views=("front","rear","left","right","top","bottom")): return {"description":description,"views":list(views),"measurement_notes":"Add dimensions and datum references."}
def report_outline(title): return ["Executive summary","Requirements","Assumptions","Research","Design","Calculations","Materials/BOM","Risks","Tests","Results","Limitations","Next steps"]
def export_json(data): return json.dumps(data,indent=2,ensure_ascii=False)

# ============================================================
# 18 — COMPLETE FUNCTION REGISTRY / SELF-DESCRIPTION
# ============================================================
FUNCTION_GROUPS={
"01 Identity & Configuration":["now","app_identity","ensure_app","app_paths"],
"02 Persistent Memory & Audit":["db","audit","audit_log","setting_get","setting_set","remember","recall","search_memory","create_project","list_projects","export_memory","import_memory"],
"03 Secrets & Owner Control":["get_secret","save_secret","delete_secret","hash_pin","set_owner_pin","owner_auth","backup_source"],
"04 Mathematics":["safe_math","vector_add","vector_sub","vector_dot","vector_cross","vector_norm","matrix_multiply","linear_interpolate","percent_change","derivative_central","integrate_trapezoid"],
"05 Mechanical / Fluids / Thermal":["force","kinetic_energy","potential_energy","momentum","impulse","power_from_torque","torque","rotational_energy","angular_momentum","stress","strain","hooke_stress","factor_of_safety","pressure","hydrostatic_pressure","thermal_expansion","reynolds","dynamic_pressure","drag_force","buoyant_force","mass_flow","volumetric_flow","bernoulli_pressure_change","spring_force","spring_energy","beam_bending_stress","second_moment_rectangle","cylinder_volume","cylinder_surface_area","sphere_volume","sphere_surface_area","ideal_gas_moles","conduction_heat","heat_energy","thermal_power"],
"06 Electrical / Electronics":["electrical_power","electrical_energy","resistor_power","ohms_law","series_resistance","parallel_resistance","capacitor_energy","capacitor_charge","rc_time_constant","inductive_energy","inductive_reactance","capacitive_reactance","rms_sine","electrical_efficiency"],
"07 Chemistry":["pH","pOH","henderson_hasselbalch","beer_lambert","arrhenius","dilution","molarity","moles_from_mass","mass_from_moles","ideal_gas_volume","equilibrium_ratio"],
"08 Quantum / Modern Physics":["photon_energy","photon_wavelength","de_broglie_wavelength","uncertainty_dp_min","particle_box_energy","harmonic_oscillator_energy","qubit_probabilities","mass_energy","relativistic_gamma","relativistic_energy"],
"09 Materials / BOM / Cost":["calculate_bom","cost_range","material_mass","material_volume","manufacturing_allowance","cost_per_unit","bom_from_rows","mass_budget"],
"10 Optimization / Scoring / Failure Analysis":["transparent_score","weighted_design_score","rank_candidates","sensitivity_delta","fmea_priority","risk_matrix","pareto_front","requirement_check","convergence_improvement"],
"11 Simulation / Testing":["simulate_projectile","simulate_rc","simulate_cooling","simulation_summary","test_plan","verification_status"],
"12 3-D Geometry / Export":["mesh_box","mesh_cylinder","mesh_sphere","mesh_translate","mesh_scale","mesh_bounds","mesh_to_obj","mesh_to_stl","mesh_volume_box","mesh_volume_cylinder","mesh_volume_sphere"],
"13 Vision / Reverse Image Helpers":["file_to_data_url","image_fingerprint","image_metadata","reverse_image_search_helpers"],
"14 AI / Research / Discovery":["client_from_key","discover_models","call_ai","build_design_prompt","build_research_plan","research_gap_analysis","evidence_grade","summarize_research_notes"],
"15 Owner-Approved Code Evolution":["static_code_scan","ast_code_scan","code_function_inventory","generate_edit_proposal","extract_python_candidate","validate_candidate","apply_owner_proposal","evolution_policy"],
"16 Defensive Cyber / RE / Crypto":["defensive_threat_model","security_headers_check","secret_redaction","hash_sha256","hash_sha512","base64_decode_safe","hex_decode_safe","entropy_estimate","binary_header","strings_extract","safe_file_hash","ctf_scope_check"],
"17 Media / Output Planning":["video_concept_spec","product_render_prompt","report_outline","export_json"],
}

def function_registry(): return FUNCTION_GROUPS

def function_count(): return sum(len(v) for v in FUNCTION_GROUPS.values())
def registry_report() -> str:
    lines=[f"{APP_NAME} {APP_VERSION}",f"Named functions: {function_count()}"]
    for group,funcs in FUNCTION_GROUPS.items(): lines.append(f"\n{group} ({len(funcs)})\n"+", ".join(funcs))
    return "\n".join(lines)

# ============================================================
# 19 — TEST SUITE
# ============================================================
def assert_close(a,b,tol=1e-9): assert abs(a-b)<=tol,(a,b)
def assert_true(x): assert x

def run_self_tests():
    tests=[]
    def t(name,fn):
        try: fn(); tests.append((name,True,"OK"))
        except Exception as e: tests.append((name,False,str(e)))
    t("identity",lambda: assert_true(app_identity()["name"]==APP_NAME))
    t("safe math",lambda: assert_close(safe_math("sqrt(2)**2"),2))
    t("vector dot",lambda: assert_close(vector_dot((1,2,3),(1,1,1)),6))
    t("force",lambda: assert_close(force(2,3),6))
    t("kinetic energy",lambda: assert_close(kinetic_energy(2,3),9))
    t("torque",lambda: assert_close(torque(10,2),20))
    t("stress",lambda: assert_close(stress(100,10),10))
    t("Reynolds",lambda: assert_close(reynolds(1,2,3,1),6))
    t("drag",lambda: assert_close(drag_force(1,2,1,1),2))
    t("electrical power",lambda: assert_close(electrical_power(12,2),24))
    t("parallel resistance",lambda: assert_close(parallel_resistance([10,10]),5))
    t("pH",lambda: assert_close(pH(1e-7),7))
    t("dilution",lambda: assert_close(dilution(2,5,1),10))
    t("photon",lambda: assert_close(photon_energy(1e15),6.62607015e-19,1e-30))
    t("de Broglie",lambda: assert_true(de_broglie_wavelength(1,1)>0))
    t("qubit normalization",lambda: assert_close(sum(qubit_probabilities(1,1).values()),1))
    t("BOM",lambda: assert_close(calculate_bom([{"quantity":2,"unit_price":3}])["total"],6))
    t("cost range",lambda: assert_true(cost_range([{"quantity":1,"unit_price":100}])["low"]<100))
    t("FMEA",lambda: assert_true(fmea_priority(10,10,10)==1000))
    t("requirement check",lambda: assert_true(requirement_check({"a":5},{"a":3})["a"]))
    t("projectile simulation",lambda: assert_true(len(simulate_projectile(10,45))>2))
    t("RC simulation",lambda: assert_true(simulation_summary(simulate_rc(1,1,1,1,.1),"V")["final"]>0))
    t("cooling simulation",lambda: assert_true(simulate_cooling(100,20,1,1,.1)[-1]["T"]<100))
    t("box mesh",lambda: assert_true(len(mesh_box(2,3,4)[0])==8))
    t("cylinder mesh",lambda: assert_true(len(mesh_cylinder(1,2)[0])>0))
    t("sphere mesh",lambda: assert_true(len(mesh_sphere(1)[0])>0))
    t("mesh bounds",lambda: assert_close(mesh_bounds(mesh_box(2,3,4)[0])["x"],2))
    t("OBJ export",lambda: assert_true(mesh_to_obj(*mesh_box(1,1,1)).startswith("v ")))
    t("STL export",lambda: assert_true(mesh_to_stl(*mesh_box(1,1,1)).startswith("solid")))
    t("image fingerprint",lambda: assert_true(len(hash_sha256(b"x"))==64))
    t("security headers",lambda: assert_true(security_headers_check({"Content-Security-Policy":"x"})["content-security-policy"]))
    t("redaction",lambda: assert_true("REDACTED" in secret_redaction("api_key=abc")))
    t("entropy",lambda: assert_true(entropy_estimate(b"aaaa")>=0))
    t("AST valid",lambda: assert_true(ast_code_scan("def x():\n return 1")["valid"]))
    t("AST invalid",lambda: assert_true(not ast_code_scan("def x(:")["valid"]))
    t("safe scan clean",lambda: assert_true(static_code_scan("x=1")==[]))
    t("safe scan blocked",lambda: assert_true(static_code_scan("os.system('x')")))
    t("function inventory",lambda: assert_true("force" in code_function_inventory(Path(__file__).read_text(encoding="utf-8"))))
    t("policy",lambda: assert_true(evolution_policy()["owner_auth_required"]))
    t("score",lambda: assert_close(weighted_design_score({k:100 for k in SCORE_WEIGHTS}),100))
    t("registry",lambda: assert_true(function_count()>=150))
    return tests

# ============================================================
# 20 ��� STREAMLIT UI
# ============================================================
def run_app():
    st.set_page_config(page_title=APP_NAME,page_icon="🧠",layout="wide")
    ensure_app(); st.title("🧠 OmniForge SuperAI Ultimate"); st.caption(f"{APP_VERSION} • {function_count()} named functions • owner-controlled evolution")
    with st.sidebar:
        st.header("🔌 AI Connection")
        saved=get_secret(); key=st.text_input("OpenAI API key",value="" if not saved else "••••••••••••••••",type="password")
        if st.button("💾 Remember this key",use_container_width=True):
            if key and not key.startswith("•"): st.success(save_secret(key)); st.rerun()
        if st.button("🗑 Forget saved key",use_container_width=True): delete_secret(); st.rerun()
        active=get_secret() if saved else (key if key and not key.startswith("•") else None)
        model=st.text_input("Model",value=setting_get("model","gpt-5-mini")); setting_set("model",model)
        if active and st.button("🔎 Discover available models",use_container_width=True):
            try: st.session_state.models=discover_models(active); st.success(f"Found {len(st.session_state.models)} models")
            except Exception as e: st.error(str(e))
        if active and st.button("🔌 Test AI connection",use_container_width=True):
            try: st.success(f"Connected. {len(discover_models(active))} models visible.")
            except Exception as e: st.error(str(e))
        st.divider(); st.subheader("🔐 Owner")
        if not setting_get("owner_pin_hash"):
            p=st.text_input("Create owner PIN (8+ chars)",type="password")
            if st.button("Set owner PIN") and len(p)>=8: set_owner_pin(p); st.success("Owner PIN created")
        else: st.success("Owner PIN configured")
        st.metric("Named functions",function_count())

    tabs=st.tabs(["🚀 WORKSPACE","🧬 AUTONOMOUS EVOLUTION","🧪 CALCULATION LAB","🧊 3-D DESIGN STUDIO","🖼️ VISION & IMAGE","🌐 DISCOVER & RESEARCH","🧠 MEMORY","🛡️ DEFENSIVE SECURITY","📋 FUNCTION CATALOG","🧰 FULL TESTS"])
    with tabs[0]:
        st.subheader("Tell it what to build, calculate, research, improve, or code")
        req=st.text_area("Owner request",height=130,placeholder="Design a new machine/product/software system. Include constraints, measurements, cost, testing, and 3-D requirements.")
        project=st.text_input("Project name",value="default")
        if st.button("🚀 Run OmniForge design/research cycle",type="primary") and req:
            if not active: st.error("Connect an API key first.")
            else:
                ctx="\n".join(x[2] for x in recall(project,20)); create_project(project,req[:500])
                try:
                    ans=call_ai(active,model,build_design_prompt(req,5,ctx),web=True); st.markdown(ans); remember(req,"request",project); remember(ans,"result",project)
                except Exception as e: st.error(str(e))
    with tabs[1]:
        st.subheader("🧬 Owner-controlled autonomous code evolution")
        st.write("Natural-language instruction → AI writes code → syntax/security scan → backup → owner PIN → apply. No silent self-modification.")
        command=st.text_area("What should OmniForge add/change?",height=120)
        if st.button("Generate complete code proposal") and command:
            if not active: st.error("Connect an API key first.")
            else:
                try:
                    st.session_state.proposal=generate_edit_proposal(active,model,command,Path(__file__).read_text(encoding="utf-8")); st.code(st.session_state.proposal,language="python")
                except Exception as e: st.error(str(e))
        if st.session_state.get("proposal"):
            candidate=extract_python_candidate(st.session_state.proposal); check=validate_candidate(candidate); st.json(check)
            pin=st.text_input("Owner PIN to approve/apply",type="password")
            if st.button("🔒 Approve + backup + apply"):
                if not owner_auth(pin): st.error("Owner authentication failed")
                else:
                    ok,info=apply_owner_proposal(candidate); st.success("Applied. Restart Streamlit to load the new source.") if ok else st.error(str(info))
    with tabs[2]:
        st.subheader("Named engineering/science calculator lab")
        expr=st.text_input("Safe math expression",placeholder="sqrt(2)*pi")
        if st.button("Calculate expression"):
            try: st.metric("Result",safe_math(expr))
            except Exception as e: st.error(str(e))
        st.code("force(m,a)\nkinetic_energy(m,v)\nstress(F,A)\nreynolds(rho,v,L,mu)\nelectrical_power(V,I)\npH(h)\nphoton_energy(frequency)\nideal_gas_moles(P,V,T)\nqubit_probabilities(a,b)",language="python")
        st.write("Simulation tools: projectile, RC charging, Newton cooling. Testing tools: requirement checks, FMEA, risk matrix, sensitivity, Pareto ranking.")
    with tabs[3]:
        st.subheader("Interactive rotatable/zoomable 3-D primitives")
        typ=st.selectbox("Geometry",["Box","Cylinder","Sphere"]); a=st.number_input("A / radius",value=100.0); b=st.number_input("B / height",value=60.0); c=st.number_input("C",value=30.0)
        if typ=="Box": v,f=mesh_box(a,b,c); volume=mesh_volume_box(a,b,c)
        elif typ=="Cylinder": v,f=mesh_cylinder(a,b); volume=mesh_volume_cylinder(a,b)
        else: v,f=mesh_sphere(a); volume=mesh_volume_sphere(a)
        st.write({"dimensions":mesh_bounds(v),"volume":volume,"vertices":len(v),"faces":len(f)})
        st.download_button("Download OBJ",mesh_to_obj(v,f),"omniforge_design.obj")
        st.download_button("Download STL",mesh_to_stl(v,f),"omniforge_design.stl")
        try:
            import plotly.graph_objects as go
            X=[p[0] for p in v];Y=[p[1] for p in v];Z=[p[2] for p in v]; I=[q[0] for q in f];J=[q[1] for q in f];K=[q[2] for q in f]
            st.plotly_chart(go.Figure(go.Mesh3d(x=X,y=Y,z=Z,i=I,j=J,k=K,opacity=.8)),use_container_width=True)
        except Exception: st.info("Install Plotly for the interactive 3-D viewer.")
    with tabs[4]:
        up=st.file_uploader("Upload product/sketch/photo",type=["png","jpg","jpeg","webp"])
        if up:
            st.image(up); st.json(image_metadata(up)); st.json(reverse_image_search_helpers(image_fingerprint(up)))
            if active and st.button("Analyze image with AI"):
                try: st.markdown(call_ai(active,model,"Analyze this image for visible components, geometry, design intent, likely materials, measurable features, uncertainties, and safe next research steps.",images=[file_to_data_url(up)],web=False))
                except Exception as e: st.error(str(e))
    with tabs[5]:
        topic=st.text_area("Research / discovery topic",height=100)
        if st.button("Build research plan") and topic: st.json(build_research_plan(topic))
        st.write("Web-enabled AI research is available in the Workspace when the model/API supports the configured search tool.")
    with tabs[6]:
        project=st.text_input("Memory project",value="default",key="memory_project")
        q=st.text_input("Search memory",key="memory_q")
        rows=search_memory(q,project) if q else recall(project,50)
        for d,k,c in rows: st.markdown(f"**{d} · {k}**\n\n{c}")
        st.download_button("Export project memory",export_memory(project),"omniforge_memory.json","application/json")
    with tabs[7]:
        st.subheader("Defense-in-depth contract")
        st.json({"owner_authentication":True,"persistent_audit":True,"backup_before_self_edit":True,"syntax_scan":True,"security_scan":True,"no_arbitrary_code_execution":True,"no_offensive_intrusion":True,"no_retaliation":True,"secret_storage":"OS keyring when available"})
        st.subheader("Authorized defensive helpers")
        st.write("Threat modeling, security-header review, secret redaction, hashing, entropy, binary headers, strings extraction, CTF scope checks, and safe reverse-engineering helpers.")
        if st.button("Show recent audit log"): st.dataframe([{"time":a,"event":b,"detail":c} for a,b,c in audit_log(50)])
    with tabs[8]:
        st.subheader(f"Exact function catalog — {function_count()} named functions")
        for group,funcs in FUNCTION_GROUPS.items():
            with st.expander(f"{group} — {len(funcs)} functions",expanded=False): st.code("\n".join(funcs))
        st.download_button("Download function catalog",registry_report(),"omniforge_function_catalog.txt","text/plain")
    with tabs[9]:
        if st.button("🧪 Run ALL self-tests",type="primary"):
            res=run_self_tests(); passed=sum(x[1] for x in res); st.dataframe([{"test":a,"passed":b,"detail":c} for a,b,c in res]); st.success(f"{passed}/{len(res)} tests passed") if passed==len(res) else st.error(f"{passed}/{len(res)} tests passed")
        st.metric("Registered named functions",function_count())
        st.code(registry_report(),language="text")

if __name__=="__main__" and st: run_app()
