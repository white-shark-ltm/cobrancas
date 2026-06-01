from django.urls import path

from . import views

app_name = 'billing'

urlpatterns = [
    path('', views.InvoiceListView.as_view(), name='list'),
    path('nova/', views.InvoiceCreateView.as_view(), name='create'),
    path('<int:pk>/', views.InvoiceDetailView.as_view(), name='detail'),
    path('<int:pk>/editar/', views.InvoiceUpdateView.as_view(), name='update'),
    path('<int:pk>/imprimir/', views.InvoicePrintView.as_view(), name='print'),
    path('<int:pk>/status/', views.InvoiceStatusView.as_view(), name='status'),
    path('<int:invoice_pk>/pagamento/', views.PaymentCreateView.as_view(), name='payment'),
]
