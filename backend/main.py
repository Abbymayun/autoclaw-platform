# AutoClaw Platform - Backend
# pip install fastapi uvicorn websockets httpx playwright python-multipart APScheduler aiofiles GitPython

import os, json, asyncio, subprocess, shutil
from datetime import datetime
from pathlib import Path
from typing import Optional
import httpx
from fastapi import FastAPI, WebSocket, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from contextlib import asynccontextmanager
import uvicorn

# ====== CONFIG ======
WORKSPACE = Path("workspace")
MEMORY_DIR = WORKSPACE / "memory"
CONFIG_FILE = WORKSPACE / "config.json"
WORKSPACE.mkdir(exist_ok=True)
MEMORY_DIR.mkdir(exist_ok=True)

def load_config():
    if CONFIG_FILE.exists():
        return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    return {"api_base":"","api_key":"","model":"gpt-4o","feishu_webhook":""}

def save_config(cfg):
    CONFIG_FILE.write_text(json.dumps(cfg,indent=2),encoding="utf-8")

# ====== MEMORY SYSTEM ======
class Memory:
    @staticmethod
    def today_file():
        return MEMORY_DIR / f"{datetime.now().strftime('%Y-%m-%d')}.md"

    @staticmethod
    def store(content: str):
        f = Memory.today_file()
        entry = f"\n## {datetime.now().strftime('%H:%M')}\n{content}\n"
        with open(f,"a",encoding="utf-8") as fp: fp.write(entry)

    @staticmethod
    def recall(days=7):
        ms = []
        for f in sorted(MEMORY_DIR.glob("*.md"),reverse=True)[:days]:
            if f.exists():
                ms.append(f"### {f.stem}\n{f.read_text(encoding='utf-8')[:2000]}")
        return "\n---\n".join(ms)

    @staticmethod
    def get_config(key: str):
        return load_config().get(key)

# ====== CHAT MODULE ======
class ChatRequest(BaseModel):
    message: str
    model: Optional[str] = None

async def chat_with_context(message: str, model: str = None):
    cfg = load_config()
    model = model or cfg.get("model","gpt-4o")
    history = Memory.recall(3)

    payload = {
        "model": model,
        "messages": [
            {"role":"system","content":f"You are AutoClaw, a helpful AI assistant. Context from memory:\n{history[:1500]}"},
            {"role":"user","content": message}
        ],
        "max_tokens": 2000
    }
    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(
            f"{cfg['api_base']}/chat/completions",
            headers={"Authorization":f"Bearer {cfg['api_key']}","Content-Type":"application/json"},
            json=payload
        )
        return r.json()["choices"][0]["message"]["content"]

# ====== BROWSER MODULE ======
class BrowserAction(BaseModel):
    url: str = ""
    task: str = ""
    action_type: str = "open"  # open, search, click, screenshot

async def browser_execute(action: BrowserAction):
    try:
        from playwright.async_api import async_playwright
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            result = ""
            if action.action_type == "open":
                await page.goto(action.url, wait_until="networkidle")
                result = await page.content()
                result = result[:5000]
            elif action.action_type == "search":
                await page.goto(f"https://www.google.com/search?q={action.task}")
                result = await page.inner_text("body")
            elif action.action_type == "screenshot":
                await page.goto(action.url, wait_until="networkidle")
                ss_path = WORKSPACE / "screenshots" / f"{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                ss_path.parent.mkdir(exist_ok=True)
                await page.screenshot(path=str(ss_path), full_page=True)
                result = f"Screenshot saved: {ss_path}"
            await browser.close()
            return {"success":True,"result":result}
    except Exception as e:
        return {"success":False,"error":str(e)}

# ====== SEARCH MODULE ======
async def web_search(query: str, num: int = 5):
    async with httpx.AsyncClient(timeout=15) as client:
        try:
            r = await client.get("https://lite.duckduckgo.com/lite/",params={"q":query})
            return {"success":True,"result":r.text[:3000]}
        except:
            # Fallback via built-in search
            return {"success":True,"result":f"Search for: {query}\n(Configure search API for better results)"}

# ====== SCHEDULER ======
scheduler_jobs = {}

class ScheduleTask(BaseModel):
    name: str
    cron_expr: str  # e.g. "0 9 * * *"
    webhook_url: str = ""
    message: str = ""

async def add_schedule(task: ScheduleTask):
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from apscheduler.triggers.cron import CronTrigger
    scheduler = getattr(add_schedule,"_scheduler",None)
    if not scheduler:
        scheduler = AsyncIOScheduler()
        scheduler.start()
        add_schedule._scheduler = scheduler
    trigger = CronTrigger.from_crontab(task.cron_expr)
    job_id = task.name.replace(" ","_")
    if task.webhook_url:
        async def job_func():
            async with httpx.AsyncClient() as c:
                await c.post(task.webhook_url,json={"text":task.message})
    else:
        async def job_func():
            Memory.store(f"[Cron: {task.name}] {task.message}")
    scheduler.add_job(job_func,trigger,id=job_id,replace_existing=True)
    scheduler_jobs[task.name] = {"cron":task.cron_expr,"status":"active"}
    return {"success":True,"name":task.name}

# ====== GITHUB MODULE ======
class DeployRequest(BaseModel):
    commit_message: str = "AutoClaw Platform Update"
    deploy_target: str = ""  # aliyun|vercel|netlify

async def git_push(message: str):
    try:
        ws = WORKSPACE
        subprocess.run(["git","-C",str(ws),"add","-A"],capture_output=True)
        subprocess.run(["git","-C",str(ws),"commit","-m",message],capture_output=True)
        r = subprocess.run(["git","-C",str(ws),"push"],capture_output=True,text=True)
        return {"success":True,"output":r.stderr or r.stdout}
    except Exception as e:
        return {"success":False,"error":str(e)}

# ====== DEPLOY MODULE ======
async def deploy_to_server(target: str):
    """One-click deploy to cloud server"""
    steps = {
        "vercel": ["vercel --prod"],
        "netlify": ["netlify deploy --prod"],
        "aliyun": [
            "docker build -t autoclaw-platform .",
            "docker save autoclaw-platform | gzip > deploy.tar.gz",
            "# scp deploy.tar.gz root@YOUR_SERVER_IP:/root/",
            "# ssh root@YOUR_SERVER_IP 'docker load < /root/deploy.tar.gz && docker-compose up -d'"
        ]
    }
    cmds = steps.get(target, steps["aliyun"])
    results = []
    for cmd in cmds:
        if cmd.startswith("#"): results.append(cmd); continue
        r = subprocess.run(cmd,shell=True,capture_output=True,text=True,cwd=WORKSPACE)
        results.append(f"$ {cmd}\n{r.stdout}{r.stderr}")
    return {"success":True,"steps":results}

# ====== FASTAPI APP ======
app = FastAPI(title="AutoClaw Platform")
app.add_middleware(CORSMiddleware,allow_origins=["*"],allow_methods=["*"],allow_headers=["*"])

# REST APIs
@app.post("/api/chat")
async def api_chat(req: ChatRequest):
    try: return {"reply": await chat_with_context(req.message, req.model)}
    except Exception as e: return {"reply": f"Error: {e}"}

@app.websocket("/ws/chat")
async def ws_chat(ws: WebSocket):
    await ws.accept()
    cfg = load_config()
    conv = []
    while True:
        msg = await ws.receive_text()
        conv.append({"role":"user","content":msg})
        payload = {"model":cfg["model"],"messages":conv[-20:],"max_tokens":2000,"stream":True}
        try:
            async with httpx.AsyncClient(timeout=120) as client:
                async with client.stream("POST",f"{cfg['api_base']}/chat/completions",
                    headers={"Authorization":f"Bearer {cfg['api_key']}","Content-Type":"application/json"},
                    json=payload) as resp:
                    full = ""
                    async for line in resp.aiter_lines():
                        if line.startswith("data: "):
                            chunk = json.loads(line[6:])
                            delta = chunk.get("choices",[{}])[0].get("delta",{}).get("content","")
                            if delta:
                                full += delta
                                await ws.send_text(delta)
                    conv.append({"role":"assistant","content":full})
        except Exception as e:
            await ws.send_text(f"\n[Error: {e}]")

@app.post("/api/browser")
async def api_browser(action: BrowserAction):
    return await browser_execute(action)

@app.get("/api/search")
async def api_search(q: str):
    return await web_search(q)

@app.post("/api/schedule")
async def api_schedule(task: ScheduleTask):
    return await add_schedule(task)

@app.get("/api/schedule/list")
async def api_schedule_list():
    return {"jobs": list(scheduler_jobs.values())}

@app.post("/api/git/push")
async def api_git_push(req: DeployRequest):
    return await git_push(req.commit_message)

@app.post("/api/deploy")
async def api_deploy(req: DeployRequest):
    return await deploy_to_server(req.deploy_target)

@app.post("/api/memory")
async def api_memory_store(content: str):
    Memory.store(content)
    return {"ok":True}

@app.get("/api/memory/recall")
async def api_memory_recall():
    return {"memory": Memory.recall(7)}

@app.get("/api/config")
async def api_get_config():
    cfg = load_config()
    cfg["api_key"] = cfg.get("api_key","")[:8]+"****" if cfg.get("api_key") else ""
    return cfg

@app.post("/api/config")
async def api_save_config(cfg: dict):
    # Merge with existing
    existing = load_config()
    existing.update(cfg)
    save_config(existing)
    Memory.store("Configuration updated")
    return {"ok":True}

@app.post("/api/upload")
async def api_upload(file: UploadFile = File(...)):
    path = WORKSPACE / "uploads" / file.filename
    path.parent.mkdir(exist_ok=True)
    with open(path,"wb") as f:
        f.write(await file.read())
    return {"path": str(path)}

@app.get("/api/files")
async def api_list_files(path: str = ""):
    p = WORKSPACE / path if path else WORKSPACE
    files = [{"name": f.name, "type": "dir" if f.is_dir() else "file", "size": f.stat().st_size if f.is_file() else 0} for f in p.iterdir()]
    return {"files": files, "path": str(p)}

@app.get("/health")
async def health():
    return {"status":"ok","time":datetime.now().isoformat()}

# Serve frontend
@app.get("/")
async def index():
    return FileResponse("frontend/index.html")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
