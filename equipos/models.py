from django.db import models
from django.core.validators import MinValueValidator


class TipoEquipo(models.TextChoices):
    MONOCROMATICO = 'MONO', 'Monocromático'
    COLOR = 'COLOR', 'Color'


class EstadoEquipo(models.TextChoices):
    ACTIVO = 'ACTIVO', 'Activo'
    INACTIVO = 'INACTIVO', 'Inactivo'
    MANTENIMIENTO = 'MANTENIMIENTO', 'En mantenimiento'


class Equipo(models.Model):
    """
    Representa una impresora/multifuncional en arrendamiento.
    """
    nombre = models.CharField(max_length=200, help_text='Modelo del equipo')
    marca = models.CharField(max_length=100)
    modelo = models.CharField(max_length=100)
    numero_serie = models.CharField(max_length=100, unique=True)
    tipo = models.CharField(max_length=10, choices=TipoEquipo.choices, default=TipoEquipo.MONOCROMATICO)
    estado = models.CharField(max_length=20, choices=EstadoEquipo.choices, default=EstadoEquipo.ACTIVO)

    # Datos del arrendamiento (referencia al ms-clientes, sin FK real entre servicios)
    cliente_id = models.PositiveIntegerField(null=True, blank=True, help_text='ID del cliente en ms-clientes')
    contrato_id = models.PositiveIntegerField(null=True, blank=True, help_text='ID del contrato en ms-contratos')
    ubicacion = models.CharField(max_length=200, blank=True)

    # Cuota mensual pactada en ciclos de motor
    cuota_mensual = models.PositiveIntegerField(
        default=5000,
        validators=[MinValueValidator(1)],
        help_text='Ciclos de motor incluidos en el contrato por mes'
    )

    # Contador inicial al momento de instalación
    contador_inicial = models.PositiveIntegerField(default=0)

    fecha_instalacion = models.DateField(null=True, blank=True)
    notas = models.TextField(blank=True)

    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['nombre']
        verbose_name = 'Equipo'
        verbose_name_plural = 'Equipos'

    def __str__(self):
        return f'{self.nombre} — {self.numero_serie}'

    @property
    def ultima_lectura(self):
        return self.lecturas.order_by('-fecha').first()

    @property
    def ciclos_ultimo_mes(self):
        lecturas = self.lecturas.order_by('-fecha')[:2]
        if len(lecturas) < 2:
            return None
        return lecturas[0].contador - lecturas[1].contador


class TonerCanal(models.TextChoices):
    NEGRO = 'K', 'Negro'
    CIAN = 'C', 'Cian'
    MAGENTA = 'M', 'Magenta'
    AMARILLO = 'Y', 'Amarillo'


class Toner(models.Model):
    """
    Tóner asociado a un equipo. Un equipo mono tiene solo K;
    un equipo color tiene K, C, M, Y.
    """
    equipo = models.ForeignKey(Equipo, on_delete=models.CASCADE, related_name='toners')
    canal = models.CharField(max_length=1, choices=TonerCanal.choices)

    capacidad_paginas = models.PositiveIntegerField(
        validators=[MinValueValidator(1)],
        help_text='Páginas totales que rinde el tóner nuevo'
    )
    paginas_restantes = models.PositiveIntegerField(
        help_text='Páginas estimadas restantes en el tóner actual'
    )
    # Porcentaje de alerta configurable por tóner (default 15%)
    umbral_alerta_pct = models.PositiveSmallIntegerField(
        default=15,
        validators=[MinValueValidator(1)],
        help_text='% restante al que se genera alerta'
    )

    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('equipo', 'canal')
        ordering = ['canal']
        verbose_name = 'Tóner'
        verbose_name_plural = 'Tóneres'

    def __str__(self):
        return f'{self.equipo} — Tóner {self.get_canal_display()}'

    @property
    def porcentaje_restante(self):
        if self.capacidad_paginas == 0:
            return 0
        return round((self.paginas_restantes / self.capacidad_paginas) * 100, 1)

    @property
    def requiere_cambio(self):
        return self.porcentaje_restante <= self.umbral_alerta_pct

    @property
    def nivel(self):
        pct = self.porcentaje_restante
        if pct <= 5:
            return 'CRITICO'
        if pct <= self.umbral_alerta_pct:
            return 'BAJO'
        return 'OK'


class LecturaContador(models.Model):
    """
    Lectura mensual del contador de ciclos de motor.
    Se registra una vez al mes por equipo.
    """
    equipo = models.ForeignKey(Equipo, on_delete=models.CASCADE, related_name='lecturas')
    fecha = models.DateField()
    contador = models.PositiveIntegerField(
        validators=[MinValueValidator(0)],
        help_text='Valor del contador en ciclos de motor al momento de la lectura'
    )
    notas = models.TextField(blank=True)
    registrado_por = models.CharField(max_length=150, blank=True)

    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-fecha']
        verbose_name = 'Lectura de Contador'
        verbose_name_plural = 'Lecturas de Contador'
        # Evitar duplicar lecturas del mismo mes para el mismo equipo
        constraints = [
            models.UniqueConstraint(
                fields=['equipo', 'fecha'],
                name='unique_lectura_equipo_fecha'
            )
        ]

    def __str__(self):
        return f'{self.equipo} — {self.fecha}: {self.contador:,}'

    @property
    def ciclos_desde_anterior(self):
        anterior = (
            LecturaContador.objects
            .filter(equipo=self.equipo, fecha__lt=self.fecha)
            .order_by('-fecha')
            .first()
        )
        if anterior is None:
            return None
        return self.contador - anterior.contador

    @property
    def excede_cuota(self):
        delta = self.ciclos_desde_anterior
        if delta is None:
            return False
        return delta > self.equipo.cuota_mensual


class CambioToner(models.Model):
    """
    Historial de cambios de tóner realizados en un equipo.
    """
    toner = models.ForeignKey(Toner, on_delete=models.CASCADE, related_name='cambios')
    fecha = models.DateField()
    paginas_al_cambio = models.PositiveIntegerField(
        help_text='Páginas restantes cuando se hizo el cambio (para estadísticas)'
    )
    notas = models.TextField(blank=True)
    realizado_por = models.CharField(max_length=150, blank=True)

    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-fecha']
        verbose_name = 'Cambio de Tóner'
        verbose_name_plural = 'Cambios de Tóner'

    def __str__(self):
        return f'{self.toner} — {self.fecha}'
