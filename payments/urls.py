from django.urls import path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register('students', views.StudentViewSet)

urlpatterns = [
    path('payments/', views.PaymentCreateView.as_view(), name='payment-create'),
    path('debtors/', views.DebtorsView.as_view(), name='debtors'),
    *router.urls,
]
