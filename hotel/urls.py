from django.urls import path
from django.views.generic import RedirectView
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_not_required

from .forms import LoginForm
from . import views

urlpatterns = [
    path('', RedirectView.as_view(pattern_name='tablero'), name='inicio'),
        path(
        'login/',
        login_not_required(
            auth_views.LoginView.as_view(
                template_name='hotel/login.html',
                authentication_form=LoginForm,
                redirect_authenticated_user=True,
            )
        ),
        name='login',
    ),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('tablero/', views.tablero, name='tablero'),

    # Habitaciones
    path('habitaciones/', views.HabitacionListView.as_view(), name='habitacion_lista'),
    path('habitaciones/nueva/', views.HabitacionCreateView.as_view(), name='habitacion_crear'),
    path('habitaciones/<int:pk>/editar/', views.HabitacionUpdateView.as_view(), name='habitacion_editar'),
    path('habitaciones/<int:pk>/eliminar/', views.HabitacionDeleteView.as_view(), name='habitacion_eliminar'),
    path('habitaciones/<int:pk>/disponible/', views.habitacion_disponible, name='habitacion_disponible'),

    # Huéspedes
    path('huespedes/', views.HuespedListView.as_view(), name='huesped_lista'),
    path('huespedes/nuevo/', views.HuespedCreateView.as_view(), name='huesped_crear'),
    path('huespedes/<int:pk>/editar/', views.HuespedUpdateView.as_view(), name='huesped_editar'),

    # Disponibilidad y reservas
    path('disponibilidad/', views.disponibilidad, name='disponibilidad'),
    path('reservas/', views.ReservaListView.as_view(), name='reserva_lista'),
    path('reservas/nueva/', views.ReservaCreateView.as_view(), name='reserva_crear'),
    path('reservas/<int:pk>/cancelar/', views.reserva_cancelar, name='reserva_cancelar'),
    path('reservas/<int:pk>/checkin/', views.reserva_checkin, name='reserva_checkin'),
    path('reservas/<int:pk>/checkout/', views.reserva_checkout, name='reserva_checkout'),
]