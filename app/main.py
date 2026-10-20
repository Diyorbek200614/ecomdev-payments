"""Mini payment ledger for a training centre: students, payments, debtors."""
import datetime as dt
import re
import sqlite3
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Query, Response
from fastapi.responses import FileResponse

from .db import get_conn, init_db
from .schemas import (
    Debtor,
    DebtorsReport,
    Payment,
    PaymentIn,
    Student,
    StudentIn,
    StudentPatch,
)

# The centre works in Tashkent: "today" and "this month" are Tashkent's.
TZ = dt.timezone(dt.timedelta(hours=5))
MONTH_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")
STATIC = Path(__file__).resolve().parent / "static"


def today() -> dt.date:
    return dt.datetime.now(TZ).date()


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(title="Training centre payments", version="1.0.0", lifespan=lifespan)

Conn = sqlite3.Connection


def to_student(row: sqlite3.Row) -> Student:
    return Student(
        id=row["id"],
        name=row["name"],
        phone=row["phone"],
        group=row["group_name"],
        monthly_fee=row["monthly_fee"],
    )


def to_payment(row: sqlite3.Row) -> Payment:
    return Payment(id=row["id"], student_id=row["student_id"], amount=row["amount"], date=row["paid_on"])


def find_student(conn: Conn, student_id: int) -> sqlite3.Row:
    row = conn.execute("SELECT * FROM students WHERE id = ?", (student_id,)).fetchone()
    if row is None:
        raise HTTPException(404, "student not found")
    return row


def month_bounds(month: str) -> tuple[str, str]:
    """'2026-10' -> ('2026-10-01', '2026-11-01'), the half-open range of the month."""
    year, mon = map(int, month.split("-"))
    start = dt.date(year, mon, 1)
    end = dt.date(year + mon // 12, mon % 12 + 1, 1)
    return start.isoformat(), end.isoformat()


# --- Students -------------------------------------------------------------

@app.get("/students", response_model=list[Student], tags=["students"])
def list_students(group: str | None = None, conn: Conn = Depends(get_conn)):
    if group:
        rows = conn.execute("SELECT * FROM students WHERE group_name = ? ORDER BY name", (group,))
    else:
        rows = conn.execute("SELECT * FROM students ORDER BY name")
    return [to_student(r) for r in rows]


@app.post("/students", response_model=Student, status_code=201, tags=["students"])
def create_student(body: StudentIn, conn: Conn = Depends(get_conn)):
    cur = conn.execute(
        "INSERT INTO students (name, phone, group_name, monthly_fee) VALUES (?, ?, ?, ?)",
        (body.name, body.phone, body.group, body.monthly_fee),
    )
    return to_student(find_student(conn, cur.lastrowid))


@app.get("/students/{student_id}", response_model=Student, tags=["students"])
def get_student(student_id: int, conn: Conn = Depends(get_conn)):
    return to_student(find_student(conn, student_id))


@app.put("/students/{student_id}", response_model=Student, tags=["students"])
def replace_student(student_id: int, body: StudentIn, conn: Conn = Depends(get_conn)):
    find_student(conn, student_id)
    conn.execute(
        "UPDATE students SET name = ?, phone = ?, group_name = ?, monthly_fee = ? WHERE id = ?",
        (body.name, body.phone, body.group, body.monthly_fee, student_id),
    )
    return to_student(find_student(conn, student_id))


@app.patch("/students/{student_id}", response_model=Student, tags=["students"])
def update_student(student_id: int, body: StudentPatch, conn: Conn = Depends(get_conn)):
    find_student(conn, student_id)
    columns = {"name": "name", "phone": "phone", "group": "group_name", "monthly_fee": "monthly_fee"}
    changes = body.model_dump(exclude_unset=True, exclude_none=True)
    if changes:
        sets = ", ".join(f"{columns[k]} = ?" for k in changes)
        conn.execute(f"UPDATE students SET {sets} WHERE id = ?", (*changes.values(), student_id))
    return to_student(find_student(conn, student_id))


@app.delete("/students/{student_id}", status_code=204, tags=["students"])
def delete_student(student_id: int, conn: Conn = Depends(get_conn)):
    find_student(conn, student_id)
    # The student's payments go with them (ON DELETE CASCADE).
    conn.execute("DELETE FROM students WHERE id = ?", (student_id,))
    return Response(status_code=204)


# --- Payments -------------------------------------------------------------

@app.post("/payments", response_model=Payment, status_code=201, tags=["payments"])
def add_payment(body: PaymentIn, conn: Conn = Depends(get_conn)):
    find_student(conn, body.student_id)
    paid_on = body.date or today()
    if paid_on > today():
        raise HTTPException(422, "payment date cannot be in the future")
    cur = conn.execute(
        "INSERT INTO payments (student_id, amount, paid_on) VALUES (?, ?, ?)",
        (body.student_id, body.amount, paid_on.isoformat()),
    )
    row = conn.execute("SELECT * FROM payments WHERE id = ?", (cur.lastrowid,)).fetchone()
    return to_payment(row)


@app.get("/students/{student_id}/payments", response_model=list[Payment], tags=["payments"])
def list_payments(student_id: int, conn: Conn = Depends(get_conn)):
    find_student(conn, student_id)
    rows = conn.execute(
        "SELECT * FROM payments WHERE student_id = ? ORDER BY paid_on DESC, id DESC",
        (student_id,),
    )
    return [to_payment(r) for r in rows]


# --- Debtors --------------------------------------------------------------

@app.get("/debtors", response_model=DebtorsReport, tags=["debtors"])
def debtors(
    month: str | None = Query(default=None, description="YYYY-MM, the current month if omitted"),
    conn: Conn = Depends(get_conn),
):
    """Students who paid less than their monthly fee in the month, and how much they owe."""
    month = month or today().strftime("%Y-%m")
    if not MONTH_RE.match(month):
        raise HTTPException(422, "month must be YYYY-MM")
    start, end = month_bounds(month)
    rows = conn.execute(
        """
        SELECT s.id, s.name, s.phone, s.group_name, s.monthly_fee,
               COALESCE(SUM(p.amount), 0) AS paid
          FROM students s
          LEFT JOIN payments p
                 ON p.student_id = s.id AND p.paid_on >= ? AND p.paid_on < ?
         GROUP BY s.id
        HAVING paid < s.monthly_fee
         ORDER BY s.monthly_fee - paid DESC, s.name
        """,
        (start, end),
    ).fetchall()
    items = [
        Debtor(
            student_id=r["id"],
            name=r["name"],
            phone=r["phone"],
            group=r["group_name"],
            monthly_fee=r["monthly_fee"],
            paid=r["paid"],
            debt=r["monthly_fee"] - r["paid"],
        )
        for r in rows
    ]
    return DebtorsReport(month=month, total_debt=sum(d.debt for d in items), debtors=items)


# --- Web page -------------------------------------------------------------

@app.get("/", include_in_schema=False)
def index():
    return FileResponse(STATIC / "index.html")
