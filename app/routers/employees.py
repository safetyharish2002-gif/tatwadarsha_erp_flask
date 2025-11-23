from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

@router.get("/employees", response_class=HTMLResponse)
def employees(request: Request):
    employee_data = [
        {"name": "Dr. Neha Sharma", "role": "Principal"},
        {"name": "Mr. Ramesh", "role": "Clerk"},
        {"name": "Ms. Sneha", "role": "Tutor"},
    ]
    return templates.TemplateResponse("employees.html", {
        "request": request,
        "title": "Employees",
        "employees": employee_data
    })
