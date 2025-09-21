from django.urls import path
from . import views

urlpatterns = [
    path('', views.upload_view, name='upload'),
    path('hotel-form/', views.hotel_form_view, name='hotel_form'),
]


