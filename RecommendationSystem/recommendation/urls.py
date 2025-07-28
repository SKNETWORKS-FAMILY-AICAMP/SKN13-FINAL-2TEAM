from django.urls import path
from . import views

urlpatterns = [
    path('', views.recommendation_home, name='recommendation_home'),
]