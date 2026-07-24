# GO_TO_MARKET_READINESS — Auditoría de Preparación Comercial

**Auditor:** Claude Sonnet 4.6 (instancia independiente, solo lectura)
**Fecha:** 2026-07-21
**Referencia SDD:** `SDD-plataforma-edge-ai-b2b2b-multivertical-v3-FINAL.md` v3.4-FINAL
**Método:** lectura de código fuente, comandos bash, ejecución de tests — evidencia citada con ruta/línea exacta. Cero simulación.

---

## 1. RESUMEN EJECUTIVO

### Veredicto por pilar

| Pilar | Veredicto | Razón de una línea |
|-------|-----------|-------------------|
| **Producto** | ⚠️ **NO-GO** | Fases 1-2 completas; 4 de 6 entregables de Fase 3 faltan o están rotos |
| **Calidad / Confiabilidad** | ⚠️ **NO-GO** | E2E smoke ✅ · pgTAP 4/4 ✅ (con workaround) · suite golden del Copiloto: cero casos construidos |
| **Infraestructura** | ❌ **NO-GO DURO** | Todo el código de producto es **untracked en git**; cero deployment; ningún secreto de producción configurado |

### Bloqueadores duros (ordenados por impacto de lanzamiento)

| # | Bloqueador | Impacto |
|---|-----------|---------|
| **B-1** | **Todo el código de producto está fuera de git** — cloud/, edge/, dashboard/, docker/, tests/, alembic/ son `Untracked`. Solo README y SDD tienen commits. | No hay nada que desplegar desde origin/master. Bloquea todo lo demás. |
| **B-2** | **Dockerfile de producción del Edge Gateway corre en STUB mode** — `docker/edge/Dockerfile` excluye ultralytics/PyTorch deliberadamente. Un gateway en producción haría inferencia sintética, no real. | El producto principal (analítica de video real) no funciona en producción. |
| **B-3** | **Model Registry tiene URL y SHA256 placeholder** — `cloud/models/router.py:95-96` retorna `https://r2.traxia.io/models/yolo_retail_v1.0.0.pt?sig=placeholder` y `sha256: "placeholder-sha256-override-in-tests"`. | Edge Gateway fallaría al descargar modelo en producción. |
| **B-4** | **Endpoint de derecho al olvido (`DELETE /v1/tenants/{tid}/partners/{pid}/data`) no existe** — SDD §12.12 y Fase 3 lo exigen. Ninguna función en cloud/ lo implementa. | Obligación legal (GDPR/DPDPA equivalentes) y entregable explícito de Fase 3. |
| **B-5** | **Suite de evaluación del Copiloto (SDD §12.9, ~20 casos golden) no construida** — `tests/copilot/test_copilot_api.py` tiene 11 tests de API pero cero casos golden con respuestas de referencia ni LLM-as-judge. El SDD la exige como gate pre-release comercial. | Sin gate de calidad no hay garantía de que el Copiloto no alucine datos de otro tenant. |

---

## 2. PILAR A — PRODUCTO

### 2.1 Tabla §3.1 — 12 decisiones del MLP recortado

| # SDD | Decisión | Estado | Evidencia | Esfuerzo si falta |
|-------|----------|--------|-----------|-------------------|
| 1 | Managed Agents → Fase 4; Copiloto vía Messages API directa | ✅ | `cloud/copilot/router.py`: `import anthropic` + llamada directa a `messages.create()` sin sandbox | — |
| 2 | Reseller → fuera del MLP (tabla existe, sin flujo de UI/backend) | ✅ | `alembic/versions/0001_initial_schema.py:505+`: tabla `resellers` + RLS creados. Ninguna ruta `/v1/resellers` en `cloud/main.py` | — |
| 3 | Partners completos: alta/baja 1 paso, `access_expires_at`, vista restringida | ✅ | `cloud/backoffice/router.py:206` POST /backoffice/partners; `router.py:233`: INSERT con `access_expires_at`. `dashboard/src/pages/Partners.tsx` implementado. | — |
| 4 | Ambientes Dev+Prod con pgTAP como gate | ⚠️ | Tests existen y pasan 4/4, pero `tests/run_tests.sh` falla sin `CREATE EXTENSION pgtap` previo (extensión instalada en imagen pero no activada en DB). Workaround aplicado en esta sesión. | 30 min: agregar `CREATE EXTENSION IF NOT EXISTS pgtap;` al initdb o al script de seed |
| 5 | Credenciales Edge Gateway: access token 24h + refresh 90 días | ✅ | `cloud/auth/router.py:51,109`: INSERT/UPDATE con `interval '90 days'`. Revocación: `status='revoked'` en `edge_gateways`. | — |
| 6 | Banca fuera del MLP | ✅ | `cloud/models/router.py`: registry solo tiene entrada `"retail"`. | — |
| 7 | Motor de Acciones: Slack + Telegram + Correo por defecto; WhatsApp opt-in | ✅ | `cloud/actions/channels.py`: `_send_slack()`, `_send_telegram()`, `_send_email()`, `_send_whatsapp()` implementados. E2E smoke prueba Slack (d) PASS. | — |
| 8 | Plantillas SOP (personal en caja, apertura/cierre, cliente sin atender) | ⚠️ | Motor de reglas funciona; plantillas son proceso operativo de onboarding, no hardcoded. No hay seed de plantillas en código. | 1 día: SQL seed de 3 reglas-plantilla en el onboarding del tenant |
| 9 | `staff_exclusion` zone type excluye personal del conteo | ✅ | `zone_dwell_summary` view (verificada): `WHERE z.zone_type <> 'staff_exclusion'`. Dashboard `Zones.tsx:19`: valor `'staff_exclusion'` en selector. Nota: SDD dice `staff_area`, código usa `staff_exclusion` — inconsistencia de naming solo. | — |
| 10 | MFA vía Supabase Auth (configuración, no desarrollo) | ⚠️ | `cloud/auth/mfa.py` existe; endpoint `/v1/auth/mfa/enroll` y `/verify`. PERO `SUPABASE_URL` defaul a `""` — sin Supabase configurado, MFA está deshabilitado silenciosamente. | 2-4 h: crear proyecto Supabase y configurar variables |
| 11 | Onboarding/offboarding de Tenants (máquina de estados) | ✅ | `cloud/lifecycle/router.py`: `/v1/tenants/register` (201), `/v1/superadmin/tenants/{id}/approve`, `/v1/superadmin/tenants/{id}/deactivate`. | — |
| 11b | **Endpoint SuperAdmin login** (brecha conocida, anotada en SDD §3.1) | ❌ | Solo existe `make_platform_admin_token(admin_id)` en `cloud/auth/superadmin.py:32` — emisión programática, sin endpoint HTTP. `grep -rn "superadmin/login" cloud/` → vacío. | 4-6 h: `POST /v1/superadmin/login` con bcrypt/Argon2 contra `platform_admins` |
| 12 | Hosting: Supabase + R2 + Render/Cloud Run | ❌ | Cero archivos de deployment en repo. `find . -name "render.yaml" -o -name "fly.toml" -o -name ".github"` → ninguno. `DATABASE_URL` en docker-compose.yml apunta a localhost. | 1-2 semanas: crear cuentas, configurar CI/CD, primer deploy |

### 2.2 Entregables por fase (SDD §13)

#### Fase 1 — Tubería de Datos Básica, Model Manager, Esquema Físico

| Entregable | Estado | Evidencia |
|-----------|--------|-----------|
| Esquema particionado (`tracking_coordinates` + `pg_partman`) | ✅ | `alembic/versions/0001_initial_schema.py` + `0003_gateway_grace_window.py`. E2E smoke (a) PASS: pg_partman config row + particiones mensuales verificadas. |
| RLS completo en todas las tablas | ✅ | pgTAP 4/4 PASS (`tests/isolation/01-04`). Break-glass policy en `0001_initial_schema.py:419`. |
| Edge Gateway: YOLO Nano + ByteTrack + cola SQLite | ⚠️ | `edge/gateway.py`, `edge/model_manager.py`, `edge/inference_queue.py` implementados. **Pero:** `docker/edge/Dockerfile` excluye ultralytics — producción usa STUB. Solo `docker/edge/Dockerfile.e2e` hace inferencia real. |
| Model Manager: descarga OTA + `Range` resumible | ✅ | `edge/model_manager.py`: headers `Range` en `_download_model_to_tmp()`. Tests `test_model_manager.py:192`: "mock server drops connection after half bytes." |
| Access + refresh token auth | ✅ | `cloud/auth/router.py`: activate/refresh/revoke. E2E smoke (c) verifica gateway online. |
| pgTAP como gate CI | ⚠️ | Tests pasan (4/4) pero `tests/run_tests.sh` requiere `CREATE EXTENSION pgtap` manual previo. Sin CI configurado. |

#### Fase 2 — Backoffice, Partners, Dashboards

| Entregable | Estado | Evidencia |
|-----------|--------|-----------|
| Mapeo de zonas con `staff_exclusion` | ✅ | `dashboard/src/pages/Zones.tsx:7,19`: selector incluye 'staff_exclusion'. View verifica exclusión. |
| Backoffice de usuarios + asignación granular a sucursales | ✅ | `cloud/backoffice/router.py`: `/users` (GET/POST), `/users/{id}/sites/{site_id}` (DELETE). |
| Módulo de reventa Partner en un paso | ✅ | `cloud/backoffice/router.py:206-296`: una transacción: partner + user + zones. |
| `access_expires_at` + job diario de revocación | ✅ | `cloud/backoffice/scheduler.py`: `revoke_expired_partners()` thread daemon. |
| Dashboard: tráfico, dwell, comparación inter-sucursal | ✅ | `dashboard/src/pages/Traffic.tsx`, `Dwell.tsx`, `Comparison.tsx`. Playwright tests pasan (`test-results/.last-run.json`: `"status": "passed"`). |
| Vista restringida Partner (matriz roles) | ✅ | `dashboard/src/hooks/useAuth.ts`: `isPartner`, `isPartnerAdmin`, `isPartnerViewer`. `Nav.tsx` oculta módulos según rol. |

#### Fase 3 — Flota, Operación Interna, Valor Cognitivo

| Entregable | Estado | Evidencia |
|-----------|--------|-----------|
| Portainer / gestión de flota OTA | ❌ | `grep -rn "portainer\|fleet" cloud/ edge/ docker/` → sin resultados. Solo mencionado en README y SDD §13. Esfuerzo: ~1 semana (instalación + Docker Swarm/Compose remote). |
| Heartbeat monitoring + alertas escalonadas Día 1/3/5 | ❌ | `grep -rn "heartbeat\|last_heartbeat" cloud/` → vacío. Schema tiene `edge_gateways.last_heartbeat_at` (campo existe), pero ningún job lo evalúa. Esfuerzo: 3-4 días. |
| Model Registry como servicio versionado (URL real) | ❌ | `cloud/models/router.py:95`: URL hardcoded `"https://r2.traxia.io/models/yolo_retail_v1.0.0.pt?sig=placeholder"`, SHA256 `"placeholder-sha256-override-in-tests"`. Sin R2 bucket creado. Esfuerzo: 1 día código + 0.5 día infra. |
| Operación interna: break-glass auditado | ⚠️ | Esquema DDL completo en `alembic/0001`: `break_glass_audit_log` + función `sec_break_glass_allows_camera()` + policy RLS. Sin endpoint HTTP de activación — solo accesible programáticamente vía GUC. Esfuerzo: 4-6 h endpoint. |
| Operación interna: retención/purga automatizada 13 meses | ⚠️ | Campo `created_at` en tablas time-series; pg_partman puede hacer DROP de particiones viejas. Sin job/cron configurado. Esfuerzo: 2 h pg_partman config + test. |
| Cifrado RTSP URL (`rtsp_url_ciphertext`) | ⚠️ | Schema tiene `rtsp_url_ciphertext BYTEA`, `rtsp_url_key_id TEXT`. Sin implementación de encrypt/decrypt en cloud/ (backoffice guarda `'\\x00'::bytea` hardcoded en test seeds). Esfuerzo: 2-3 días (elegir KMS + implementar). |
| Copiloto (chat + auditoría de stock) | ✅ | E2E smoke (e) PASS: respuesta real en español. (f) PASS: 9 findings + presigned URL 200. `cloud/copilot/router.py` + `audit.py`. |
| Motor de Acciones | ✅ | E2E smoke (d) PASS: regla threshold disparada, `status=sent`. `cloud/actions/engine.py` + `channels.py`. |
| Partner offboarding + derecho al olvido | ❌ | `DELETE /v1/tenants/{tid}/partners/{pid}/data` no existe. `grep -rn "olvido\|forget\|/data" cloud/` → sin resultados. Backoffice solo tiene `POST /partners/{id}/revoke` (desactiva acceso, no purga datos). Esfuerzo: 1-2 días. |
| Suite evaluación Copiloto §12.9 (~20 casos golden) | ❌ | `tests/copilot/test_copilot_api.py`: 11 tests de API (scope, 503, injection defense). Cero casos golden con preguntas reales de retail, respuestas de referencia, ni runner LLM-as-judge. Esfuerzo: 1-2 semanas (definir casos + construir runner). |
| Playwright E2E dashboard | ✅ | `dashboard/e2e/`: `fase3.spec.ts`, `tenant_admin.spec.ts`, `partner_viewer.spec.ts`, `operator.spec.ts`. Último run: `"status": "passed", "failedTests": []`. |

---

## 3. PILAR B — CALIDAD / CONFIABILIDAD

### 3.1 Estado del repositorio git

```
$ git -C /Users/rodrigogalindo/Traxia-Analytics status
On branch master
Your branch is up to date with 'origin/master'.

Changes not staged for commit:
	modified:   README.md
	modified:   SDD-plataforma-edge-ai-b2b2b-multivertical-v3-FINAL.md

Untracked files:
	alembic.ini
	alembic/           ← MIGRACIONES DE DB — no en git
	cloud/             ← TODO EL BACKEND — no en git
	dashboard/         ← TODO EL FRONTEND — no en git
	docker-compose.yml ← COMPOSE PRODUCCIÓN — no en git
	docker-compose.e2e.yml
	docker/            ← TODOS LOS DOCKERFILES — no en git
	edge/              ← TODO EL EDGE GATEWAY — no en git
	requirements.txt   ← DEPENDENCIAS — no en git
	tests/             ← TODOS LOS TESTS — no en git
```

**Veredicto:** origin/master solo contiene README.md y el SDD. **Cero código de producto committeado.** Los commits recientes (99bc217, e29e862, be74aad, ...) son exclusivamente de documentación.

### 3.2 Suite E2E Smoke Test (`./tests/run_e2e.sh`)

Ejecutado en esta sesión (2026-07-21 12:12–12:15):

```
$ DATABASE_URL=... ANTHROPIC_API_KEY=... python3 tests/e2e/smoke_test.py
(a) PASS  pg_partman + RLS on agent_findings/action_rules
(b) PASS  GET /health → 200  {"status":"ok"}
(c) PASS  12,783 eventos; ByteTrack: track-002/003/004 × 4261 apariciones cada uno
(d) PASS  Regla threshold bb1e2e00 disparada, status=sent (httpbin 200)
(e) PASS  POST /v1/copilot/chat → 200, answer_len=458, zones=1
(f) PASS  9 agent_findings; presigned URL HTTP 200 (image/jpeg 690B); snapshot_r2_key no expuesto
(g) PASS  delta=0 en 11 polls durante 60s outage; +1241 eventos drenados post-outage
Frontend PASS  nginx 200 SPA HTML; /v1/ proxied al cloud-api
```

**Nota importante sobre (f):** el snapshot que sube a MinIO es una imagen gris 64×64 px (`cloud/copilot/audit.py:39-44`), no un frame real de cámara. Claude Vision responde apropiadamente ("imagen insuficiente — cámara sin señal"). En producción real el snapshot debería ser el frame más reciente del RTSP, lo que requiere integración que no existe aún.

### 3.3 Suite pgTAP de aislamiento (`tests/isolation/`)

```bash
# Workaround requerido (no en script oficial):
$ psql ... -c "CREATE EXTENSION IF NOT EXISTS pgtap;"

$ DATABASE_URL=... bash tests/run_tests.sh
01_tenant_isolation.sql          OK
02_site_scoped_isolation.sql     OK
03_partner_isolation.sql         OK
04_tenant_keeps_visibility_of_ceded_zones.sql  OK
Results: 4 passed, 0 failed
```

**Sin el workaround:** `ERROR: function plan(integer) does not exist` — el script `tests/run_tests.sh` no llama `CREATE EXTENSION pgtap` antes de correr los tests.

**pgTAP está en el Dockerfile** (`docker/postgres/Dockerfile`: compilado desde source), pero no se activa automáticamente en la DB. Corrección trivial (30 min).

### 3.4 Suite de evaluación del Copiloto (SDD §12.9)

**Estado: NO EXISTE.**

`tests/copilot/test_copilot_api.py` contiene:
- 6 tests de endpoint HTTP (scoping, 503, 422, inyección)
- 2 tests de defensa contra prompt injection (verifican el system prompt)
- 3 tests de ciclo de auditoría (mock de `_find_dwell_drops`)
- **CERO** casos golden con preguntas reales de retail

El SDD §12.9 exige: ~20 casos por vertical (6 footfall, 4 dwell, 4 colas, 3 scope, 3 adversariales) + runner LLM-as-judge (Sonnet) con rúbrica + firma humana. Ninguno de estos componentes existe.

**Por qué importa:** sin gate de calidad no hay forma reproducible de garantizar que el Copiloto no cite datos fuera del alcance del usuario antes del primer cliente real.

### 3.5 Marcadores de incompletitud en código de producto

| Archivo | Línea | Contenido | ¿Bloquea producción? |
|---------|-------|-----------|---------------------|
| `cloud/models/router.py` | 95 | `"download_url": "https://r2.traxia.io/models/yolo_retail_v1.0.0.pt?sig=placeholder"` | **SÍ** — Edge Gateway fallaría al descargar |
| `cloud/models/router.py` | 96 | `"sha256": "placeholder-sha256-override-in-tests"` | **SÍ** — Verificación de integridad fallaría |
| `docker/edge/Dockerfile` | comment | `# ultralytics/PyTorch intentionally excluded... gateway falls back to STUB mode` | **SÍ** — Sin inferencia real en producción |
| `dashboard/src/pages/Login.tsx` | comment | `"In production this would integrate with an OAuth/OIDC flow"` | **SÍ** — Clientes pegarían JWT a mano |
| `cloud/copilot/audit.py` | 39-44 | Placeholder 64×64 gris en lugar de frame real del RTSP | Limitación funcional — auditoría visual no tiene imagen real |
| `cloud/copilot/audit.py` | 108 | `# For MLP: use placeholder` en `_fetch_snapshot()` | Mismo que arriba |

---

## 4. PILAR C — INFRAESTRUCTURA

### 4.1 CI/CD y deployment

```bash
$ find . -name "render.yaml" -o -name "fly.toml" -o -name "Procfile" -o -name ".github" -type d
(vacío)

$ find . -name "*.yml" | xargs grep -l "workflow\|CI\|deploy" 2>/dev/null
dashboard/node_modules/playwright/lib/agents/copilot-setup-steps.yml  ← solo dependencia
```

**Veredicto: cero infraestructura de CI/CD.** No hay pipeline de integración continua, no hay deployment automatizado, no hay configuración de ningún proveedor de hosting.

### 4.2 Variables de entorno requeridas

#### `cloud/config.py`

| Variable | Default | Requerida en producción | Evidencia de valor real en repo |
|----------|---------|------------------------|--------------------------------|
| `JWT_SECRET` | **raise ValueError** | Sí — falla al arrancar sin ella | Ninguna |
| `DATABASE_URL` | `localhost:5432/traxia` | Sí (URL de Supabase/Render) | Ninguna |
| `PLATFORM_ADMIN_SECRET` | `""` | Sí (para SuperAdmin ops) | Ninguna |
| `SUPABASE_URL` | `""` | Sí (para MFA) | Ninguna |
| `SUPABASE_ANON_KEY` | `""` | Sí (para MFA) | Ninguna |
| `SUPABASE_SERVICE_ROLE_KEY` | `""` | Sí (para MFA) | Ninguna |
| `ANTHROPIC_API_KEY` | `""` | Sí (Copiloto se desactiva sin ella) | **Sí** — proporcionada en esta sesión (no persistida en repo) |
| `R2_ACCOUNT_ID` | `""` | Sí (snapshots sin URL en findings) | Ninguna |
| `R2_ACCESS_KEY_ID` | `""` | Sí | Ninguna |
| `R2_SECRET_ACCESS_KEY` | `""` | Sí | Ninguna |

#### `edge/config.py`

| Variable | Default | Requerida en producción |
|----------|---------|------------------------|
| `CLOUD_API_URL` | `http://localhost:8000` | Sí (URL del backend en Render/Cloud Run) |
| `GATEWAY_ID` | `""` | Sí (ID único por dispositivo — MAC/serial) |
| `RTSP_URLS` | `[]` (lista vacía) | Sí (URL RTSP de las cámaras del cliente) |

**Ninguna variable de producción tiene evidencia de valor real en el repositorio.** No hay `.env.production`, no hay secrets configurados en ningún servicio de CI/CD.

### 4.3 Estado real de servicios externos

| Servicio | Estado verificable desde el repo | Conclusión |
|---------|----------------------------------|-----------|
| **Supabase** (hosting + Auth/MFA) | `SUPABASE_URL=""` en config. Sin URL de proyecto en ningún archivo. | **Fuera del alcance** — verificar manualmente si existe proyecto creado |
| **Cloudflare R2** (snapshots + Model Registry) | URL `r2.traxia.io` en models/router.py es placeholder. Sin `R2_ACCOUNT_ID`. | **Fuera del alcance** — verificar manualmente si bucket existe |
| **Render / Cloud Run** (backend hosting) | Sin render.yaml, sin Procfile, sin .github/workflows. | **No desplegado** — ninguna evidencia de deployment |
| **GitHub origin/master** | `git log`: 8 commits, todos de documentación. | **Código de producto no está en origin** |

---

## 5. LO QUE NO PUDISTE VERIFICAR — PILAR D (fuera del repo)

Los siguientes elementos son necesarios para un lanzamiento comercial y **no viven en este repositorio**. No se puede determinar su estado desde el código; requieren verificación manual:

| Ítem | Estado desde el repo |
|------|---------------------|
| **Contrato tipo con el Asset Owner** (términos de servicio, SLA, responsabilidades de datos bajo GDPR/DPDPA locales) | Fuera del alcance del repositorio — verificar manualmente |
| **Política de privacidad publicada** (dado que el producto procesa video de personas en instalaciones del cliente) | Fuera del alcance del repositorio — verificar manualmente |
| **Pricing ejecutado** (Plan Base / Plan Enterprise — Sección 10.1 define la economía unitaria pero no hay hoja de precio publicada) | Fuera del alcance del repositorio — verificar manualmente |
| **Sitio web de ventas / landing page** | Fuera del alcance del repositorio — verificar manualmente |
| **Canal de soporte al cliente** (ticket system, SLA de respuesta) | Fuera del alcance del repositorio — verificar manualmente |
| **Acuerdo con Anthropic** para uso comercial del API (uso empresarial de Claude — verificar términos de uso en volumen) | Fuera del alcance del repositorio — verificar manualmente |
| **Cuenta Cloudflare R2 con bucket creado** (`traxia-snapshots`) | Fuera del alcance del repositorio — verificar manualmente |
| **Proyecto Supabase creado** con Auth/MFA configurado | Fuera del alcance del repositorio — verificar manualmente |
| **Hardware del Edge Gateway** disponible para el cliente piloto (la PC conectada a cámaras) | Fuera del alcance del repositorio — verificar manualmente |
| **Manual de instalación del Edge Gateway** (docker pull + configuración de RTSP_URLS + GATEWAY_ID para técnicos sin perfil dev) | Fuera del alcance del repositorio — verificar manualmente |

---

## Apéndice: Re-verificación de hallazgos de la auditoría previa

| Hallazgo previo | Estado en esta auditoría | Evidencia |
|----------------|--------------------------|-----------|
| Código no committeado en git | **CONFIRMADO** | `git status`: cloud/, edge/, dashboard/, docker/, tests/, alembic/ son Untracked |
| Edge Gateway STUB en producción | **CONFIRMADO** | `docker/edge/Dockerfile:comment`: "ultralytics/PyTorch intentionally excluded... STUB mode" |
| Dashboard login = caja para pegar JWT | **CONFIRMADO** | `dashboard/src/pages/Login.tsx:comment`: "paste-in flow for MLP. In production this would integrate with OAuth/OIDC" |
| Model Registry URL placeholder | **CONFIRMADO** | `cloud/models/router.py:95-96`: URL y SHA256 con valor literal "placeholder" |
| Sin endpoint derecho al olvido para Partners | **CONFIRMADO** | `grep -rn "olvido\|/data" cloud/` → vacío. Solo existe `POST /partners/{id}/revoke` |
| Sin fleet management / Portainer | **CONFIRMADO** | `find . -name "portainer*"` → ninguno. Solo mencionado en README y SDD §13 como Fase 3 |
| Sin suite evaluación del Copiloto (§12.9) | **CONFIRMADO** | `tests/copilot/test_copilot_api.py`: 11 tests de API, 0 casos golden |

**Hallazgos nuevos no cubiertos en la auditoría previa:**

- **SuperAdmin login endpoint faltante** (SDD §3.1/11b lo reconoce como "brecha conocida" — solo existe `make_platform_admin_token()` programático)
- **`CREATE EXTENSION pgtap` faltante en `tests/run_tests.sh`** — pgTAP instalado en Dockerfile pero no activado en DB; tests fallan sin workaround manual
- **Snapshot del Copiloto es imagen placeholder** (64×64 gris), no frame real del RTSP — auditoría visual no tiene utilidad práctica
- **Break-glass sin endpoint HTTP** — schema completo en DB pero sin `POST /v1/superadmin/break-glass` para activarlo desde la API
- **Cifrado RTSP URL no implementado** — schema tiene `rtsp_url_ciphertext BYTEA` pero ningún código de cloud/ encripta/desencripta; seeds usan `'\\x00'::bytea` hardcoded
- **SDD usa `staff_area`, código usa `staff_exclusion`** — inconsistencia de naming (cosmética, sin impacto funcional)
- **MFA silenciosamente deshabilitada** cuando `SUPABASE_URL=""` — código existe pero la condición `if not config.SUPABASE_URL: return 503` hace que parezca funcionar hasta que se prueba
