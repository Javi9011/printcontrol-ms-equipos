from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import EquipoViewSet, TonerViewSet, LecturaContadorViewSet

router = DefaultRouter()
router.register(r'equipos', EquipoViewSet, basename='equipo')
router.register(r'toners', TonerViewSet, basename='toner')
router.register(r'lecturas', LecturaContadorViewSet, basename='lectura')

urlpatterns = [
    path('', include(router.urls)),
]
