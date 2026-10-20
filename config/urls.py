from django.contrib import admin
from django.urls import include, path

from payments.views import IndexView

urlpatterns = [
    path('', IndexView.as_view(), name='index'),
    path('api/', include('payments.urls')),
    path('admin/', admin.site.urls),
]
