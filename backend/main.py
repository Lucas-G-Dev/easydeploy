import os
import httpx
import asyncio
from datetime import datetime
from typing import Optional
from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from contextlib import asynccontextmanager

EASYPANEL_URL = os.getenv("EASYPANEL_URL", "http://localhost:3000")
EASYPANEL_TOKEN = os.getenv("EASYPANEL_TOKEN", "")

action_log = []

def log_action(action: str, service: str, status: str = "ok", detail: str = ""):
    action_log.insert(0, {
        "time": datetime.now().strftime("%H:%M"),
        "action": action,
        "service": service,
        "status": status,
        "detail": detail,
    })
    if len(action_log) > 50:
        action_log.pop()

def ep_headers():
    return {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {EASYPANEL_TOKEN}",
    }

async def trpc_query(procedure: str, input_data: dict = None):
    import json
    params = {}
    if input_data:
        params["input"] = json.dumps({"json": input_data})
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(
            f"{EASYPANEL_URL}/api/trpc/{procedure}",
            headers=ep_headers(),
            params=params,
        )
        r.raise_for_status()
        return r.json()

async def trpc_mutation(procedure: str, payload: dict = None):
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.post(
            f"{EASYPANEL_URL}/api/trpc/{procedure}",
            headers=ep_headers(),
            json={"json": payload or {}},
        )
        r.raise_for_status()
        return r.json()

app = FastAPI(title="EasyDeploy Dashboard")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.join(BASE_DIR, "..", "frontend")

app.mount("/static", StaticFiles(directory=os.path.join(FRONTEND_DIR, "static")), name="static")
templates = Jinja2Templates(directory=os.path.join(FRONTEND_DIR, "templates"))


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/api/projects")
async def list_projects():
    try:
        data = await trpc_query("projects.listProjects")
        return {"ok": True, "data": data.get("result", {}).get("data", {}).get("json", [])}
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@app.get("/api/services")
async def list_all_services():
    """
    O Easypanel não retorna os serviços junto da lista de projetos.
    projects.listProjects só traz nome/metadados do projeto.
    Os serviços de cada projeto vêm de uma chamada separada:
    projects.inspectProject, uma por projeto.
    """
    try:
        projects_data = await trpc_query("projects.listProjects")
        projects = projects_data.get("result", {}).get("data", {}).get("json", [])

        async def fetch_project_services(proj):
            proj_name = proj.get("name", "")
            try:
                detail = await trpc_query("projects.inspectProject", {"projectName": proj_name})
                proj_detail = detail.get("result", {}).get("data", {}).get("json", {})
            except Exception:
                proj_detail = {}
            svc_list = proj_detail.get("services", []) or proj.get("services", [])
            result = []
            for svc in svc_list:
                svc["_project"] = proj_name
                result.append(svc)
            return result

        results = await asyncio.gather(*[fetch_project_services(p) for p in projects])
        services = []
        for r in results:
            services.extend(r)

        return {"ok": True, "data": services}
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


class DeployRequest(BaseModel):
    projectName: str
    serviceName: str

@app.post("/api/deploy")
async def deploy_service(req: DeployRequest):
    try:
        await trpc_mutation("app.deployService", {
            "projectName": req.projectName,
            "serviceName": req.serviceName,
        })
        log_action("Deploy iniciado", f"{req.projectName}/{req.serviceName}", "ok")
        return {"ok": True}
    except Exception as e:
        log_action("Deploy falhou", f"{req.projectName}/{req.serviceName}", "error", str(e))
        raise HTTPException(status_code=502, detail=str(e))


class ServiceActionRequest(BaseModel):
    projectName: str
    serviceName: str

@app.post("/api/restart")
async def restart_service(req: ServiceActionRequest):
    try:
        await trpc_mutation("app.restartService", {
            "projectName": req.projectName,
            "serviceName": req.serviceName,
        })
        log_action("Reiniciado", f"{req.projectName}/{req.serviceName}", "ok")
        return {"ok": True}
    except Exception as e:
        log_action("Restart falhou", f"{req.projectName}/{req.serviceName}", "error", str(e))
        raise HTTPException(status_code=502, detail=str(e))

@app.post("/api/stop")
async def stop_service(req: ServiceActionRequest):
    try:
        await trpc_mutation("app.stopService", {
            "projectName": req.projectName,
            "serviceName": req.serviceName,
        })
        log_action("Serviço parado", f"{req.projectName}/{req.serviceName}", "warn")
        return {"ok": True}
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))

@app.post("/api/start")
async def start_service(req: ServiceActionRequest):
    try:
        await trpc_mutation("app.startService", {
            "projectName": req.projectName,
            "serviceName": req.serviceName,
        })
        log_action("Serviço iniciado", f"{req.projectName}/{req.serviceName}", "ok")
        return {"ok": True}
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))

@app.post("/api/destroy")
async def destroy_service(req: ServiceActionRequest):
    try:
        await trpc_mutation("app.destroyService", {
            "projectName": req.projectName,
            "serviceName": req.serviceName,
        })
        log_action("Serviço deletado", f"{req.projectName}/{req.serviceName}", "warn")
        return {"ok": True}
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


class CreateServiceRequest(BaseModel):
    projectName: str
    serviceName: str
    sourceType: str
    image: Optional[str] = None
    githubOwner: Optional[str] = None
    githubRepo: Optional[str] = None
    githubBranch: Optional[str] = "main"
    domain: Optional[str] = None
    port: Optional[int] = 80

@app.post("/api/create-service")
async def create_service(req: CreateServiceRequest):
    try:
        payload: dict = {
            "projectName": req.projectName,
            "serviceName": req.serviceName,
        }
        if req.sourceType == "image":
            payload["source"] = {"type": "image", "image": req.image}
        else:
            payload["source"] = {
                "type": "github",
                "owner": req.githubOwner,
                "repo": req.githubRepo,
                "ref": req.githubBranch,
                "autoDeploy": True,
            }
        await trpc_mutation("app.createService", payload)

        if req.domain:
            await asyncio.sleep(1)
            await trpc_mutation("domains.addDomain", {
                "projectName": req.projectName,
                "serviceName": req.serviceName,
                "host": req.domain,
                "port": req.port,
                "https": True,
                "www": False,
            })

        await trpc_mutation("app.deployService", {
            "projectName": req.projectName,
            "serviceName": req.serviceName,
        })

        log_action("Serviço criado", f"{req.projectName}/{req.serviceName}", "ok",
                   f"domain: {req.domain}" if req.domain else "")
        return {"ok": True}
    except Exception as e:
        log_action("Criação falhou", f"{req.projectName}/{req.serviceName}", "error", str(e))
        raise HTTPException(status_code=502, detail=str(e))


class AddDomainRequest(BaseModel):
    projectName: str
    serviceName: str
    domain: str
    port: int = 80

@app.post("/api/add-domain")
async def add_domain(req: AddDomainRequest):
    try:
        await trpc_mutation("domains.addDomain", {
            "projectName": req.projectName,
            "serviceName": req.serviceName,
            "host": req.domain,
            "port": req.port,
            "https": True,
            "www": False,
        })
        log_action("Domínio adicionado", f"{req.projectName}/{req.serviceName}", "ok", req.domain)
        return {"ok": True}
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


class RemoveDomainRequest(BaseModel):
    projectName: str
    serviceName: str
    domain: str

@app.post("/api/remove-domain")
async def remove_domain(req: RemoveDomainRequest):
    try:
        await trpc_mutation("domains.removeDomain", {
            "projectName": req.projectName,
            "serviceName": req.serviceName,
            "host": req.domain,
        })
        log_action("Domínio removido", f"{req.projectName}/{req.serviceName}", "warn", req.domain)
        return {"ok": True}
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


@app.get("/api/logs")
async def get_logs():
    return {"ok": True, "data": action_log}


@app.get("/api/health")
async def health():
    try:
        await trpc_query("projects.listProjects")
        return {"ok": True, "panel": EASYPANEL_URL, "connected": True}
    except Exception as e:
        return {"ok": False, "panel": EASYPANEL_URL, "connected": False, "error": str(e)}
