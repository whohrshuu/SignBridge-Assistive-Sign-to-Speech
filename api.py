"""SignBridge public MVP API. Supabase Auth validates JWTs; PostgREST enforces RLS."""
import os, re, json, csv, io, math
from collections import Counter
from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
import httpx
from pydantic import BaseModel, Field, field_validator

URL=os.getenv("SUPABASE_URL","").rstrip("/")
KEY=os.getenv("SUPABASE_PUBLISHABLE_KEY",os.getenv("SUPABASE_ANON_KEY",""))
ORIGINS=[x.strip() for x in os.getenv("FRONTEND_ORIGINS","").split(",") if x.strip()]
app=FastAPI(title="SignBridge private API", docs_url=None, redoc_url=None)
app.add_middleware(CORSMiddleware, allow_origins=ORIGINS, allow_credentials=False, allow_methods=["GET","POST","DELETE","PATCH"], allow_headers=["Authorization","Content-Type"], max_age=600)
LABEL=re.compile(r"^[A-Za-z][A-Za-z0-9 _'-]{0,47}$")
EVENTS={"recognized","quick","spoken","saved"}
class Sample(BaseModel):
    label: str
    handedness: str="Unknown"
    landmarks: list[dict[str,float]]
    @field_validator("label")
    @classmethod
    def label_ok(cls,v):
        if not LABEL.fullmatch(v.strip()): raise ValueError("Invalid label")
        return v.strip()
class Gesture(BaseModel):
    handedness: str="Unknown"
    landmarks: list[dict[str,float]]
class History(BaseModel):
    phrase: str=Field(min_length=1,max_length=500)
    event_type: str="recognized"
    source: str=Field(default="gesture", min_length=1,max_length=32)
def validate_gesture(g):
    if g.handedness not in ("Left","Right","Unknown") or len(g.landmarks)!=21:
        raise HTTPException(422,"21 landmarks and valid handedness required")
    for p in g.landmarks:
        if set(p)!= {"x","y","z"} or any(not math.isfinite(p[k]) or abs(p[k])>10 for k in ("x","y","z")):
            raise HTTPException(422,"Invalid coordinates")
    normalized(g.landmarks,g.handedness)
def normalized(points, handedness):
    origin=points[0]; mirror=-1 if handedness=="Left" else 1
    v=[((p["x"]-origin["x"])*mirror,p["y"]-origin["y"],p["z"]-origin["z"]) for p in points]
    scale=max(math.hypot(x,y) for x,y,z in v)
    if scale<1e-5: raise HTTPException(422,"Hand landmarks too close together")
    return [n/scale for xyz in v for n in xyz]
async def identity(request: Request):
    token=request.headers.get("authorization","")
    if not token.startswith("Bearer ") or not URL or not KEY: raise HTTPException(401,"Authentication required")
    jwt=token[7:]
    async with httpx.AsyncClient(timeout=10) as client:
        try: r=await client.get(f"{URL}/auth/v1/user",headers={"apikey":KEY,"Authorization":f"Bearer {jwt}"})
        except httpx.HTTPError: raise HTTPException(503,"Auth service unavailable")
    if r.status_code != 200: raise HTTPException(401,"Invalid or expired session")
    user=r.json()
    if not user.get("id"): raise HTTPException(401,"Unknown user")
    return {"id":user["id"],"jwt":jwt}
async def db(method, table, identity, params=None, payload=None, prefer=None):
    headers={"apikey":KEY,"Authorization":f"Bearer {identity['jwt']}","Content-Type":"application/json"}
    if prefer: headers["Prefer"]=prefer
    async with httpx.AsyncClient(timeout=15) as client:
        try: r=await client.request(method,f"{URL}/rest/v1/{table}",headers=headers,params=params,json=payload)
        except httpx.HTTPError: raise HTTPException(503,"Database unavailable")
    if r.status_code>=400:
        if r.status_code in (401,403): raise HTTPException(403,"Database access denied")
        raise HTTPException(503 if r.status_code>=500 else 422,"Database request failed")
    return r.json() if r.content else []
@app.get("/api/health")
def health(): return {"status":"ok","service":"SignBridge API"}
@app.get("/api/me")
async def me(user=Depends(identity)): return {"id":user["id"]}
@app.get("/api/history")
async def history(limit:int=25,user=Depends(identity)):
    limit=max(1,min(limit,100))
    return {"items":await db("GET","recognition_history",user,{"select":"id,event_type,phrase,source,created_at","user_id":f"eq.{user['id']}","order":"created_at.desc","limit":limit})}
@app.post("/api/history",status_code=201)
async def save_history(item:History,user=Depends(identity)):
    if item.event_type not in EVENTS: raise HTTPException(422,"Invalid event")
    result=await db("POST","recognition_history",user,payload=[{"user_id":user["id"],**item.model_dump()}],prefer="return=representation")
    return {"item":result[0]}
@app.delete("/api/history")
async def clear_history(user=Depends(identity)):
    await db("DELETE","recognition_history",user,{"user_id":f"eq.{user['id']}"})
    return {"deleted":True}
@app.get("/api/samples")
async def samples(limit:int=100,user=Depends(identity)):
    limit=max(1,min(limit,500))
    return {"items":await db("GET","gesture_samples",user,{"select":"id,label,handedness,created_at","user_id":f"eq.{user['id']}","order":"created_at.desc","limit":limit})}
async def all_samples(user):
    rows=[]
    for offset in range(0,2000,500):
        page=await db("GET","gesture_samples",user,{"select":"id,label,handedness,landmarks,created_at","user_id":f"eq.{user['id']}","order":"created_at.desc,id.desc","limit":500,"offset":offset})
        rows.extend(page)
        if len(page)<500: break
    return rows
@app.post("/api/samples",status_code=201)
async def save_sample(item:Sample,user=Depends(identity)):
    validate_gesture(item)
    rows=await all_samples(user)
    if len(rows)>=2000: raise HTTPException(409,"2000-sample account limit reached")
    r=await db("POST","gesture_samples",user,payload=[{"user_id":user["id"],**item.model_dump()}],prefer="return=representation")
    return {"id":r[0]["id"],"label":r[0]["label"]}
@app.delete("/api/samples")
async def clear_samples(user=Depends(identity)):
    await db("DELETE","gesture_samples",user,{"user_id":f"eq.{user['id']}"})
    return {"deleted":True}
@app.delete("/api/samples/{sample_id}")
async def delete_sample(sample_id:str,user=Depends(identity)):
    if not re.fullmatch(r"[0-9a-fA-F-]{36}",sample_id): raise HTTPException(404,"Not found")
    r=await db("DELETE","gesture_samples",user,{"id":f"eq.{sample_id}","user_id":f"eq.{user['id']}"},prefer="return=representation")
    if not r: raise HTTPException(404,"Not found")
    return {"deleted":True}
@app.get("/api/stats")
async def stats(user=Depends(identity)):
    rows=await all_samples(user)
    counts=Counter(x["label"] for x in rows)
    history=await db("GET","recognition_history",user,{"select":"id","user_id":f"eq.{user['id']}","limit":1001})
    return {"history_count":len(history),"sample_count":len(rows),"labels":dict(counts),"trained_labels":[x for x,n in counts.items() if n>=3]}
@app.post("/api/predict")
async def predict(item:Gesture,user=Depends(identity)):
    validate_gesture(item)
    target=normalized(item.landmarks,item.handedness)
    rows=await all_samples(user)
    counts=Counter(x["label"] for x in rows)
    eligible=sorted(x for x,n in counts.items() if n>=3)
    if not eligible: return {"label":None,"confidence":0,"trained_labels":[],"reason":"Capture at least 3 examples per label"}
    dist=[]
    for row in rows:
        if row["label"] not in eligible: continue
        try: v=normalized(row["landmarks"],row["handedness"])
        except (KeyError,TypeError,HTTPException): continue
        distance=math.sqrt(sum((a-b)**2 for a,b in zip(target,v))/len(target))
        dist.append((distance,row["label"]))
    if not dist: return {"label":None,"confidence":0,"trained_labels":eligible,"reason":"No usable samples"}
    neighbors=sorted(dist)[:5]; votes=Counter(x[1] for x in neighbors)
    winner=sorted(votes,key=lambda x:(-votes[x],min(d for d,l in neighbors if l==x),x))[0]
    nearest=min(d for d,l in neighbors if l==winner)
    confidence=round(max(0,min(1,(votes[winner]/len(neighbors))*(1-nearest/0.18))),3)
    if nearest>0.18 or confidence<0.35:
        return {"label":None,"confidence":confidence,"trained_labels":eligible,"reason":"Unknown or low confidence"}
    return {"label":winner,"confidence":confidence,"trained_labels":eligible,"reason":None}
@app.get("/api/export.json")
async def export_json(user=Depends(identity)):
    return {"format":"SignBridge private landmarks v1","samples":await all_samples(user)}
@app.get("/api/export.csv")
async def export_csv(user=Depends(identity)):
    output=io.StringIO(); writer=csv.writer(output)
    writer.writerow(["id","label","handedness","created_at"]+[f"point_{i}_{axis}" for i in range(21) for axis in "xyz"])
    for item in await all_samples(user):
        writer.writerow([item["id"],item["label"],item["handedness"],item["created_at"]]+[p[k] for p in item["landmarks"] for k in "xyz"])
    return Response(output.getvalue(),media_type="text/csv",headers={"Content-Disposition":'attachment; filename="signbridge-dataset.csv"'})

# Serve the authenticated UI and API from one HTTPS origin on Render.
from pathlib import Path
from fastapi.staticfiles import StaticFiles
@app.get("/config.js", include_in_schema=False)
def public_config():
    safe_key = KEY if not KEY.startswith("sb_secret_") else ""
    # Legacy JWT service_role keys must never be sent to a browser.
    try:
        import base64
        part = KEY.split(".")[1]
        if json.loads(base64.urlsafe_b64decode(part + "=" * (-len(part) % 4))).get("role") == "service_role":
            safe_key = ""
    except (IndexError, ValueError, UnicodeError):
        pass
    return Response("window.SIGNBRIDGE_CONFIG=" + json.dumps({"supabaseUrl": URL, "supabaseAnonKey": safe_key, "apiUrl": ""}) + ";", media_type="application/javascript", headers={"Cache-Control":"no-store"})
app.mount("/", StaticFiles(directory=Path(__file__).resolve().parent / "frontend", html=True), name="frontend")
