"""URL routing principal."""
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path, reverse_lazy
from django.views.generic import RedirectView


urlpatterns = [
    path('', RedirectView.as_view(url='/admin/', permanent=False), name='root_redirect'),
    path(
        'admin/login/',
        auth_views.LoginView.as_view(
            template_name='admin/login.html',
            redirect_authenticated_user=True,
            next_page=reverse_lazy('dashboard'),
        ),
        name='login',
    ),
    path(
        'admin/logout/',
        auth_views.LogoutView.as_view(next_page=reverse_lazy('login')),
        name='admin_logout',
    ),
    path('admin/', include('factures.urls')),
    path('django-admin/', admin.site.urls),
]
