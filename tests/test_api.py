import datetime as dt

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test.sqlite3"))
    from app.main import app

    with TestClient(app) as c:
        yield c


def add_student(client, name="Aziz", fee=800_000, group="Python-1", phone="+998 90 123-45-67"):
    r = client.post("/students", json={"name": name, "phone": phone, "group": group, "monthly_fee": fee})
    assert r.status_code == 201, r.text
    return r.json()


def pay(client, student_id, amount, date):
    r = client.post("/payments", json={"student_id": student_id, "amount": amount, "date": date})
    assert r.status_code == 201, r.text
    return r.json()


# --- Students -------------------------------------------------------------

def test_student_crud(client):
    s = add_student(client)
    assert s == {"id": s["id"], "name": "Aziz", "phone": "+998901234567", "group": "Python-1", "monthly_fee": 800_000}

    assert client.get("/students").json() == [s]
    assert client.get(f"/students/{s['id']}").json() == s

    r = client.patch(f"/students/{s['id']}", json={"monthly_fee": 900_000})
    assert r.status_code == 200 and r.json()["monthly_fee"] == 900_000 and r.json()["name"] == "Aziz"

    r = client.put(f"/students/{s['id']}", json={"name": "Aziz K.", "phone": "+998901112233", "group": "Python-2", "monthly_fee": 700_000})
    assert r.json() == {"id": s["id"], "name": "Aziz K.", "phone": "+998901112233", "group": "Python-2", "monthly_fee": 700_000}

    assert client.delete(f"/students/{s['id']}").status_code == 204
    assert client.get(f"/students/{s['id']}").status_code == 404
    assert client.get("/students").json() == []


def test_students_filter_by_group(client):
    add_student(client, "A", group="G1")
    add_student(client, "B", group="G2")
    assert [s["name"] for s in client.get("/students", params={"group": "G2"}).json()] == ["B"]


@pytest.mark.parametrize("body", [
    {"name": "", "phone": "+998901234567", "group": "G", "monthly_fee": 100},
    {"name": "   ", "phone": "+998901234567", "group": "G", "monthly_fee": 100},
    {"name": "A", "phone": "abc", "group": "G", "monthly_fee": 100},
    {"name": "A", "phone": "+998901234567", "group": "G", "monthly_fee": 0},
    {"name": "A", "phone": "+998901234567", "group": "G", "monthly_fee": -5},
    {"name": "A", "phone": "+998901234567", "monthly_fee": 100},
])
def test_student_validation(client, body):
    assert client.post("/students", json=body).status_code == 422


def test_missing_student_is_404(client):
    assert client.get("/students/999").status_code == 404
    assert client.patch("/students/999", json={"name": "X"}).status_code == 404
    assert client.delete("/students/999").status_code == 404
    assert client.get("/students/999/payments").status_code == 404


# --- Payments -------------------------------------------------------------

def test_payments_list_by_student(client):
    a = add_student(client, "A")
    b = add_student(client, "B")
    pay(client, a["id"], 100_000, "2026-09-05")
    pay(client, a["id"], 200_000, "2026-09-20")
    pay(client, b["id"], 300_000, "2026-09-10")

    items = client.get(f"/students/{a['id']}/payments").json()
    assert [(p["amount"], p["date"]) for p in items] == [(200_000, "2026-09-20"), (100_000, "2026-09-05")]


def test_payment_date_defaults_to_today(client):
    from app.main import today

    s = add_student(client)
    r = client.post("/payments", json={"student_id": s["id"], "amount": 1000})
    assert r.status_code == 201 and r.json()["date"] == today().isoformat()


def test_payment_validation(client):
    s = add_student(client)
    future = (dt.date.today() + dt.timedelta(days=3)).isoformat()
    assert client.post("/payments", json={"student_id": 999, "amount": 100, "date": "2026-09-01"}).status_code == 404
    assert client.post("/payments", json={"student_id": s["id"], "amount": 0, "date": "2026-09-01"}).status_code == 422
    assert client.post("/payments", json={"student_id": s["id"], "amount": 100, "date": "2026-13-01"}).status_code == 422
    assert client.post("/payments", json={"student_id": s["id"], "amount": 100, "date": future}).status_code == 422


def test_deleting_student_deletes_payments(client):
    s = add_student(client)
    pay(client, s["id"], 100, "2026-09-01")
    client.delete(f"/students/{s['id']}")
    s2 = add_student(client, "Other")
    # The old payment must not leak into the debtors report.
    report = client.get("/debtors", params={"month": "2026-09"}).json()
    assert [(d["student_id"], d["paid"]) for d in report["debtors"]] == [(s2["id"], 0)]


# --- Debtors --------------------------------------------------------------

def test_debtors_for_month(client):
    full = add_student(client, "Full", fee=800_000)
    part = add_student(client, "Part", fee=800_000)
    none = add_student(client, "None", fee=600_000)
    split = add_student(client, "Split", fee=600_000)
    over = add_student(client, "Over", fee=500_000)

    pay(client, full["id"], 800_000, "2026-09-01")
    pay(client, part["id"], 300_000, "2026-09-15")
    pay(client, none["id"], 600_000, "2026-08-31")   # previous month, does not count
    pay(client, none["id"], 600_000, "2026-10-01")   # next month, does not count
    pay(client, split["id"], 400_000, "2026-09-01")
    pay(client, split["id"], 200_000, "2026-09-30")  # last day of the month counts
    pay(client, over["id"], 700_000, "2026-09-10")

    report = client.get("/debtors", params={"month": "2026-09"}).json()
    assert report["month"] == "2026-09"
    assert [(d["name"], d["paid"], d["debt"]) for d in report["debtors"]] == [
        ("None", 0, 600_000),        # largest debt first
        ("Part", 300_000, 500_000),
    ]
    assert report["total_debt"] == 1_100_000


def test_debtors_december_rolls_into_next_year(client):
    s = add_student(client, fee=100)
    pay(client, s["id"], 100, "2025-12-31")
    pay(client, s["id"], 100, "2026-01-01")
    assert client.get("/debtors", params={"month": "2025-12"}).json()["debtors"] == []
    assert client.get("/debtors", params={"month": "2026-01"}).json()["debtors"] == []
    assert len(client.get("/debtors", params={"month": "2026-02"}).json()["debtors"]) == 1


def test_fee_change_applies_to_report(client):
    s = add_student(client, fee=500_000)
    pay(client, s["id"], 500_000, "2026-09-03")
    client.patch(f"/students/{s['id']}", json={"monthly_fee": 600_000})
    [d] = client.get("/debtors", params={"month": "2026-09"}).json()["debtors"]
    assert d["debt"] == 100_000


def test_debtors_default_month_is_current(client):
    from app.main import today

    add_student(client)
    assert client.get("/debtors").json()["month"] == today().strftime("%Y-%m")


@pytest.mark.parametrize("month", ["2026-13", "2026-1", "26-09", "2026/09", "abc"])
def test_debtors_bad_month(client, month):
    assert client.get("/debtors", params={"month": month}).status_code == 422


def test_index_page(client):
    r = client.get("/")
    assert r.status_code == 200 and "Должники" in r.text
