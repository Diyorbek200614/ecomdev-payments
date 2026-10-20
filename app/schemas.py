"""Request and response models. Money is whole sums (so'm), never floats."""
import datetime as dt
import re

from pydantic import BaseModel, Field, field_validator

PHONE_RE = re.compile(r"^\+?[0-9]{7,15}$")


def clean_phone(value: str) -> str:
    compact = re.sub(r"[\s\-()]", "", value)
    if not PHONE_RE.match(compact):
        raise ValueError("phone must be 7-15 digits, optionally starting with +")
    return compact


def not_blank(value: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError("must not be blank")
    return value


class StudentIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    phone: str
    group: str = Field(min_length=1, max_length=50)
    monthly_fee: int = Field(gt=0, description="Monthly fee in so'm")

    @field_validator("name", "group")
    @classmethod
    def _text(cls, v: str) -> str:
        return not_blank(v)

    @field_validator("phone")
    @classmethod
    def _phone(cls, v: str) -> str:
        return clean_phone(v)


class StudentPatch(BaseModel):
    """Partial update: only the fields sent are changed."""
    name: str | None = Field(default=None, min_length=1, max_length=100)
    phone: str | None = None
    group: str | None = Field(default=None, min_length=1, max_length=50)
    monthly_fee: int | None = Field(default=None, gt=0)

    @field_validator("name", "group")
    @classmethod
    def _text(cls, v: str | None) -> str | None:
        return None if v is None else not_blank(v)

    @field_validator("phone")
    @classmethod
    def _phone(cls, v: str | None) -> str | None:
        return None if v is None else clean_phone(v)


class Student(BaseModel):
    id: int
    name: str
    phone: str
    group: str
    monthly_fee: int


class PaymentIn(BaseModel):
    student_id: int
    amount: int = Field(gt=0, description="Amount in so'm")
    date: dt.date | None = Field(default=None, description="Defaults to today")


class Payment(BaseModel):
    id: int
    student_id: int
    amount: int
    date: dt.date


class Debtor(BaseModel):
    student_id: int
    name: str
    phone: str
    group: str
    monthly_fee: int
    paid: int
    debt: int


class DebtorsReport(BaseModel):
    month: str
    total_debt: int
    debtors: list[Debtor]
