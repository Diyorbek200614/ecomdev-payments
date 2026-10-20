from datetime import date
from unittest import mock

from rest_framework import status
from rest_framework.test import APITestCase

from .models import Payment, Student


class Base(APITestCase):
    def add_student(self, name='Ali', fee='1000000', group='Python-1', phone='+998 90 123-45-67'):
        r = self.client.post('/api/students/', {'name': name, 'phone': phone, 'group': group, 'monthly_fee': fee}, format='json')
        self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.data)
        return r.data

    def pay(self, student_id, amount, day=None):
        body = {'student': student_id, 'amount': amount}
        if day:
            body['date'] = day
        r = self.client.post('/api/payments/', body, format='json')
        self.assertEqual(r.status_code, status.HTTP_201_CREATED, r.data)
        return r.data

    def debtors(self, month=None):
        r = self.client.get('/api/debtors/', {'month': month} if month else {})
        self.assertEqual(r.status_code, status.HTTP_200_OK, r.data)
        return r.json()


class StudentTests(Base):
    def test_crud(self):
        s = self.add_student()
        self.assertEqual(s, {'id': s['id'], 'name': 'Ali', 'phone': '+998901234567', 'group': 'Python-1', 'monthly_fee': '1000000.00'})

        self.assertEqual(self.client.get('/api/students/').json(), [s])
        self.assertEqual(self.client.get(f"/api/students/{s['id']}/").json(), s)

        r = self.client.patch(f"/api/students/{s['id']}/", {'monthly_fee': '900000'}, format='json')
        self.assertEqual((r.status_code, r.data['monthly_fee'], r.data['name']), (200, '900000.00', 'Ali'))

        r = self.client.put(f"/api/students/{s['id']}/",
                            {'name': 'Vali', 'phone': '+998901112233', 'group': 'Python-2', 'monthly_fee': '700000'}, format='json')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json(), {'id': s['id'], 'name': 'Vali', 'phone': '+998901112233', 'group': 'Python-2', 'monthly_fee': '700000.00'})

        self.assertEqual(self.client.delete(f"/api/students/{s['id']}/").status_code, 204)
        self.assertEqual(self.client.get(f"/api/students/{s['id']}/").status_code, 404)

    def test_validation(self):
        bad = [
            {'name': '', 'phone': '+998901234567', 'group': 'G', 'monthly_fee': '100'},
            {'name': '   ', 'phone': '+998901234567', 'group': 'G', 'monthly_fee': '100'},
            {'name': 'A', 'phone': 'abc', 'group': 'G', 'monthly_fee': '100'},
            {'name': 'A', 'phone': '+998901234567', 'group': 'G', 'monthly_fee': '0'},
            {'name': 'A', 'phone': '+998901234567', 'monthly_fee': '100'},
        ]
        for body in bad:
            with self.subTest(body=body):
                self.assertEqual(self.client.post('/api/students/', body, format='json').status_code, 400)

    def test_cannot_delete_student_with_payments(self):
        s = self.add_student()
        self.pay(s['id'], '100000', '2026-09-01')
        r = self.client.delete(f"/api/students/{s['id']}/")
        self.assertEqual(r.status_code, status.HTTP_409_CONFLICT)
        self.assertIn('оплаты', r.data['detail'])
        self.assertTrue(Student.objects.filter(pk=s['id']).exists())
        self.assertEqual(Payment.objects.count(), 1)


class PaymentTests(Base):
    def test_add_and_list_by_student(self):
        a = self.add_student('A')
        b = self.add_student('B')
        p = self.pay(a['id'], '100000', '2026-09-05')
        self.assertEqual(p, {'id': p['id'], 'student': a['id'], 'amount': '100000.00', 'date': '2026-09-05'})
        self.pay(a['id'], '200000.50', '2026-09-20')
        self.pay(b['id'], '300000', '2026-09-10')

        items = self.client.get(f"/api/students/{a['id']}/payments/").json()
        self.assertEqual([(x['amount'], x['date']) for x in items], [('200000.50', '2026-09-20'), ('100000.00', '2026-09-05')])
        self.assertEqual(self.client.get('/api/students/999/payments/').status_code, 404)

    def test_date_defaults_to_today(self):
        s = self.add_student()
        with mock.patch('django.utils.timezone.localdate', return_value=date(2026, 10, 20)):
            p = self.pay(s['id'], '1000')
        self.assertEqual(p['date'], '2026-10-20')

    def test_invalid_amount(self):
        s = self.add_student()
        for amount in ['0', '-100', 'abc', '']:
            with self.subTest(amount=amount):
                r = self.client.post('/api/payments/', {'student': s['id'], 'amount': amount, 'date': '2026-09-01'}, format='json')
                self.assertEqual(r.status_code, 400)
                self.assertIn('amount', r.data)

    def test_student_must_exist(self):
        r = self.client.post('/api/payments/', {'student': 999, 'amount': '100', 'date': '2026-09-01'}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertIn('student', r.data)


class DebtorTests(Base):
    def test_sums_several_payments_in_month(self):
        s = self.add_student(fee='1000000')
        self.pay(s['id'], '200000', '2026-09-01')
        self.pay(s['id'], '400000', '2026-09-30')
        self.assertEqual(self.debtors('2026-09'), [
            {'student_id': s['id'], 'name': 'Ali', 'monthly_fee': '1000000.00', 'paid': '600000.00', 'debt': '400000.00'},
        ])

    def test_fully_paid_and_overpaid_are_excluded(self):
        full = self.add_student('Full', fee='800000')
        split = self.add_student('Split', fee='600000')
        over = self.add_student('Over', fee='500000')
        self.pay(full['id'], '800000', '2026-09-10')
        self.pay(split['id'], '400000', '2026-09-01')
        self.pay(split['id'], '200000', '2026-09-15')
        self.pay(over['id'], '700000', '2026-09-03')
        self.assertEqual(self.debtors('2026-09'), [])

    def test_payments_are_split_by_month(self):
        s = self.add_student(fee='600000')
        self.pay(s['id'], '600000', '2026-08-31')   # previous month
        self.pay(s['id'], '100000', '2026-09-01')   # first day counts
        self.pay(s['id'], '600000', '2026-10-01')   # next month
        [d] = self.debtors('2026-09')
        self.assertEqual((d['paid'], d['debt']), ('100000.00', '500000.00'))
        self.assertEqual(self.debtors('2026-08'), [])
        self.assertEqual(self.debtors('2026-10'), [])

    def test_december_and_unpaid_students(self):
        a = self.add_student('A', fee='100')
        b = self.add_student('B', fee='300')
        self.pay(a['id'], '100', '2025-12-31')
        self.pay(a['id'], '100', '2026-01-01')
        self.assertEqual([d['name'] for d in self.debtors('2025-12')], ['B'])
        self.assertEqual([(d['name'], d['debt']) for d in self.debtors('2026-02')], [('B', '300.00'), ('A', '100.00')])

    def test_default_month_is_current(self):
        s = self.add_student(fee='100')
        with mock.patch('django.utils.timezone.localdate', return_value=date(2026, 10, 20)):
            self.pay(s['id'], '100', '2026-10-05')
            self.assertEqual(self.debtors(), [])
            self.pay(s['id'], '1', '2026-09-05')
        self.assertEqual(len(self.debtors('2026-09')), 1)

    def test_invalid_month(self):
        for month in ['2026-13', '2026-00', '2026-1', '26-09', '2026/09', 'abc']:
            with self.subTest(month=month):
                r = self.client.get('/api/debtors/', {'month': month})
                self.assertEqual(r.status_code, 400)
                self.assertIn('month', r.data)


class PageTests(APITestCase):
    def test_index_page_opens(self):
        r = self.client.get('/')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Должники')
