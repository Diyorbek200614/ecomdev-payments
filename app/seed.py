"""Demo data: `python -m app.seed` fills an empty database with a few students and payments."""
import datetime as dt

from .db import connect, init_db
from .main import today

STUDENTS = [
    ("Aziz Karimov", "+998901234567", "Python-1", 800_000),
    ("Malika Yusupova", "+998935551122", "Python-1", 800_000),
    ("Sardor Rahimov", "+998977778899", "English-B2", 600_000),
    ("Dilnoza Tosheva", "+998912223344", "English-B2", 600_000),
    ("Jasur Aliyev", "+998998887766", "Design", 1_000_000),
]


def main() -> None:
    init_db()
    with connect() as conn:
        if conn.execute("SELECT COUNT(*) FROM students").fetchone()[0]:
            print("Database already has students, nothing to do.")
            return
        ids = [
            conn.execute(
                "INSERT INTO students (name, phone, group_name, monthly_fee) VALUES (?, ?, ?, ?)", s
            ).lastrowid
            for s in STUDENTS
        ]
        first = today().replace(day=1)
        last_month = first - dt.timedelta(days=1)
        payments = [
            (ids[0], 800_000, first),        # paid in full
            (ids[1], 300_000, first),        # owes 500 000
            (ids[2], 600_000, last_month),   # paid last month only: owes all of this one
            (ids[3], 400_000, first),
            (ids[3], 200_000, first),        # two payments that add up to the fee
            # Jasur paid nothing
        ]
        conn.executemany(
            "INSERT INTO payments (student_id, amount, paid_on) VALUES (?, ?, ?)",
            [(sid, amount, day.isoformat()) for sid, amount, day in payments],
        )
    print(f"Added {len(STUDENTS)} students and {len(payments)} payments.")


if __name__ == "__main__":
    main()
