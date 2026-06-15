from django.contrib import admin
from django.utils.html import format_html
from .models import Equipo, Toner, LecturaContador, CambioToner


class TonerInline(admin.TabularInline):
    model = Toner
    extra = 0
    readonly_fields = ['porcentaje_restante', 'nivel']

    def porcentaje_restante(self, obj):
        pct = obj.porcentaje_restante
        color = '#E24B4A' if pct <= 5 else '#EF9F27' if pct <= obj.umbral_alerta_pct else '#639922'
        return format_html(
            '<span style="color:{};font-weight:bold">{}%</span>', color, pct
        )

    def nivel(self, obj):
        return obj.nivel


class LecturaInline(admin.TabularInline):
    model = LecturaContador
    extra = 0
    readonly_fields = ['ciclos_desde_anterior', 'excede_cuota']
    fields = ['fecha', 'contador', 'ciclos_desde_anterior', 'excede_cuota', 'notas', 'registrado_por']

    def ciclos_desde_anterior(self, obj):
        return obj.ciclos_desde_anterior

    def excede_cuota(self, obj):
        return '⚠️ Sí' if obj.excede_cuota else '✅ No'


@admin.register(Equipo)
class EquipoAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'numero_serie', 'tipo', 'estado', 'cliente_id', 'ubicacion', 'cuota_mensual', 'creado_en']
    list_filter = ['tipo', 'estado', 'marca']
    search_fields = ['nombre', 'numero_serie', 'marca', 'modelo']
    inlines = [TonerInline, LecturaInline]
    readonly_fields = ['creado_en', 'actualizado_en']


@admin.register(Toner)
class TonerAdmin(admin.ModelAdmin):
    list_display = ['equipo', 'canal', 'paginas_restantes', 'capacidad_paginas', 'porcentaje_display', 'nivel_display']
    list_filter = ['canal', 'equipo__tipo']
    search_fields = ['equipo__nombre', 'equipo__numero_serie']

    def porcentaje_display(self, obj):
        return f'{obj.porcentaje_restante}%'
    porcentaje_display.short_description = '% Restante'

    def nivel_display(self, obj):
        colors = {'OK': 'green', 'BAJO': 'orange', 'CRITICO': 'red'}
        return format_html(
            '<span style="color:{}">{}</span>',
            colors.get(obj.nivel, 'black'), obj.nivel
        )
    nivel_display.short_description = 'Nivel'


@admin.register(LecturaContador)
class LecturaContadorAdmin(admin.ModelAdmin):
    list_display = ['equipo', 'fecha', 'contador', 'ciclos_display', 'excede_display']
    list_filter = ['fecha', 'equipo']
    search_fields = ['equipo__nombre']

    def ciclos_display(self, obj):
        delta = obj.ciclos_desde_anterior
        return f'+{delta:,}' if delta else '—'
    ciclos_display.short_description = 'Ciclos mes'

    def excede_display(self, obj):
        return '⚠️' if obj.excede_cuota else '✅'
    excede_display.short_description = 'Cuota'


@admin.register(CambioToner)
class CambioTonerAdmin(admin.ModelAdmin):
    list_display = ['toner', 'fecha', 'paginas_al_cambio', 'realizado_por']
    list_filter = ['fecha']
