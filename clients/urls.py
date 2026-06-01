"""URLs do módulo de clientes."""

from django.urls import path

from clients.views import (
    ClientCreateView,
    ClientDeactivateView,
    ClientDetailView,
    ClientListView,
    ClientUpdateView,
)

app_name = 'clients'

urlpatterns = [
    path('',                    ClientListView.as_view(),      name='list'),
    path('novo/',               ClientCreateView.as_view(),    name='create'),
    path('<int:pk>/',           ClientDetailView.as_view(),    name='detail'),
    path('<int:pk>/editar/',    ClientUpdateView.as_view(),    name='update'),
    path('<int:pk>/desativar/', ClientDeactivateView.as_view(), name='deactivate'),
]
