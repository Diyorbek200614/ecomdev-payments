from decimal import Decimal

from django.core.validators import MinValueValidator, RegexValidator
from django.db import models
from django.utils import timezone

MONEY = {'max_digits': 12, 'decimal_places': 2}
positive = MinValueValidator(Decimal('0.01'), 'Сумма должна быть больше нуля.')


def today():
    """Today in TIME_ZONE (Tashkent), the default payment date."""
    return timezone.localdate()


class Student(models.Model):
    name = models.CharField('имя', max_length=100)
    phone = models.CharField(
        'телефон',
        max_length=20,
        validators=[RegexValidator(r'^\+?\d{7,15}$', 'Телефон: от 7 до 15 цифр, можно с + в начале.')],
    )
    group = models.CharField('группа', max_length=50)
    monthly_fee = models.DecimalField('ежемесячная сумма', validators=[positive], **MONEY)

    class Meta:
        ordering = ['name', 'id']
        verbose_name = 'ученик'
        verbose_name_plural = 'ученики'

    def __str__(self):
        return f'{self.name} ({self.group})'


class Payment(models.Model):
    # PROTECT: a student with payments cannot be deleted, the payment history stays.
    student = models.ForeignKey(Student, on_delete=models.PROTECT, related_name='payments', verbose_name='ученик')
    amount = models.DecimalField('сумма', validators=[positive], **MONEY)
    date = models.DateField('дата', default=today)

    class Meta:
        ordering = ['-date', '-id']
        indexes = [models.Index(fields=['student', 'date'])]
        verbose_name = 'оплата'
        verbose_name_plural = 'оплаты'

    def __str__(self):
        return f'{self.student.name}: {self.amount} ({self.date})'
