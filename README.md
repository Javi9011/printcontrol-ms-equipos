# ms-equipos — PrintControl

Microservicio Django REST para gestión de equipos de impresión en arrendamiento.

## Stack
- Python 3.12 + Django 5 + Django REST Framework
- PostgreSQL 16
- Docker / docker-compose

## Endpoints principales

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/api/v1/equipos/` | Listar equipos |
| POST | `/api/v1/equipos/` | Crear equipo |
| GET | `/api/v1/equipos/{id}/` | Detalle de equipo |
| PUT/PATCH | `/api/v1/equipos/{id}/` | Actualizar equipo |
| DELETE | `/api/v1/equipos/{id}/` | Eliminar equipo |
| GET | `/api/v1/equipos/resumen/` | Métricas para dashboard |
| POST | `/api/v1/equipos/{id}/lecturas/` | Registrar lectura mensual + tóneres |
| GET | `/api/v1/equipos/{id}/historial-lecturas/` | Historial de lecturas |
| GET | `/api/v1/equipos/{id}/toners/` | Estado de tóneres |
| GET | `/api/v1/equipos/alertas-toner/` | Todos los tóneres bajos |
| POST | `/api/v1/toners/{id}/cambiar/` | Registrar cambio de tóner |
| GET | `/api/v1/toners/{id}/historial/` | Historial de cambios de tóner |
| GET/POST | `/api/v1/lecturas/` | Lecturas (CRUD directo) |
| GET | `/api/docs/` | Swagger UI |
| GET | `/api/redoc/` | ReDoc |

## Levantarlo con Docker (recomendado)

```bash
# 1. Clonar / entrar al directorio
cd ms-equipos

# 2. Crear el .env
cp .env.example .env

# 3. Levantar todo
docker-compose up --build

# 4. Crear superusuario (en otra terminal)
docker-compose exec ms-equipos python manage.py createsuperuser
```

Accede a:
- API: http://localhost:8001/api/v1/
- Swagger: http://localhost:8001/api/docs/
- Admin: http://localhost:8001/admin/

## Levantarlo sin Docker (venv local)

```bash
cd ms-equipos

python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

pip install -r requirements.txt

cp .env.example .env
# Edita .env con tus datos de PostgreSQL local

python manage.py migrate
python manage.py createsuperuser
python manage.py runserver 8001
```

## Ejemplo — Registrar lectura mensual con actualización de tóner

```bash
curl -X POST http://localhost:8001/api/v1/equipos/1/lecturas/ \
  -H "Content-Type: application/json" \
  -d '{
    "fecha": "2025-05-31",
    "contador": 22500,
    "notas": "Lectura de mayo",
    "registrado_por": "Técnico 1",
    "toners": [
      {"canal": "K", "paginas_restantes": 1200},
      {"canal": "C", "paginas_restantes": 400}
    ]
  }'
```

## Subir a GitHub

```bash
git init
git add .
git commit -m "feat: ms-equipos inicial"
git remote add origin https://github.com/TU_USUARIO/printcontrol-ms-equipos.git
git push -u origin main
```
