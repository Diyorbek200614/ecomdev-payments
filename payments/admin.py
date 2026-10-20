from django.contrib import admin

from .models import Payment, Student


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'phone', 'group', 'monthly_fee']
    list_filter = ['group']
    search_fields = ['name', 'phone']


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ['id', 'student', 'amount', 'date']
    list_filter = ['date']
    autocomplete_fields = ['student']
