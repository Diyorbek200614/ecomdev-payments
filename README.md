# Мини-учёт оплат учебного центра

Django + Django REST Framework, SQLite, одна страница на HTML/CSS/JavaScript.

## Требования

- Python 3.12 или новее (проверено на 3.14);
- pip, git. Больше ничего: база — файл SQLite.

## Установка и запуск с нуля

Linux / macOS:

```bash
git clone <ссылка на репозиторий> ecomdev-payments
cd ecomdev-payments
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python manage.py makemigrations       # миграции уже в репозитории: ответит «No changes detected»
python manage.py migrate              # создаёт db.sqlite3
python manage.py createsuperuser      # администратор для /admin/ (необязательно)
python manage.py runserver
```

Windows (PowerShell) — те же команды, кроме двух: `python -m venv .venv` и `.venv\Scripts\Activate.ps1`.

Тесты:

```bash
python manage.py test
```

### Настройки

| Переменная | По умолчанию | Зачем |
|---|---|---|
| `DJANGO_SECRET_KEY` | создаётся в файле `.secret_key` при первом запуске | секретный ключ |
| `DJANGO_DEBUG` | `1` | `0` — выключить режим отладки |
| `DJANGO_ALLOWED_HOSTS` | `localhost,127.0.0.1` | хосты через запятую |

Секретный ключ, `.secret_key` и `db.sqlite3` в git не попадают (`.gitignore`).

## Адреса

- http://127.0.0.1:8000/ — веб-интерфейс: должники за месяц и форма оплаты;
- http://127.0.0.1:8000/api/ — API (в браузере открывается DRF-интерфейс);
- http://127.0.0.1:8000/admin/ — админка (ученики и оплаты).

## API

Суммы — десятичные строки с двумя знаками (`"1000000.00"`), даты — `YYYY-MM-DD`.

| Метод | Путь | Что делает |
|---|---|---|
| `GET` | `/api/students/` | список учеников |
| `POST` | `/api/students/` | создать: `name`, `phone`, `group`, `monthly_fee` |
| `GET` | `/api/students/{id}/` | один ученик |
| `PUT` / `PATCH` | `/api/students/{id}/` | изменить все поля / часть полей |
| `DELETE` | `/api/students/{id}/` | удалить; если есть оплаты — `409` и сообщение, ничего не удаляется |
| `POST` | `/api/payments/` | добавить оплату: `student`, `amount`, `date` (необязательно, по умолчанию сегодня) |
| `GET` | `/api/students/{id}/payments/` | оплаты ученика, новые сверху |
| `GET` | `/api/debtors/?month=YYYY-MM` | должники за месяц; без `month` — текущий месяц |

Правила должников: берутся только оплаты с датой в выбранном месяце, оплаты ученика за месяц
складываются, `debt = max(monthly_fee − paid, 0)`, ученики с нулевым долгом в список не попадают.
Сортировка — по долгу, большие сверху. «Сегодня» и «текущий месяц» — по Ташкенту (`TIME_ZONE`).

Ошибки: неверная сумма (`0`, отрицательная, не число), несуществующий ученик, неверный месяц,
неверный телефон — `400` с полем и текстом ошибки по-русски.

### Примеры

```bash
curl -X POST http://127.0.0.1:8000/api/students/ -H "Content-Type: application/json" \
  -d '{"name": "Ali", "phone": "+998 90 123-45-67", "group": "Python-1", "monthly_fee": "1000000"}'

curl -X POST http://127.0.0.1:8000/api/payments/ -H "Content-Type: application/json" \
  -d '{"student": 1, "amount": "600000", "date": "2026-10-05"}'

curl http://127.0.0.1:8000/api/students/1/payments/

curl "http://127.0.0.1:8000/api/debtors/?month=2026-10"
```

Ответ последнего запроса:

```json
[
  {"student_id": 1, "name": "Ali", "monthly_fee": "1000000.00", "paid": "600000.00", "debt": "400000.00"}
]
```

## Структура

```
config/                     настройки и корневые URL
payments/models.py          Student, Payment
payments/serializers.py     сериализаторы и проверки
payments/views.py           API и расчёт должников
payments/urls.py            маршруты /api/
payments/templates/payments/index.html   веб-страница
payments/tests.py           тесты
```

## Что можно улучшить за ещё одну неделю

1. **История тарифов и дата зачисления.** Сейчас к любому месяцу применяется текущая
   `monthly_fee`, а ученик, пришедший позже, считается должником и за прошлые месяцы.
   Нужны таблица тарифов с датой начала и поля «зачислен» / «отчислен».
2. **Баланс вместо помесячного среза.** Переплата не переносится на следующий месяц,
   долг прошлых месяцев не накапливается. Отчёт «общий долг на дату» решил бы это.
3. **Доступ и журнал.** API открыт без входа. Добавить авторизацию (токены или сессии
   с CSRF), роли, отмену оплаты с причиной и автором вместо правок задним числом.
4. **Удобство интерфейса.** Выбор даты оплаты, поиск ученика, список его оплат и
   выгрузка должников в Excel; пагинация в API.
5. **Эксплуатация.** PostgreSQL вместо SQLite, настройки для продакшена
   (`DEBUG=0`, gunicorn, статика), CI с тестами.
