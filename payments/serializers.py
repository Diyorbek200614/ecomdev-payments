import re

from rest_framework import serializers

from .models import MONEY, Payment, Student

POSITIVE = 'Сумма должна быть больше нуля.'


class StudentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Student
        fields = ['id', 'name', 'phone', 'group', 'monthly_fee']
        extra_kwargs = {'monthly_fee': {'error_messages': {'min_value': POSITIVE}}}

    def to_internal_value(self, data):
        # Accept "+998 90 123-45-67": spaces, dashes and brackets are dropped before validation.
        if isinstance(data, dict) and isinstance(data.get('phone'), str):
            data = {**data, 'phone': re.sub(r'[\s\-()]', '', data['phone'])}
        return super().to_internal_value(data)


class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = ['id', 'student', 'amount', 'date']
        extra_kwargs = {
            'date': {'required': False},
            'amount': {'error_messages': {'min_value': POSITIVE}},
            'student': {'error_messages': {'does_not_exist': 'Ученик с id={pk_value} не найден.'}},
        }


class DebtorSerializer(serializers.Serializer):
    student_id = serializers.IntegerField()
    name = serializers.CharField()
    monthly_fee = serializers.DecimalField(**MONEY)
    paid = serializers.DecimalField(**MONEY)
    debt = serializers.DecimalField(**MONEY)
