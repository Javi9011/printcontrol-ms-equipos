from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema, extend_schema_view

from .models import Equipo, Toner, LecturaContador, CambioToner, EstadoEquipo
from .serializers import (
    EquipoListSerializer,
    EquipoWriteSerializer,
    TonerSerializer,
    LecturaContadorSerializer,
    LecturaConToneresSerializer,
    CambioTonerSerializer,
    ResumenEquipoSerializer,
)


@extend_schema_view(
    list=extend_schema(summary='Listar equipos'),
    retrieve=extend_schema(summary='Detalle de un equipo'),
    create=extend_schema(summary='Crear equipo'),
    update=extend_schema(summary='Actualizar equipo'),
    partial_update=extend_schema(summary='Actualizar parcialmente'),
    destroy=extend_schema(summary='Eliminar equipo'),
)
class EquipoViewSet(viewsets.ModelViewSet):
    """
    CRUD completo de equipos de impresión.
    """
    queryset = Equipo.objects.prefetch_related('toners', 'lecturas').all()
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['tipo', 'estado', 'cliente_id', 'contrato_id']
    search_fields = ['nombre', 'marca', 'modelo', 'numero_serie', 'ubicacion']
    ordering_fields = ['nombre', 'creado_en', 'cuota_mensual']
    ordering = ['nombre']
    # En dev sin auth; en prod cambiar a IsAuthenticated
    permission_classes = [AllowAny]

    def get_serializer_class(self):
        if self.action in ('create', 'update', 'partial_update'):
            return EquipoWriteSerializer
        return EquipoListSerializer

    @extend_schema(
        summary='Resumen / dashboard',
        responses={200: ResumenEquipoSerializer},
    )
    @action(detail=False, methods=['get'], url_path='resumen')
    def resumen(self, request):
        """Métricas agregadas para el dashboard del frontend."""
        equipos = Equipo.objects.prefetch_related('toners', 'lecturas').all()

        alertas_toner = 0
        alertas_criticas = 0
        equipos_cuota = 0

        for eq in equipos:
            for t in eq.toners.all():
                if t.requiere_cambio:
                    alertas_toner += 1
                    if t.nivel == 'CRITICO':
                        alertas_criticas += 1
            delta = eq.ciclos_ultimo_mes
            if delta is not None and delta > eq.cuota_mensual:
                equipos_cuota += 1

        data = {
            'total_equipos': equipos.count(),
            'equipos_activos': equipos.filter(estado=EstadoEquipo.ACTIVO).count(),
            'alertas_toner': alertas_toner,
            'alertas_criticas': alertas_criticas,
            'equipos_con_cuota_excedida': equipos_cuota,
        }
        return Response(ResumenEquipoSerializer(data).data)

    @extend_schema(
        summary='Registrar lectura mensual + actualizar tóneres',
        request=LecturaConToneresSerializer,
        responses={201: LecturaContadorSerializer},
    )
    @action(detail=True, methods=['post'], url_path='lecturas')
    @transaction.atomic
    def registrar_lectura(self, request, pk=None):
        """
        Registra la lectura del contador de ciclos y opcionalmente
        actualiza los niveles de cada tóner. Todo en una sola petición.
        """
        equipo = self.get_object()
        serializer = LecturaConToneresSerializer(
            data=request.data,
            context={'equipo': equipo}
        )
        serializer.is_valid(raise_exception=True)
        vd = serializer.validated_data

        # Crear lectura
        lectura = LecturaContador.objects.create(
            equipo=equipo,
            fecha=vd['fecha'],
            contador=vd['contador'],
            notas=vd.get('notas', ''),
            registrado_por=vd.get('registrado_por', ''),
        )

        # Actualizar tóneres si vienen en el payload
        for toner_data in vd.get('toners', []):
            try:
                toner = equipo.toners.get(canal=toner_data['canal'])
                toner.paginas_restantes = toner_data['paginas_restantes']
                toner.save(update_fields=['paginas_restantes', 'actualizado_en'])
            except Toner.DoesNotExist:
                pass

        return Response(
            LecturaContadorSerializer(lectura).data,
            status=status.HTTP_201_CREATED
        )

    @extend_schema(summary='Historial de lecturas de un equipo')
    @action(detail=True, methods=['get'], url_path='historial-lecturas')
    def historial_lecturas(self, request, pk=None):
        equipo = self.get_object()
        lecturas = equipo.lecturas.order_by('-fecha')
        serializer = LecturaContadorSerializer(lecturas, many=True)
        return Response(serializer.data)

    @extend_schema(summary='Estado de tóneres de un equipo')
    @action(detail=True, methods=['get'], url_path='toners')
    def toners_equipo(self, request, pk=None):
        equipo = self.get_object()
        serializer = TonerSerializer(equipo.toners.all(), many=True)
        return Response(serializer.data)

    @extend_schema(summary='Alertas de tóner de todos los equipos')
    @action(detail=False, methods=['get'], url_path='alertas-toner')
    def alertas_toner(self, request):
        """Devuelve todos los tóneres que requieren cambio o están bajos."""
        toners_alerta = (
            Toner.objects
            .select_related('equipo')
            .all()
        )
        resultado = [
            {
                'equipo_id': t.equipo.id,
                'equipo_nombre': t.equipo.nombre,
                'equipo_serial': t.equipo.numero_serie,
                'cliente_id': t.equipo.cliente_id,
                'ubicacion': t.equipo.ubicacion,
                'canal': t.canal,
                'canal_display': t.get_canal_display(),
                'porcentaje_restante': t.porcentaje_restante,
                'nivel': t.nivel,
                'paginas_restantes': t.paginas_restantes,
                'capacidad_paginas': t.capacidad_paginas,
            }
            for t in toners_alerta
            if t.requiere_cambio
        ]
        return Response(resultado)


@extend_schema_view(
    list=extend_schema(summary='Listar tóneres'),
    retrieve=extend_schema(summary='Detalle de tóner'),
    create=extend_schema(summary='Crear tóner'),
    update=extend_schema(summary='Actualizar tóner'),
    partial_update=extend_schema(summary='Actualizar parcialmente'),
    destroy=extend_schema(summary='Eliminar tóner'),
)
class TonerViewSet(viewsets.ModelViewSet):
    queryset = Toner.objects.select_related('equipo').all()
    serializer_class = TonerSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['equipo', 'canal']
    permission_classes = [AllowAny]

    @extend_schema(
        summary='Registrar cambio de tóner (resetea a capacidad total)',
        request=CambioTonerSerializer,
        responses={200: TonerSerializer},
    )
    @action(detail=True, methods=['post'], url_path='cambiar')
    @transaction.atomic
    def cambiar_toner(self, request, pk=None):
        """
        Registra el cambio físico del tóner:
        - Guarda el historial de cambio
        - Resetea paginas_restantes a la capacidad total
        """
        toner = self.get_object()
        paginas_al_cambio = toner.paginas_restantes

        CambioToner.objects.create(
            toner=toner,
            fecha=request.data.get('fecha'),
            paginas_al_cambio=paginas_al_cambio,
            notas=request.data.get('notas', ''),
            realizado_por=request.data.get('realizado_por', ''),
        )

        toner.paginas_restantes = toner.capacidad_paginas
        toner.save(update_fields=['paginas_restantes', 'actualizado_en'])

        return Response(TonerSerializer(toner).data)

    @extend_schema(summary='Historial de cambios de un tóner')
    @action(detail=True, methods=['get'], url_path='historial')
    def historial_cambios(self, request, pk=None):
        toner = self.get_object()
        cambios = toner.cambios.order_by('-fecha')
        return Response(CambioTonerSerializer(cambios, many=True).data)


class LecturaContadorViewSet(viewsets.ModelViewSet):
    queryset = LecturaContador.objects.select_related('equipo').all()
    serializer_class = LecturaContadorSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['equipo', 'fecha']
    ordering_fields = ['fecha', 'contador']
    ordering = ['-fecha']
    permission_classes = [AllowAny]
