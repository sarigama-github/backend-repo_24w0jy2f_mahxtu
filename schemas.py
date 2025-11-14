"""
Database Schemas

Define your MongoDB collection schemas here using Pydantic models.
These schemas are used for data validation in your application.

Each Pydantic model represents a collection in your database.
Model name is converted to lowercase for the collection name:
- User -> "user" collection
- Product -> "product" collection
- BlogPost -> "blogs" collection
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

# Example schemas (kept for reference):

class User(BaseModel):
    name: str = Field(..., description="Full name")
    email: str = Field(..., description="Email address")
    address: str = Field(..., description="Address")
    age: Optional[int] = Field(None, ge=0, le=120, description="Age in years")
    is_active: bool = Field(True, description="Whether user is active")

class Product(BaseModel):
    title: str = Field(..., description="Product title")
    description: Optional[str] = Field(None, description="Product description")
    price: float = Field(..., ge=0, description="Price in dollars")
    category: str = Field(..., description="Product category")
    in_stock: bool = Field(True, description="Whether product is in stock")

# App schemas:

class Task(BaseModel):
    title: str = Field(..., description="Task title")
    description: Optional[str] = Field(None, description="Task details")
    status: str = Field("pending", description="pending | in_progress | done")
    priority: str = Field("medium", description="low | medium | high")
    due_date: Optional[datetime] = Field(None, description="Due date/time")
    tags: List[str] = Field(default_factory=list)

class Activity(BaseModel):
    type: str = Field(..., description="Type of activity, e.g., task_created, task_completed, work_logged")
    message: str = Field(..., description="Human-friendly message")
    related_id: Optional[str] = Field(None, description="Related entity id")
    icon: Optional[str] = Field(None, description="Icon hint for UI")

class Worklog(BaseModel):
    date: datetime = Field(..., description="Work date")
    hours: float = Field(..., ge=0, le=24, description="Hours worked on date")
    project: Optional[str] = Field(None, description="Project or category")
    notes: Optional[str] = Field(None, description="Notes for the work entry")

class Note(BaseModel):
    title: str = Field(..., description="Note title")
    content: str = Field(..., description="Markdown or plain text content")
    pinned: bool = Field(False, description="Pinned to top")
