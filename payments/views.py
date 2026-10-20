import re
from datetime import date
from decimal import Decimal

from django.db.models import DecimalField, Q, Sum, Value
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.generic import TemplateView
from rest_framework import generics, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import MONEY, Payment, Student
from .serializers import DebtorSerializer, PaymentSerializer, StudentSerializer

MONTH_RE = re.compile(r'^\d{4}-(0[1-9]|1[0-2])$')
CENT = Decimal('0.01')


class StudentViewSet(viewsets.ModelViewSet):
    """Students: list, create, retrieve, update (PUT/PATCH), delete."""
    queryset = Student.objects.all()
    serializer_class = StudentSerializer

    def destroy(self, request, *args, **kwargs):
        student = self.get_object()
        count = student.payments.count()
        if count:
            return Response(
                {'detail': f'Нельзя удалить ученика: у него есть оплаты ({count}). История платежей сохраняется.'},
                status=status.HTTP_409_CONFLICT,
            )
        student.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=['get'])
    def payments(self, request, pk=None):
        student = self.get_object()
        return Response(PaymentSerializer(student.payments.all(), many=True).data)


class PaymentCreateView(generics.CreateAPIView):
    queryset = Payment.objects.all()
    serializer_class = PaymentSerializer


def month_range(month: str) -> tuple[date, date]:
    """'2026-10' -> (2026-10-01, 2026-11-01): the month as a half-open range."""
    year, mon = map(int, month.split('-'))
    return date(year, mon, 1), date(year + mon // 12, mon % 12 + 1, 1)


class DebtorsView(APIView):
    """Students who paid less than their monthly fee in the month (?month=YYYY-MM, default current)."""

    def get(self, request):
        month = request.query_params.get('month') or timezone.localdate().strftime('%Y-%m')
        if not MONTH_RE.match(month):
            raise ValidationError({'month': 'Месяц должен быть в формате YYYY-MM, например 2026-10.'})
        start, end = month_range(month)
        students = Student.objects.annotate(
            paid=Coalesce(
                Sum('payments__amount', filter=Q(payments__date__gte=start, payments__date__lt=end)),
                Value(Decimal('0')),
                output_field=DecimalField(**MONEY),
            )
        )
        debtors = []
        for s in students:
            paid = Decimal(s.paid).quantize(CENT)
            debt = max(s.monthly_fee - paid, Decimal('0'))
            if debt > 0:
                debtors.append({
                    'student_id': s.id,
                    'name': s.name,
                    'monthly_fee': s.monthly_fee,
                    'paid': paid,
                    'debt': debt,
                })
        debtors.sort(key=lambda d: (-d['debt'], d['name']))
        return Response(DebtorSerializer(debtors, many=True).data)


class IndexView(TemplateView):
    template_name = 'payments/index.html'
