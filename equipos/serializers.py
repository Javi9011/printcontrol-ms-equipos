from rest_framework import serializers
from .models import Equipo, Toner, LecturaContador, CambioToner, TonerCanal, TipoEquipo


class TonerSerializer(serializers.ModelSerializer):
    porcentaje_restante = serializers.ReadOnlyField()
    requiere_cambio = serializers.ReadOnlyField()
    nivel = serializers.ReadOnlyField()
    canal_display = serializers.CharField(source='get_canal_display', read_only=True)

    class Meta:
        model = Toner
        fields = [
            'id','equipo','canal', 'canal_display',
            'capacidad_paginas', 'paginas_restantes',
            'umbral_alerta_pct',
            'porcentaje_restante', 'requiere_cambio', 'nivel',
            'actualizado_en',
        ]
        read_only_fields = ['id', 'actualizado_en']

class CambioTonerSerializer(serializers.ModelSerializer):
    class Meta:
        model = CambioToner
        fields = ['id', 'toner', 'fecha', 'paginas_al_cambio', 'notas', 'realizado_por', 'creado_en']
        read_only_fields = ['creado_en']



class LecturaContadorSerializer(serializers.ModelSerializer):
    ciclos_desde_anterior = serializers.ReadOnlyField()
    excede_cuota = serializers.ReadOnlyField()
    ciclos_k_desde_anterior = serializers.SerializerMethodField()
    ciclos_c_desde_anterior = serializers.SerializerMethodField()
    ciclos_m_desde_anterior = serializers.SerializerMethodField()
    ciclos_y_desde_anterior = serializers.SerializerMethodField()

    class Meta:
        model = LecturaContador
        fields = [
            'id', 'equipo', 'fecha', 'contador',
            'contador_k', 'contador_c', 'contador_m', 'contador_y',
            'ciclos_desde_anterior', 'excede_cuota',
            'ciclos_k_desde_anterior',
            'ciclos_c_desde_anterior',
            'ciclos_m_desde_anterior',
            'ciclos_y_desde_anterior',
            'notas', 'registrado_por', 'creado_en',
        ]
        read_only_fields = ['creado_en']

    def _calcular_ciclos_color(self, obj, campo):
        anterior = (
            LecturaContador.objects
            .filter(equipo=obj.equipo, fecha__lt=obj.fecha)
            .order_by('-fecha')
            .first()
        )

        if not anterior:
            return None

        actual = getattr(obj, campo)
        previo = getattr(anterior, campo)

        if actual is None or previo is None:
            return None

        return actual - previo


    def get_ciclos_k_desde_anterior(self, obj):
        return self._calcular_ciclos_color(obj, 'contador_k')


    def get_ciclos_c_desde_anterior(self, obj):
        return self._calcular_ciclos_color(obj, 'contador_c')


    def get_ciclos_m_desde_anterior(self, obj):
        return self._calcular_ciclos_color(obj, 'contador_m')


    def get_ciclos_y_desde_anterior(self, obj):
        return self._calcular_ciclos_color(obj, 'contador_y')

    def validate(self, data):
        equipo = data.get(
            'equipo',
            self.instance.equipo if self.instance else None
        )
        fecha = data.get(
            'fecha',
            self.instance.fecha if self.instance else None
        )
        contador = data.get(
            'contador',
            self.instance.contador if self.instance else None
        )

        if not equipo or not fecha or contador is None:
            return data

        # Evitar dos lecturas del mismo equipo en el mismo mes
        lecturas_mes = LecturaContador.objects.filter(
            equipo=equipo,
            fecha__year=fecha.year,
            fecha__month=fecha.month
        )

        if self.instance:
            lecturas_mes = lecturas_mes.exclude(pk=self.instance.pk)

        if lecturas_mes.exists():
            raise serializers.ValidationError({
                'fecha': 'Ya existe una lectura para este equipo en ese mes.'
            })

        # Buscar la lectura inmediatamente anterior
        anterior = (
            LecturaContador.objects
            .filter(equipo=equipo, fecha__lt=fecha)
            .exclude(pk=self.instance.pk if self.instance else None)
            .order_by('-fecha')
            .first()
        )

        # Si es la primera lectura, utilizar el contador inicial
        contador_anterior = (
            anterior.contador if anterior else equipo.contador_inicial
        )

        if contador < contador_anterior:
            raise serializers.ValidationError({
                'contador': (
                    f'El contador no puede ser menor al valor anterior '
                    f'({contador_anterior:,}).'
                )
            })

        # Comprobar que no supere una lectura posterior existente
        siguiente = (
            LecturaContador.objects
            .filter(equipo=equipo, fecha__gt=fecha)
            .exclude(pk=self.instance.pk if self.instance else None)
            .order_by('fecha')
            .first()
        )

        if siguiente and contador > siguiente.contador:
            raise serializers.ValidationError({
                'contador': (
                    f'El contador no puede superar la siguiente lectura '
                    f'({siguiente.contador:,}).'
                )
            })

        return data



class EquipoListSerializer(serializers.ModelSerializer):
    """Serializer ligero para listados."""
    toners = TonerSerializer(many=True, read_only=True)
    ultima_lectura = LecturaContadorSerializer(read_only=True)
    ciclos_ultimo_mes = serializers.ReadOnlyField()
    estado_display = serializers.CharField(source='get_estado_display', read_only=True)
    tipo_display = serializers.CharField(source='get_tipo_display', read_only=True)
    alertas_toner = serializers.SerializerMethodField()

    class Meta:
        model = Equipo
        fields = [
            'id', 'nombre', 'marca', 'modelo', 'numero_serie',
            'tipo', 'tipo_display', 'estado', 'estado_display',
            'cliente_id', 'contrato_id', 'ubicacion',
            'cuota_mensual', 'contador_inicial', 'fecha_instalacion',
            'toners', 'ultima_lectura', 'ciclos_ultimo_mes',
            'alertas_toner', 'creado_en', 'actualizado_en',
        ]

    def get_alertas_toner(self, obj):
        return [
            {
                'canal': t.canal,
                'canal_display': t.get_canal_display(),
                'nivel': t.nivel,
                'porcentaje_restante': t.porcentaje_restante,
            }
            for t in obj.toners.all()
            if t.requiere_cambio
        ]


class EquipoWriteSerializer(serializers.ModelSerializer):
    """Serializer para crear/actualizar equipos."""

    class Meta:
        model = Equipo
        fields = [
            'nombre', 'marca', 'modelo', 'numero_serie',
            'tipo', 'estado', 'cliente_id', 'contrato_id',
            'ubicacion', 'cuota_mensual', 'contador_inicial',
            'fecha_instalacion', 'notas',
        ]

    def validate_numero_serie(self, value):
        qs = Equipo.objects.filter(numero_serie=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError('Ya existe un equipo con este número de serie.')
        return value


class ActualizarTonerSerializer(serializers.Serializer):
    """Payload para actualizar páginas restantes de un tóner al registrar lectura."""
    canal = serializers.ChoiceField(choices=TonerCanal.choices)
    paginas_restantes = serializers.IntegerField(min_value=0)


class LecturaConToneresSerializer(serializers.Serializer):
    """
    Endpoint combinado: registra la lectura del contador y opcionalmente
    actualiza los niveles de tóner en una sola llamada.
    """
    fecha = serializers.DateField()
    contador = serializers.IntegerField(min_value=0)

    contador_k = serializers.IntegerField(
        min_value=0,
        required=True
    )
    contador_c = serializers.IntegerField(
        min_value=0,
        required=False,
        allow_null=True
    )
    contador_m = serializers.IntegerField(
        min_value=0,
        required=False,
        allow_null=True
    )
    contador_y = serializers.IntegerField(
        min_value=0,
        required=False,
        allow_null=True
    )

    notas = serializers.CharField(required=False, allow_blank=True, default='')
    registrado_por = serializers.CharField(required=False, allow_blank=True, default='')
    toners = ActualizarTonerSerializer(many=True, required=False, default=list)

    def validate(self, data):
        equipo = self.context.get('equipo')

        if not equipo:
            return data

        # Validar canales según el tipo de impresora
        if equipo.tipo == TipoEquipo.COLOR:
            for campo in ['contador_c', 'contador_m', 'contador_y']:
                if data.get(campo) is None:
                    raise serializers.ValidationError({
                        campo: 'Este contador es obligatorio para impresoras a color.'
                    })
        else:
            for campo in ['contador_c', 'contador_m', 'contador_y']:
                if data.get(campo) is not None:
                    raise serializers.ValidationError({
                        campo: 'Este contador no aplica para impresoras monocromáticas.'
                    })

        # Validar que ningún contador disminuya respecto a la lectura anterior
        anterior = equipo.lecturas.order_by('-fecha').first()

        if anterior:
            for campo in ['contador', 'contador_k', 'contador_c', 'contador_m', 'contador_y']:
                actual = data.get(campo)
                previo = getattr(anterior, campo)

                if actual is not None and previo is not None and actual < previo:
                    raise serializers.ValidationError({
                        campo: f'No puede ser menor al valor anterior ({previo:,}).'
                    })

        return data

class ResumenEquipoSerializer(serializers.Serializer):
    """Resumen agregado para el dashboard."""
    total_equipos = serializers.IntegerField()
    equipos_activos = serializers.IntegerField()
    alertas_toner = serializers.IntegerField()
    alertas_criticas = serializers.IntegerField()
    equipos_con_cuota_excedida = serializers.IntegerField()
