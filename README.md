# Traxia Analytics

> **Si buscas el System Design Document completo (arquitectura, DDL, RLS, roadmap),
> salta a la sección [System Design Document (SDD) v3.4 — FINAL](#system-design-document-sdd-v34--final)
> más abajo.**

## Estado del Proyecto — 2026-07-21

### Fases completadas

| Fase | Descripción | Estado |
|------|-------------|--------|
| **Fase 1** | Esquema PostgreSQL 17 + RLS 3 niveles + Edge Gateway + auth (access/refresh token) | ✅ Completa |
| **Fase 2** | Backoffice, Partners, dashboards de tráfico/dwell/comparativo | ✅ Completa |
| **Fase 3** | Motor de Acciones + Copiloto (Claude) + Hallazgos con snapshot firmado | ✅ Completa |

### Qué tiene interfaz visual y qué es solo API

| Módulo | Dashboard UI | API Cloud | Notas |
|--------|:---:|:---:|-------|
| Tráfico / Heatmap | ✅ | ✅ | |
| Dwell Time por zona | ✅ | ✅ | |
| Comparativo inter-sucursal | ✅ | ✅ | Tenant Admin únicamente |
| Zonas / Cámaras (dibujo de polígonos) | ✅ | ✅ | Tenant Admin únicamente |
| Backoffice de Usuarios | ✅ | ✅ | Tenant Admin únicamente |
| Partners (alta/baja/revocación) | ✅ | ✅ | Tenant Admin únicamente |
| Motor de Acciones (reglas + canales + log) | ✅ | ✅ | Tenant Admin únicamente, nunca Partner |
| Copiloto (chat con Claude Haiku 4.5) | ✅ | ✅ | Admin + Partner (datos acotados por RLS) |
| Hallazgos de auditoría (`agent_findings`) | ✅ | ✅ | Admin + Partner (RLS); snapshot como URL firmada R2 (5 min) |
| Exportar PDF/CSV | ✅ | ✅ | |
| Model Registry / Fleet Management | ❌ UI | ✅ API | Gestión interna vía SuperAdmin, sin UI todavía |
| Login SuperAdmin | ❌ | ✅ | Ver brecha conocida abajo |
| Reseller / Canal distribuidor | ❌ | ❌ activo | Diferido a v2.0 (tabla y RLS escritos, inertes) |

### Brechas conocidas documentadas en el SDD

1. **Login de SuperAdmin** (SDD §4, §8.5): el SuperAdmin no es un usuario de la tabla
   `users` — es acceso interno de la plataforma. No existe pantalla de login para el
   SuperAdmin en el dashboard React. En el MLP, las operaciones del SuperAdmin
   (crear tenants, asignar `vertical_type`, publicar modelos) se ejecutan directamente
   sobre la base de datos o vía endpoints internos. Una UI de SuperAdmin está diseñada
   pero no construida.

2. **Guardrail de salida del Copiloto** (SDD §12.4): la seguridad del Copiloto
   descansa en el aislamiento de datos (RLS filtra qué zonas se incluyen en el system
   prompt), no en un filtro server-side de la respuesta del modelo. La respuesta de
   Claude sale tal cual hacia el usuario — no existe un filtro de contenido de salida.
   Esto está documentado explícitamente en `tests/copilot/test_copilot_api.py` y es
   una decisión de diseño, no un olvido.

3. **Reseller / Canal** (SDD §3.1, decisión 2): la tabla `resellers`, su RLS y el
   Flujo 6 están completos y validados en el SDD, pero **inertes** en el MLP. Se
   activan sin rediseño cuando exista el primer acuerdo de canal real.

---

## Cómo levantar el proyecto localmente

### Pre-requisitos

- Python 3.11+
- Node.js 20+
- PostgreSQL 17 local (o Supabase CLI)
- Docker (para el Edge Gateway)

### 1. Base de datos

```bash
# Crea la base de datos y ejecuta el DDL + extensiones (ver SDD §8)
psql -U postgres -c "CREATE DATABASE traxia_dev;"
psql -U postgres -d traxia_dev -f db/schema.sql
# Las extensiones requeridas: pgcrypto, citext, pg_partman
```

### 2. API Cloud

```bash
cd cloud
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Variables de entorno requeridas (sin defaults en el código):
export DATABASE_URL="postgresql://traxia_app:password@localhost/traxia_dev"
export JWT_SECRET="your-secret-here"          # ValueError si no está seteado
export ANTHROPIC_API_KEY="sk-ant-..."         # Opcional; sin ella el Copiloto devuelve 503

uvicorn cloud.main:app --reload --port 8000
```

### 3. Dashboard

```bash
cd dashboard
npm install
cp .env.example .env.local                   # ajusta VITE_API_URL=http://localhost:8000
npm run dev                                   # http://localhost:5173
```

### 4. Edge Gateway (modo STUB para desarrollo)

```bash
cd edge
# Sin ultralytics instalado, el gateway corre en STUB mode (detecciones sintéticas)
pip install -r requirements.txt
python -m edge.gateway
```

Para validación real con YOLOv8n + ByteTrack (requiere ultralytics/PyTorch):
```bash
./validate_inference/run.sh --model /path/to/yolo_retail.pt
```

### 5. Tests

```bash
# API Cloud (no requiere DB real — fixtures de pytest)
cd cloud && pytest tests/ -v

# Edge Gateway (unit tests, sin ultralytics)
cd edge && pytest tests/ -v

# Dashboard E2E (Playwright, requiere `npm run dev` corriendo)
cd dashboard && npx playwright test
```

---

## Matriz de roles rápida

| Pantalla | Tenant Admin | Operator/Viewer | Partner |
|----------|:---:|:---:|:---:|
| Tráfico / Dwell / Heatmap | ✅ | ✅ (sus sedes) | ✅ (sus zonas) |
| Copiloto + Hallazgos | ✅ | ✅ | ✅ (acotado) |
| Exportar | ✅ | ✅ | ✅ |
| Zonas / Comparativo / Usuarios / Partners | ✅ | ❌ | ❌ |
| **Motor de Acciones** | ✅ | ❌ | **nunca** |

> El aislamiento de datos (qué ve cada rol) está garantizado por RLS en PostgreSQL,
> no solo por la UI. Ver SDD §8.3 para la implementación completa.

---
