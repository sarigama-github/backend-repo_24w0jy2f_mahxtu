import os
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from database import db, create_document, get_documents
from schemas import Task, Activity, Worklog, Note
from bson import ObjectId

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class UpdateTask(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[str] = None
    due_date: Optional[datetime] = None
    tags: Optional[List[str]] = None

class UpdateNote(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    pinned: Optional[bool] = None


# Utility functions

def oid(id_str: str) -> ObjectId:
    try:
        return ObjectId(id_str)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid ID format")


def serialize(doc):
    if not doc:
        return doc
    doc["id"] = str(doc.pop("_id")) if doc.get("_id") else None
    # Convert datetimes to isoformat
    for k, v in list(doc.items()):
        if isinstance(v, datetime):
            doc[k] = v.astimezone(timezone.utc).isoformat()
    return doc


@app.get("/")
def read_root():
    return {"message": "Daily Activity Tracker API is running"}


@app.get("/api/hello")
def hello():
    return {"message": "Hello from the backend API!"}


@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }

    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
            response["database_name"] = getattr(db, 'name', None) or "✅ Connected"
            response["connection_status"] = "Connected"
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️  Available but not initialized"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"

    response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set"

    return response


# Tasks CRUD
@app.get("/api/tasks")
def list_tasks(status: Optional[str] = None):
    try:
        filt = {"status": status} if status else {}
        items = get_documents("task", filt)
        return [serialize(x) for x in items]
    except Exception:
        # Fallback dummy
        return [
            {
                "id": "demo1",
                "title": "Plan the week",
                "description": "Outline top priorities and meetings",
                "status": "in_progress",
                "priority": "high",
                "due_date": datetime.now(timezone.utc).isoformat(),
                "tags": ["planning"],
            },
            {
                "id": "demo2",
                "title": "Deep work block",
                "description": "Focus on project Alpha",
                "status": "pending",
                "priority": "medium",
                "due_date": None,
                "tags": ["focus"],
            },
            {
                "id": "demo3",
                "title": "Review PRs",
                "description": "Check incoming pull requests",
                "status": "done",
                "priority": "low",
                "due_date": None,
                "tags": ["code"],
            },
        ]


@app.post("/api/tasks")
def create_task(task: Task):
    try:
        new_id = create_document("task", task)
        # Log activity
        if db is not None:
            db["activity"].insert_one({
                "type": "task_created",
                "message": f"Created task: {task.title}",
                "related_id": new_id,
                "created_at": datetime.now(timezone.utc),
            })
        return {"id": new_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/api/tasks/{task_id}")
def update_task(task_id: str, payload: UpdateTask):
    if db is None:
        raise HTTPException(status_code=503, detail="Database not configured")
    res = db["task"].find_one_and_update(
        {"_id": oid(task_id)},
        {"$set": {k: v for k, v in payload.model_dump(exclude_unset=True).items()}},
        return_document=True,
    )
    if not res:
        raise HTTPException(status_code=404, detail="Task not found")
    db["activity"].insert_one({
        "type": "task_updated",
        "message": f"Updated task: {res.get('title', '')}",
        "related_id": task_id,
        "created_at": datetime.now(timezone.utc),
    })
    return serialize(res)


@app.delete("/api/tasks/{task_id}")
def delete_task(task_id: str):
    if db is None:
        raise HTTPException(status_code=503, detail="Database not configured")
    res = db["task"].find_one_and_delete({"_id": oid(task_id)})
    if not res:
        raise HTTPException(status_code=404, detail="Task not found")
    db["activity"].insert_one({
        "type": "task_deleted",
        "message": f"Deleted task: {res.get('title', '')}",
        "related_id": task_id,
        "created_at": datetime.now(timezone.utc),
    })
    return {"ok": True}


# Worklogs
@app.get("/api/worklogs")
def list_worklogs():
    try:
        items = get_documents("worklog")
        return [serialize(x) for x in items]
    except Exception:
        today = datetime.now(timezone.utc)
        return [
            serialize({
                "_id": ObjectId(),
                "date": today - timedelta(days=i),
                "hours": h,
                "project": "General",
                "notes": "Demo data",
            }) for i, h in enumerate([6, 7.5, 8, 4, 0, 5, 7])
        ]


@app.post("/api/worklogs")
def create_worklog(work: Worklog):
    try:
        new_id = create_document("worklog", work)
        if db is not None:
            db["activity"].insert_one({
                "type": "work_logged",
                "message": f"Logged {work.hours}h",
                "related_id": new_id,
                "created_at": datetime.now(timezone.utc),
            })
        return {"id": new_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Notes
@app.get("/api/notes")
def list_notes():
    try:
        items = get_documents("note")
        return [serialize(x) for x in items]
    except Exception:
        return [
            {"id": "n1", "title": "Standup at 9:30", "content": "Share progress and blockers", "pinned": True},
            {"id": "n2", "title": "Follow up", "content": "Email client about contract", "pinned": False},
        ]


@app.post("/api/notes")
def create_note(note: Note):
    try:
        new_id = create_document("note", note)
        return {"id": new_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/api/notes/{note_id}")
def update_note(note_id: str, payload: UpdateNote):
    if db is None:
        raise HTTPException(status_code=503, detail="Database not configured")
    res = db["note"].find_one_and_update(
        {"_id": oid(note_id)},
        {"$set": {k: v for k, v in payload.model_dump(exclude_unset=True).items()}},
        return_document=True,
    )
    if not res:
        raise HTTPException(status_code=404, detail="Note not found")
    return serialize(res)


@app.delete("/api/notes/{note_id}")
def delete_note(note_id: str):
    if db is None:
        raise HTTPException(status_code=503, detail="Database not configured")
    res = db["note"].find_one_and_delete({"_id": oid(note_id)})
    if not res:
        raise HTTPException(status_code=404, detail="Note not found")
    return {"ok": True}


# Activities
@app.get("/api/activities")
def list_activities(limit: int = 20):
    try:
        if db is None:
            raise Exception("No DB")
        cursor = db["activity"].find({}).sort("created_at", -1).limit(limit)
        return [serialize(x) for x in cursor]
    except Exception:
        now = datetime.now(timezone.utc)
        demo = [
            {"id": "a1", "type": "task_completed", "message": "Completed 'Review PRs'", "created_at": (now - timedelta(hours=2)).isoformat()},
            {"id": "a2", "type": "work_logged", "message": "Logged 7.5h", "created_at": (now - timedelta(hours=5)).isoformat()},
            {"id": "a3", "type": "note_added", "message": "Added reminder: Standup at 9:30", "created_at": (now - timedelta(days=1)).isoformat()},
        ]
        return demo


# Analytics
@app.get("/api/analytics/weekly")
def weekly_analytics():
    try:
        # Build last 7 days hours and tasks done
        end = datetime.now(timezone.utc)
        start = end - timedelta(days=6)
        results = {"days": [], "hours": [], "tasks_completed": []}

        # Hours
        hours_map = {d.date(): 0 for d in (start + timedelta(days=i) for i in range(7))}
        tasks_map = {d.date(): 0 for d in (start + timedelta(days=i) for i in range(7))}

        if db is not None:
            for wl in db["worklog"].find({"date": {"$gte": start, "$lte": end}}):
                d = wl.get("date")
                if isinstance(d, datetime):
                    hours_map[d.date()] = hours_map.get(d.date(), 0) + float(wl.get("hours", 0))
            for t in db["task"].find({"status": "done"}):
                d = t.get("updated_at") or t.get("created_at")
                if isinstance(d, datetime) and start.date() <= d.date() <= end.date():
                    tasks_map[d.date()] = tasks_map.get(d.date(), 0) + 1
        else:
            # Dummy
            demo_hours = [6, 7.5, 8, 4, 0, 5, 7]
            for i in range(7):
                hours_map[(start + timedelta(days=i)).date()] = demo_hours[i]
            tasks_map[(end - timedelta(days=1)).date()] = 3
            tasks_map[end.date()] = 2

        for i in range(7):
            day = (start + timedelta(days=i)).date()
            results["days"].append(day.strftime("%a"))
            results["hours"].append(round(hours_map.get(day, 0), 2))
            results["tasks_completed"].append(tasks_map.get(day, 0))
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/analytics/monthly")
def monthly_analytics():
    try:
        end = datetime.now(timezone.utc)
        start = end - timedelta(days=29)
        weeks = [
            (start + timedelta(days=i*7), start + timedelta(days=(i+1)*7 - 1))
            for i in range(4)
        ]
        summary = []
        for (ws, we) in weeks:
            hours = 0.0
            tasks_done = 0
            if db is not None:
                for wl in db["worklog"].find({"date": {"$gte": ws, "$lte": we}}):
                    if isinstance(wl.get("date"), datetime):
                        hours += float(wl.get("hours", 0))
                for t in db["task"].find({"status": "done"}):
                    d = t.get("updated_at") or t.get("created_at")
                    if isinstance(d, datetime) and ws.date() <= d.date() <= we.date():
                        tasks_done += 1
            else:
                hours = 32 + 4 * (weeks.index((ws, we)))
                tasks_done = 5 + weeks.index((ws, we))
            summary.append({
                "label": f"W{weeks.index((ws, we)) + 1}",
                "hours": round(hours, 2),
                "tasks_completed": tasks_done,
            })
        return {"weeks": summary}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/seed-dummy")
def seed_dummy():
    if db is None:
        raise HTTPException(status_code=503, detail="Database not configured")
    now = datetime.now(timezone.utc)
    # Insert tasks
    tasks = [
        {"title": "Plan the week", "description": "Outline priorities", "status": "in_progress", "priority": "high", "tags": ["planning"], "created_at": now, "updated_at": now},
        {"title": "Deep work block", "description": "Project Alpha", "status": "pending", "priority": "medium", "tags": ["focus"], "created_at": now, "updated_at": now},
        {"title": "Review PRs", "description": "Check PRs", "status": "done", "priority": "low", "tags": ["code"], "created_at": now - timedelta(days=1), "updated_at": now - timedelta(days=1)},
    ]
    db["task"].insert_many(tasks)
    # Insert worklogs
    for i, h in enumerate([6, 7.5, 8, 4, 0, 5, 7]):
        db["worklog"].insert_one({"date": now - timedelta(days=i), "hours": h, "project": "General", "notes": "Seed"})
    # Insert notes
    db["note"].insert_many([
        {"title": "Standup at 9:30", "content": "Progress & blockers", "pinned": True, "created_at": now, "updated_at": now},
        {"title": "Follow up", "content": "Email client about contract", "pinned": False, "created_at": now, "updated_at": now},
    ])
    return {"ok": True}


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
