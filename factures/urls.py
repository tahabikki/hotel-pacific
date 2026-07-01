"""URLs de l'app factures."""
from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('planning/', views.planning_reservations, name='planning_reservations'),
    path('settings/', views.user_settings, name='user_settings'),
    path('factures/', views.FactureListView.as_view(), name='facture_liste'),
    path('clients/', views.ClientListView.as_view(), name='clients_liste'),
    path('clients/nouveau/', views.client_create, name='client_create'),
    path('clients/<int:pk>/modifier/', views.client_update, name='client_update'),
    path('clients/<int:pk>/supprimer/', views.client_delete, name='client_delete'),
    path('facture/nouvelle/', views.facture_create, name='facture_create'),
    path('facture/<int:pk>/', views.facture_detail, name='facture_detail'),
    path('facture/<int:pk>/modifier/', views.facture_update, name='facture_update'),
    path('facture/<int:pk>/supprimer/', views.facture_delete, name='facture_delete'),
    path('facture/<int:pk>/pdf/', views.facture_pdf, name='facture_pdf'),

    path('bilan/', views.bilan, name='bilan'),
    path('export/csv/', views.export_csv, name='export_csv'),
    path('export/pdf/', views.export_pdf, name='export_pdf'),
]
