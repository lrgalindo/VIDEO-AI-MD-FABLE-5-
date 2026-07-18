# System Design Document (SDD) v3.4 — FINAL

## Plataforma de Analítica "Hardware-Free" vía Edge AI — Motor Base Multi-Vertical (B2B2B)

> **Estatus del documento:** VERSIÓN FINAL. Fuente única de verdad de la
> **arquitectura completa** del producto para desarrollo técnico y salida al
> mercado. A partir de v3.4, este documento distingue explícitamente entre **la
> arquitectura completa** (todo lo diseñado hasta hoy, sin recortes) y **el MLP
> recortado** (Sección 3.1: qué se construye primero) — ninguna pieza de la
> arquitectura completa se elimina; lo que no entra al MLP queda documentado,
> validado y listo para activarse sin rediseño cuando el negocio lo requiera. Toda
> afirmación sobre productos de Anthropic fue verificada contra documentación
> oficial vigente al 2026-07-18 (pricing, estado de betas, modelos
> activos/retirados). Toda afirmación competitiva fue calibrada contra el material
> público de Agrex.ai vigente a la misma fecha. Toda afirmación sobre disponibilidad
> de extensiones en el hosting destino (Supabase) y sobre política de créditos de
> AWS/GCP fue verificada contra documentación oficial vigente a la misma fecha. Los
> cambios de cada iteración están detallados en el **Apéndice A — Changelog** al
> final del documento.

---

### Nota de versión

**v3.4-FINAL (esta iteración):** define el **MLP recortado** — qué se construye
primero — sin quitar ni un feature de cara al cliente ni retroceder en la
propuesta de valor frente a Agrex.ai. El recorte es exclusivamente de **madurez
operativa que el cliente nunca ve**: orquestación multiagente, PKI, ambientes
duplicados, y el rol Reseller completo (deferido a v2.0, no solo su comisión —
corrección respecto a v3.3, que solo excluía la liquidación). Nueva **Sección 3.1**
consolida las doce decisiones de alcance con su "gancho" de activación futura
(dónde vive ya construido en este mismo documento y qué dispara su encendido, sin
rediseño). Cambios que sí tocan arquitectura, todos validados por ejecución donde
aplica DDL: (a) **credenciales del Edge Gateway para el MLP** pasan de mTLS a
**refresh token** (access token 24h + refresh 90 días, revocación real en ≤24h vía
`edge_gateways.status='revoked'`) — mTLS (Sección 8.7 ya escrita) queda como
gancho para cuando un vertical lo exija contractualmente, no se descarta; (b)
**hosting del MLP** se fija en Supabase + Cloudflare R2 + Render/Cloud Run +
GitHub — verificado que ni AWS ($200 de crédito, cuenta se cierra a los 6 meses
salvo upgrade a plan pagado) ni GCP ($300/90 días) sostienen una cuenta nueva sin
reloj de expiración, mientras que estos sí; AWS/RDS quedan como ruta de escalamiento
para Fase 4+; (c) **ambientes** se reducen a Dev+Prod para el MLP (suite pgTAP como
gate obligatorio de promoción), QA/Staging como ambiente adicional para cuando el
volumen lo justifique; (d) **tres refinamientos de Partners** que la revisión reveló
como necesarios para el MLP y no estaban en el esquema: alta/baja en un solo paso,
acceso por tiempo limitado (`partners.access_expires_at`, nueva columna, DDL
validado por ejecución) y una matriz explícita de qué ve un Partner Admin/Viewer en
el frontend; (e) **Motor de Acciones**: canales por defecto Slack+Telegram+Correo
(costo marginal cero) con WhatsApp opt-in de costo pass-through explícito (no
absorbido), más plantillas de reglas SOP de compliance (personal ausente en caja,
apertura/cierre fuera de horario, cliente sin atender) sobre el mismo motor ya
diseñado; (f) **zona de exclusión de personal** (`zone_type='staff_area'`) para no
contar empleados como clientes; **demografía (edad/género) queda deliberadamente
fuera por defecto** — refuerza Zero Biometrics como diferenciador de privacidad
frente a Agrex, no una limitación técnica; (g) **MFA** viene de fábrica con
Supabase Auth (configuración, no desarrollo); (h) **máquina de estados de
onboarding/offboarding de Tenants** simplificada para el MLP (auto-registro →
aprobación de un clic → activo; baja dispara retención + revocación de tokens). El
Roadmap (Sección 13) se actualiza con el estimado recortado (8-13 semanas, antes
10-19) y la Sección 12 completa (Enjambre/Managed Agents) queda intacta como
Fase 4 — no se reescribe una sola línea, solo se reafirma que el MLP no la activa.

**v3.3-FINAL:** cierre de portabilidad de hosting y barrido de
gaps de ciclo de vida. (1) **Corrección bloqueante de arquitectura:** TimescaleDB
está **deprecado para proyectos nuevos de Supabase** (Postgres 17; solo sobrevive
en proyectos viejos sobre Postgres 15 hasta ~mayo 2026) — verificado contra la
documentación oficial de Supabase. Como el destino de hosting de bajo costo/fallback
es Supabase free tier, toda la capa time-series se rediseña sobre **particionamiento
declarativo nativo de PostgreSQL + `pg_partman`** (Sección 8.6, reescrita), sin
ninguna extensión no disponible en Supabase; el DDL de particionamiento se **validó
por ejecución contra PostgreSQL 16 plano** y se documenta explícitamente la pérdida
de la compresión columnar automática de Timescale y sus mitigaciones. (2) **Bugs
técnicos corregidos y validados por ejecución:** se escribe el RLS completo y real
(no "sigue el mismo patrón" en prosa) para las ocho tablas restantes (`sites`,
`cameras`, `zones`, `users`, `partners`, `tenants`, `resellers`,
`user_site_assignments`); se corrige un defecto en `agent_findings_write` que
impedía a un subagente en contexto Partner escribir hallazgos; se agrega política de
`INSERT` a `zone_dwell_sessions` (bloqueada por `FORCE RLS`); se decide y documenta
explícitamente el RLS de `agent_run_metrics`; y se corrige el residual "2 niveles"
del diagrama de la Sección 6. (3) **Secciones nuevas de ciclo de vida:** Flujo 6
(referido de Reseller) y Flujo 7 (reemplazo de hardware / DR del Edge); credenciales
del Edge por **mTLS** con rotación y revocación contra estado en DB (8.7); alertas
escalonadas antes de pérdida de datos offline vía el Motor de Acciones (12.11);
offboarding de Partner con derecho al olvido sobre `agent_findings` (12.12);
descargas OTA resumibles con manejo de expiración de URL firmada (9.1); y una tabla
de decisiones **Build-vs-Buy** (7.3). (4) **Enganche al Roadmap:** las seis piezas
del punto (3) más la tabla Build-vs-Buy quedaban sin mención en la Sección 13 —
diseñadas pero no ancladas al plan de ejecución. Se ubican explícitamente en Fase 1
(mTLS, descargas resumibles, Build-vs-Buy — mecanismos definitivos que se
construyen una sola vez) y Fase 3 (Flujo 6, Flujo 7, alertas escalonadas y
offboarding — extensiones de Operación Interna y el Motor de Acciones). El resto
del documento no se toca salvo donde estas correcciones exigen consistencia.

**v3.2-FINAL:** auditoría integral en tres frentes y cierre del
documento como versión definitiva. (1) **Negocio:** la Sección 10.1 se reescribe con
una economía unitaria de dos planes (Base y Enterprise) y el costo del Enjambre
Cognitivo se recalcula con los multiplicadores reales publicados por Anthropic
(~15x tokens para sistemas multiagente, ~4x para agentes individuales) — el Plan
Enterprise **no cabe** dentro del COGS objetivo original de $22-41/sede y se
re-precia en consecuencia, en vez de forzar una estimación optimista. (2) **Datos:**
se corrigen cuatro defectos reales del DDL/RLS de la Sección 8: la política de
`zone_dwell_sessions` dejaba ciego al Asset Owner sobre zonas cedidas a Partners
(contradiciendo el Flujo 3); la política break-glass otorgaba acceso a *todos* los
tenants mientras hubiera cualquier sesión abierta; los datos semilla y tests pgTAP
usaban literales no-UUID que fallan en ejecución; y las funciones helper ahora son
`STABLE LEAKPROOF PARALLEL SAFE` (requisito no negociable). El DDL completo fue
**validado por ejecución** contra PostgreSQL 16 (RLS incluido; llamadas TimescaleDB
verificadas contra su documentación). (3) **Infraestructura/IA:** se retira toda
referencia a Claude 3.5 Sonnet (modelo retirado desde oct-2025) y se define la
estrategia de modelos vigente (Haiku 4.5 / Sonnet); la Sección 12 se expande con:
evaluación de paralelizabilidad por subagente (12.6), patrón de artefactos para el
flujo subagente↔DB (12.7), observabilidad sin contenido conversacional (12.8),
metodología de evaluación de calidad del Copiloto/Enjambre (12.9), y el Motor de
Acciones que cierra la brecha competitiva contra la capa agéntica de Agrex.ai
(12.10). El estatus de multiagent orchestration se actualiza: ya no es research
preview — forma parte de la beta pública `managed-agents-2026-04-01`.

**v3.1:** se agrega la Sección 12 — la arquitectura
del Enjambre Cognitivo sobre **Claude Managed Agents**, con 5 correcciones/adiciones
verificadas contra documentación oficial vigente (no contra una transcripción de
segunda mano): (1) el aislamiento real entre Partners y Asset Owner requiere
**sesiones separadas**, no sub-agentes de una misma sesión — los sub-agentes
comparten sandbox, filesystem y vault; (2) el modelo de aislamiento de datos sigue
siendo el de **tres niveles** ya construido en la Sección 8 (`tenant → site →
partner`) — no hubo regresión al modelo de dos niveles en este documento; (3) nota
de compliance por vertical (Managed Agents no es elegible para ZDR/HIPAA BAA); (4)
separación explícita entre el Copiloto en vivo (Messages API directa) y las tareas
asíncronas del Enjambre (Managed Agents); (5) nota de validación financiera del
costo real de Managed Agents contra el COGS objetivo. **Pendiente:** esta iteración
NO incluye la fusión completa de "B2B2B Asset Owner" / "Multi-Vertical" (ya
cubiertos en v3.0, Secciones 1-3/6-8) ni la Matriz de Pricing CENAM — no se
disponía del documento fuente con ese contenido al momento de esta edición.

**v3.0:** se formaliza el esquema físico de base de datos —
ejecutable, no solo conceptual— que sostiene toda la arquitectura de tenancy
descrita en v2.0. Se agrega: (1) jerarquía explícita de sucursales (`sites`) entre
`tenants` y `cameras`, con vistas agregadas para comparativos inter-sucursal; (2) un
modelo de gestión de usuarios desde el backoffice con asignación granular
usuario↔sucursal; (3) la implementación completa en RLS del aislamiento de dos
niveles Tenant→Partner ya descrito conceptualmente en v2.0, ahora a nivel de
`site_id` y con zonas (`zones`) reales para Dwell Time; (4) una estrategia de
ambientes (Dev/QA/Staging/Prod) con suite de pruebas de aislamiento automatizadas; y
(5) los mecanismos de operación interna (acceso break-glass, retención/purga,
backup/DR, cifrado de credenciales, observabilidad) necesarios para operar esto en
producción. Esta versión es la base sobre la cual arranca la construcción del
sistema — el Anexo técnico (Sección 8) ahora contiene DDL completo y ejecutable.

Este documento consolida el SDD original con los hallazgos de las rondas de
discovery. Los cambios estructurales que se integran de punta a punta son:

1. **Cambio de cliente principal (modelo B2B2B):** el cliente directo deja de ser la
   Marca/CPG y pasa a ser el **Asset Owner** — el dueño de la infraestructura de
   cámaras (supermercados, bancos, bodegas, centros comerciales, etc.). El Asset
   Owner usa la plataforma para optimizar su propia operación y, adicionalmente,
   puede revender sub-accesos analíticos filtrados a sus propios socios comerciales
   (marcas, inquilinos, aseguradoras, según el vertical).
2. **Motor Base Multi-Vertical (Core Engine):** no vendemos white-label hacia afuera;
   internamente la plataforma es un motor agnóstico a la industria. La activación de
   un vertical para un cliente es un proceso que ejecutamos **nosotros como empresa**
   durante el onboarding: instalamos y configuramos, en el computador local conectado
   a las cámaras, el Edge Gateway (Docker/software) que procesa el video y lo
   comprime en telemetría ligera de forma local, enviándola a la nube para que el
   resto del sistema (backend, tableros, Copiloto) se ejecute sobre esos datos. Como
   parte de esa misma configuración, el Edge Gateway descarga en tiempo de ejecución
   el modelo YOLOv8n especializado correspondiente al vertical asignado
   (`yolo_retail.pt`, `yolo_banking.pt`, `yolo_logistics.pt`, etc.), sin contaminar
   el código base ni inflar el consumo de RAM del hardware prestado por el cliente.

Todas las secciones fueron reescritas para reflejar estos dos cambios de forma
nativa, no como un parche. No se omite ninguna sección del documento original.

---

### 1. Resumen Ejecutivo

Este documento define la arquitectura y estrategia de producto para una plataforma
de analítica de video B2B2B, inspirada funcionalmente en modelos de clase mundial
como Agrex AI, orientada inicialmente a Centroamérica.

El problema central radica en que los dueños de infraestructura física con cámaras
—cadenas de supermercados (ej. Walmart, La Torre), bancos con sucursales, operadores
de bodegas y centros de distribución— carecen de visibilidad sobre el comportamiento
físico de las personas dentro de sus instalaciones, y además no tienen forma sencilla
de convertir esa visibilidad en un activo comercial frente a los socios que operan
dentro de su espacio (marcas de consumo masivo, inquilinos, aseguradoras). A esto se
suma que la infraestructura de videovigilancia (CCTV) instalada en la región promedia
entre 5 y 10 años de antigüedad, imposibilitando el uso de analítica nativa en la
cámara.

La oportunidad de negocio consiste en implementar un modelo **"Hardware-Free"** desde
la perspectiva de inversión de capital (CAPEX $0 para el cliente) y **B2B2B** desde
la perspectiva comercial: el **Asset Owner** es nuestro único cliente contractual
directo. Le vendemos un producto de dos capas:

* **Capa Operativa (uso interno del Asset Owner):** tableros de tráfico, colas,
  ocupación y mapas de calor para que optimice su propia operación, sin importar si
  es un supermercado, un banco o una bodega.
* **Capa de Reventa (módulo de sub-acceso):** una herramienta que le permite al Asset
  Owner crear, dar de alta y administrar sus propios "Partners" (socios comerciales
  — marcas, inquilinos, aseguradoras) y otorgarles acceso analítico **filtrado y
  acotado** a los ROIs (Regiones de Interés) que el Asset Owner decida compartir. La
  plataforma **no** vende ni contrata directamente con esos Partners: el Asset Owner
  es quien gestiona esa relación comercial hacia adelante.

Desde el punto de vista técnico, el sistema despliega un servicio de Edge Computing
**agnóstico que se instala directamente sobre la computadora o servidor que el
comercio ya posee**, con una opción de arrendamiento de hardware (ej. Mac Mini)
exclusivamente para clientes sin equipo adecuado. Este sistema extrae video
localmente, aplica modelos de Visión por Computadora (YOLO y algoritmos de Tracking)
con privacidad desde el diseño (Zero Biometrics), y envía telemetría ligera a la
nube.

Internamente, la plataforma opera como un **Motor Base Multi-Vertical**: el mismo
código de Edge Gateway y el mismo backend sirven a cualquier industria; lo único que
cambia por cliente es **qué modelo de detección especializado** se descarga en tiempo
de ejecución, según el vertical que el SuperAdmin le asignó en el onboarding. Esto
nos permite entrar a nuevas industrias (banca, logística) sin bifurcar el código base
ni renegociar la arquitectura, mientras mantenemos el consumo de RAM acotado en
hardware prestado (BYOD).

Un ecosistema de agentes LLM (Claude) interpretará la telemetría para ofrecer
tableros interactivos e insights cognitivos tanto al Asset Owner como a sus Partners
(dentro del alcance que el Asset Owner les habilitó), monetizables bajo un modelo
SaaS multi-tenant con aislamiento de tres niveles (tenant → site → partner).

**Posicionamiento frente al referente de mercado (Agrex.ai).** El competidor
directo ya tiene en producción: consulta en lenguaje natural sobre video histórico,
agentes autónomos de monitoreo 24/7, y acciones automáticas sin humano en el loop
(alertas WhatsApp/Slack/SMS, actualización de ERP, workflows de compliance), además
de la postura estándar de privacidad (procesamiento edge, sin biometría,
DPDPA/GDPR). Por lo tanto: (a) la privacidad edge/zero-biometrics es **table
stakes**, no diferenciador — se comunica como requisito cumplido, no como ventaja;
(b) la paridad funcional con su capa agéntica es requisito de salida (Copiloto en
lenguaje natural + Motor de Acciones, Secciones 12.4 y 12.10); y (c) nuestros
diferenciadores reales son tres: el **modelo B2B2B con módulo de reventa** (Agrex
vende B2B directo — nosotros convertimos la analítica del Asset Owner en un activo
comercial revendible, con aislamiento tenant → site → partner garantizado a nivel
de base de datos), el **modelo "Hardware-Free" BYOD con Zero-Video Egress** sobre
el hardware heredado típico de CENAM, y la **estructura de costos calibrada para
sensibilidad de precio alta** (Sección 10.1).

---

### 2. Contexto y Objetivos

#### Objetivos de Negocio

* **Modelo de Ingresos Recurrentes B2B2B:** establecer una suscripción mensual única
  con el Asset Owner (cliente maestro) que cubra su capa operativa, más un módulo
  opcional de reventa que le permite monetizar sub-accesos hacia sus Partners. La
  plataforma no factura directamente a los Partners en el MLP (ver Sección 3).
* **Despliegue de Baja Fricción:** evitar la instalación de cámaras nuevas, cableado
  o sensores físicos. Utilizar la infraestructura existente al máximo.
* **Cumplimiento Normativo Absoluto:** garantizar la nula recolección de datos
  biométricos o personales para sortear bloqueos de ciberseguridad y legales
  corporativos, sin importar el vertical.
* **Expansión Multi-Vertical sin Reescritura:** que la incorporación de una nueva
  industria (banca, logística, salud) sea un ejercicio de "entrenar/adquirir un
  modelo YOLO nuevo y registrarlo", no un fork del producto.

#### Objetivos Técnicos

* **Desacoplamiento Estricto:** separar físicamente la extracción de datos (Motor de
  Visión en el Edge) de la lógica de negocio y generación de insights (Controlador y
  LLMs en la nube).
* **Optimización de Ancho de Banda:** evitar el envío de flujos de video continuo a
  internet. La transmisión debe limitarse a metadatos JSON y fotogramas discretos
  (snapshots) bajo demanda.
* **Agnosticismo de Hardware y Sistema Operativo:** el Edge Gateway debe ser capaz de
  ejecutarse sobre Windows, Linux o macOS, soportando arquitecturas x86 y ARM. Debe
  adaptarse a las capacidades de cómputo del cliente (con o sin GPU), degradando
  amablemente su consumo de recursos si es necesario.
* **Agnosticismo de VMS:** el sistema debe poder leer protocolos estándar (RTSP,
  ONVIF) de cualquier NVR/DVR heredado, sin depender de marcas específicas.
* **Agnosticismo de Vertical (nuevo):** el Edge Gateway y el backend deben ser
  ciegos a la industria del cliente. La especialización vive exclusivamente en un
  artefacto intercambiable (el checkpoint `.pt` de YOLO) que se resuelve en tiempo
  de ejecución, no en tiempo de compilación/build.
* **Aislamiento Multi-Tenant de Tres Niveles (no negociable):** el modelo de datos
  y el RBAC deben soportar aislamiento en tres niveles — `tenant → site → partner`:
  (1) entre Asset Owners, (2) entre sucursales de un mismo Asset Owner (usuarios
  regionales acotados por `site`), y (3) entre los Partners de un mismo Asset Owner,
  y entre el propio Asset Owner y sus Partners (un Partner nunca debe ver datos
  operativos internos del Asset Owner que no le fueron explícitamente compartidos).
  El mecanismo base es PostgreSQL Row-Level Security con `FORCE ROW LEVEL SECURITY`
  y funciones helper `STABLE LEAKPROOF` (Sección 8). Ninguna optimización de costo
  puede debilitar este mecanismo.

---

### 3. Alcance

> **Nota v3.4:** esta sección describe el alcance de la **arquitectura completa**
> del producto. La **Sección 3.1**, inmediatamente después, define el subconjunto
> exacto — el MLP recortado — que se construye primero, con el "gancho" de dónde
> vive cada pieza diferida y qué la activa sin rediseño. Toda esta Sección 3 sigue
> siendo válida como diseño final; 3.1 es la capa de secuenciación de ejecución
> encima de ella.

#### Dentro del Alcance (MVP / MLP)

* Despliegue del Edge Gateway como contenedor Docker (o ejecutable nativo) sobre el
  hardware existente del cliente para procesamiento local de RTSP.
* **Model Manager en el Edge (nuevo):** componente que, al recibir el `vertical_type`
  asignado a la tienda, descarga desde el Model Registry en la nube el checkpoint
  YOLOv8n correspondiente, verifica su integridad (checksum SHA256), lo cachea
  localmente, y solo mantiene en memoria el modelo del vertical activo (nunca varios
  a la vez).
* Motor de Visión (YOLO) acoplado a un algoritmo de Tracking multiobjeto para
  detección exclusiva de la clase `person`, mantenimiento de IDs temporales y
  extracción de coordenadas `(x, y)`. **El tracker (ByteTrack) es agnóstico al
  vertical** — opera sobre bounding boxes sin importar qué checkpoint los generó, por
  lo que no requiere ninguna variante por industria.
* Mecanismo de sincronización offline con cola persistente local
  (Offline-Sync Resolution).
* Herramienta interna de mapeo espacial (configuración de polígonos/ROIs) por cámara.
* **Módulo de Reventa / Sub-Tenancy (nuevo):** panel dentro del portal del Asset
  Owner para crear, editar y desactivar Partners, y para asignarles/revocarles acceso
  a ROIs específicos. Incluye el flujo de invitación (el Partner recibe credenciales
  propias, con su propio rol `Partner Admin`).
* Base de datos de series de tiempo (Time-Series) para almacenamiento centralizado de
  telemetría.
* Tableros (Dashboards) multi-tenant con los tres niveles de aislamiento: vista
  operativa completa para el Asset Owner, vista acotada por sucursal para usuarios
  regionales, y vista acotada por ROI para cada Partner.
* Integración básica de un Agente Cognitivo (Claude — estrategia de modelos por
  carga de trabajo en la Sección 12.5: Haiku 4.5 para consultas conversacionales,
  Sonnet para auditorías visuales de quiebre de stock) sobre la telemetría
  disponible en el alcance de quien pregunta.
* Selector de vertical/industria en el flujo de onboarding, gestionado por el
  SuperAdmin, que determina qué modelo descarga el Model Manager.

#### Fuera del Alcance (Explícitamente Excluido)

* **Reconocimiento Facial y Emociones:** por limitaciones de resolución en cámaras
  heredadas, ángulos "vista de pájaro" y cumplimiento de privacidad de datos.
* **Integración Directa con POS (Cajas Registradoras):** el MVP no cruzará
  transacciones de facturación.
* **Venta de Hardware como Core:** no somos una empresa de hardware; el hardware de
  procesamiento (Mac Mini u otro) entrará exclusivamente como un servicio de leasing
  de contingencia.
* **Re-identificación Inter-cámara (ReID):** el rastreo de la misma persona saltando
  de una cámara a otra es computacionalmente prohibitivo para equipos de gama baja;
  el tracking vivirá dentro del límite visual de cada cámara.
* **Facturación Automatizada Asset Owner → Partner (nuevo):** la plataforma provee el
  control de acceso y el aislamiento de datos entre Partners, pero **no** es un motor
  de facturación ni de cobro para la relación comercial entre el Asset Owner y sus
  Partners. Esa relación (pricing, contrato, cobro) es responsabilidad exclusiva y
  externa del Asset Owner. Esto es una decisión de alcance deliberada para no
  convertirnos en una pasarela de pagos B2B en el MLP.
* **Entrenamiento de Modelos Especializados Más Allá de Retail (nuevo):** la
  arquitectura del Motor Base soporta múltiples verticales desde el día uno, pero el
  MLP se lanza comercialmente **solo con `yolo_retail.pt`** como vertical piloto.
  `yolo_banking.pt`, `yolo_logistics.pt` y otros quedan en el roadmap (Sección 12);
  no se entrenan ni se liberan en esta fase, para no diluir el foco de ingeniería.
* **Selección Automática de Vertical por IA:** la asignación de vertical a un cliente
  es una decisión manual del SuperAdmin en el onboarding, no una clasificación
  automática por visión por computadora.
* **Rol Reseller completo — no solo su facturación (corregido v3.4; en v3.3 solo se
  excluía la comisión).** Revisión de alcance: ningún caso de uso descrito para el
  MLP requirió un Reseller — todo lo necesario para el lanzamiento es la relación
  Asset Owner↔Partner. El **flujo entero** (Flujo 6, alta de Reseller, portal de
  gestión de cartera) queda fuera del MLP y se difiere a **v2.0**, no solo la
  liquidación de su comisión (que de todos modos seguiría fuera de alcance por el
  mismo principio ya aplicado a Partners: la plataforma provee atribución, no
  cobro). La tabla `resellers`, su RLS y el Flujo 6 ya están completos y validados
  en este documento (Secciones 5 y 8.3) — quedan **inertes** para el MLP, no
  eliminados; se activan sin rediseño cuando exista el primer acuerdo de canal real
  (ver Sección 3.1, decisión 2).
* **Demografía (edad, género) — deliberadamente fuera por defecto (nuevo, v3.4).**
  Es una capa de sensibilidad de dato mayor que la sola detección de `person` ya
  cubierta por Zero Biometrics, y precisamente esa política (cero biometría, cero
  demografía) es un diferenciador de privacidad frente a Agrex.ai (Sección 1), no
  una limitación técnica a superar. Se evalúa **caso por caso** si un cliente
  específico lo solicita explícitamente y bajo su propio consentimiento — nunca
  como comportamiento por defecto de la plataforma.
* **Vertical Banca — fuera del MLP (nuevo, v3.4).** El go-to-market del MLP se
  enfoca en retail, logística y otros verticales "enterprise" no regulados (perfil
  Walmart/La Torre). Esto ya era consistente con la restricción de la Sección 3
  arriba (`yolo_retail.pt` como único checkpoint del MLP) — se hace explícito aquí
  como decisión de mercado, no solo de modelo. Consecuencia directa: la restricción
  ZDR/HIPAA BAA de Managed Agents (Sección 12.3) **ni siquiera aplica** en el MLP,
  porque el MLP no usa Managed Agents (ver Sección 3.1, decisión 1) ni vende a
  banca. La Sección 12.3 ya cubre el compliance necesario para cuando se entre a
  ese vertical.

---

#### 3.1 MLP Recortado — Qué Se Construye Primero (nueva, v3.4)

**Principio rector:** nada de lo que sigue quita un feature que el cliente
experimenta. Lo que se recorta es exclusivamente **maquinaria interna** que no es
visible ni monetizable en el año 1 del contrato: orquestación multiagente, PKI,
ambientes duplicados, workflows de aprobación de varios pasos. Donde esta sección
*agrega* algo respecto al diseño original (acceso por tiempo limitado, vista
restringida de Partner, exclusión de personal, plantillas de SOP) es porque la
revisión de alcance reveló que sí importa para la propuesta de valor, aunque no
estuviera en el recorte inicial — no son features nuevas sin justificación, son
gaps que el recorte hizo visibles.

Cada decisión trae su **gancho de activación**: dónde vive ya construido en este
documento y qué evento de negocio lo enciende, sin rediseño.

| # | Decisión | Detalle | Gancho de activación futura |
| --- | --- | --- | --- |
| 1 | **Enjambre/Managed Agents → Fase 4, no MLP** | Copiloto y auditoría de stock corren sobre **Messages API directa** en el MLP (una sola llamada con imagen+prompt, Sección 12.4/12.5). Sin sandbox, sin sesiones, sin el multiplicador de ~15x en tokens (Sección 10.1). El cliente recibe exactamente las mismas dos funcionalidades. | La Sección 12 completa (sesiones por contexto, patrón de artefactos, evaluación de calidad) ya está escrita y validada — se activa entera en Fase 4 sin reescribir nada. |
| 2 | **Reseller → fuera del MLP, diferido a v2.0** | Ningún caso de uso del MLP lo requiere; todo lo necesario es la relación Asset Owner↔Partner. Confirmado explícitamente por el negocio (no solo su comisión, como decía v3.3 — el flujo entero). | Flujo 6 y la tabla `resellers` (con su RLS) ya están completos y validados en el SDD — se activan cuando se cierre el primer acuerdo de canal real. |
| 3 | **Partners (marcas/CPG) — se mantienen completos, con 3 refinamientos nuevos** | Alta/baja en un solo paso, acceso por tiempo limitado, y matriz explícita de vista restringida. Ver Secciones 4 y 5. | — (es MLP día 1) |
| 4 | **Ambientes: Dev + Prod únicamente** | Suite pgTAP (Sección 8.4) como gate obligatorio antes de cualquier promoción Dev→Prod. | QA/Staging se agregan como ambiente adicional al mismo pipeline cuando el volumen de clientes lo justifique — no se rediseña el pipeline, se agrega un nodo más. |
| 5 | **Credenciales del Edge Gateway: refresh token, no mTLS** | Access token de 24h + refresh token de 90 días (Sección 8.7). Revocación real: `edge_gateways.status='revoked'` bloquea el siguiente refresh — ventana máxima de exposición 24h. Sin PKI, sin diferencias de implementación entre Windows/Linux/Mac. | mTLS (Sección 8.7, ya escrito y validado en v3.3) se activa si algún vertical o cliente lo exige contractualmente. |
| 6 | **Banca fuera del MLP** | Go-to-market enfocado en retail/logística/verticales "enterprise" no regulados. Consecuencia de la decisión 1: la restricción ZDR/HIPAA BAA de Managed Agents ni siquiera aplica en el MLP. | La Sección 12.3 ya cubre el compliance de banca para cuando se entre a ese vertical. |
| 7 | **Motor de Acciones: Slack + Telegram + Correo por defecto; WhatsApp opt-in con costo pass-through** | Cero costo marginal en los tres canales por defecto (Sección 12.10). WhatsApp disponible desde el día 1 si el cliente lo quiere, con el costo de Meta reflejado explícitamente en su factura, no absorbido en el COGS. | — (ya es MLP día 1, solo con la etiqueta de costo correcta) |
| 8 | **Plantillas de SOP de Compliance en el Motor de Acciones** | Mismo motor de reglas-por-umbral ya planeado para colas (Sección 12.10) — se agregan plantillas: personal no presente en zona de caja, apertura/cierre fuera de horario, cliente sin atender. No es una capacidad nueva, son más reglas sobre la infraestructura ya construida. | Plantillas adicionales por vertical se agregan igual, sin tocar el motor. |
| 9 | **Zona de Exclusión de Personal sí; Demografía (edad/género) no** | Se agrega un tipo de zona `staff_area` que se excluye del conteo de clientes (Sección 6.1) — bajo costo, alto valor de precisión. Demografía queda deliberadamente fuera: más sensible que detectar `person`, y Zero Biometrics es ventaja de privacidad frente a Agrex.ai, no limitación (ver Sección 3, "Fuera de Alcance"). | Demografía se evalúa caso por caso si un cliente específico la pide bajo su propio consentimiento, nunca por defecto. |
| 10 | **MFA en el login** | Viene de fábrica con Supabase Auth — es configuración, no desarrollo. Se incluye en el MLP sin mover el estimado de tiempo (Sección 7). | — |
| 11 | **Onboarding/offboarding de Tenants: máquina de estados simple** | Auto-registro → `status='onboarding'` → aprobación de un clic del SuperAdmin → `status='active'` (Sección 5, Flujo 1 variante MLP). Baja: `status='inactive'` dispara retención + revocación de tokens (mecanismo de la decisión 5). | Quitar el paso de aprobación manual para hacerlo 100% self-service es borrar un solo paso del flujo, no rediseñarlo. |
| 12 | **Hosting: Supabase + Cloudflare R2 + Render/Cloud Run + GitHub** | Ninguno de los tres tiene reloj de expiración para cuentas nuevas en 2026 — a diferencia de AWS (cuenta nueva se cierra a los 6 meses salvo upgrade a plan pagado, aunque conserva ~30 servicios "always-free" que no expiran) y GCP (crédito de $300 válido 90 días) — verificado contra documentación oficial de ambos proveedores (Sección 7). Todo el almacenamiento de objetos (snapshots + Model Registry) se unifica en Cloudflare R2 (API compatible con S3). | AWS/RDS quedan documentados como ruta de escalamiento (Sección 7) para cuando el volumen de Fase 4+ lo justifique — es una migración de proveedor de infraestructura equivalente (misma API S3), no un rediseño de arquitectura. |

**Estimado de tiempo del MLP recortado (detalle y justificación en Sección 13):**

| Fase | Antes del recorte (v3.3) | Después (v3.4, MLP recortado) |
| --- | --- | --- |
| Fase 1 (esquema + RLS + Edge Gateway + auth) | 2-4 semanas | **2-3 semanas** |
| Fase 2 (Backoffice + Partners + dashboards) | 3-6 semanas | **3-5 semanas** |
| Fase 3 (Operación Interna + Motor de Acciones + Copiloto/auditoría) | 5-9 semanas | **3-5 semanas** |
| **Total MLP** | 10-19 semanas | **8-13 semanas** |

La reducción más grande viene de sacar toda la maquinaria de Managed Agents
(sesiones, patrón de artefactos, evaluación) de la Fase 3 — no de recortar ningún
feature visible para el cliente.

---

### 4. Usuarios y Roles (IAM - Identity and Access Management)

El modelo de identidad tiene **dos niveles contractuales de tenancy** — el Asset
Owner (tenant maestro, cliente contractual directo) y, opcionalmente, uno o más
Partners (sub-tenants) que el propio Asset Owner da de alta dentro de su cuenta —
sobre los que el **aislamiento de datos opera en tres niveles**: `tenant → site →
partner` (un usuario regional puede acotarse a sucursales específicas dentro del
tenant, además del corte tenant/partner). La implementación completa de ese
aislamiento de tres niveles vía RLS está en la Sección 8.3.

| Rol | Nivel | Descripción | Permisos Clave |
| --- | --- | --- | --- |
| **SuperAdmin (Plataforma)** | Plataforma | Administrador central del sistema SaaS. No es un registro de la tabla `users` (ver Sección 8.5) — es acceso interno de la plataforma. | Crear Asset Owners (tenants maestros) y Resellers. Asignar el `vertical_type` de cada cliente. Registrar IDs de Edge Gateways. Mapear polígonos (zonas/ROIs) sobre fotogramas de cámaras. Gestionar flota (actualizaciones OTA de código y de modelos). Publicar nuevos checkpoints en el Model Registry. Único rol con acceso *break-glass* auditado cross-tenant. |
| **Reseller Admin (Distribuidor/Canal)** *(fuera del MLP, diferido a v2.0 — ver Sección 3.1, decisión 2)* | Reseller | Socio de canal que onboardea y da soporte comercial a una cartera de Asset Owners. Rol y tabla completos y validados en este documento, pero **inertes hasta v2.0** — ningún caso de uso del MLP lo requiere. | Ve metadata de gestión (nombre, estado, sedes) de los Tenants bajo su `reseller_id`. **No ve telemetría ni tableros operativos de esos Tenants por defecto** — mismo principio de mínimo privilegio que un Partner; el Asset Owner tendría que habilitárselo explícitamente si en el futuro se decide lo contrario. Puede iniciar el alta de un nuevo Tenant en su cartera, sujeto a aprobación del SuperAdmin. |
| **Tenant Admin (Asset Owner / Cliente Maestro)** | Tenant | Gerente de Operaciones, TI o Seguridad del dueño de la infraestructura (supermercado, banco, bodega, centro comercial). | Visualizar tráfico, colas, ocupación y mapas de calor de **toda** su infraestructura (todas sus sucursales). Acceso completo al Copiloto sobre sus propios datos. **Backoffice de Usuarios:** crear usuarios `operator`/`viewer` y asignarles una o varias sucursales específicas (ver Sección 8.2). **Módulo de Reventa:** crear, editar, desactivar Partners; asignar o revocar el acceso de cada Partner a zonas (ROIs) específicas, a nivel de sucursal completa o de zona individual. |
| **Tenant Operator/Viewer Regional** *(nuevo)* | Tenant, acotado | Gerente o analista de una o varias sucursales específicas, sin visibilidad del resto de la cadena. | Visualiza tráfico, colas y mapas de calor **únicamente de las sucursales que el Tenant Admin le asignó** vía `user_site_assignments` (Sección 8.2). `operator` puede además ajustar configuración operativa de sus sucursales asignadas; `viewer` es de solo lectura. |
| **Partner Admin (Sub-Tenant / Socio Comercial)** | Sub-Tenant | Gerente de Trade Marketing, Category Manager, o equivalente del socio comercial que opera dentro del espacio del Asset Owner (ej. Nestlé dentro de La Torre; una aseguradora dentro de una sucursal bancaria). Es dado de alta **por el Asset Owner**, nunca directamente por el SuperAdmin. | Visualizar **únicamente** los datos de las zonas (ROIs) que el Asset Owner le asignó explícitamente — puede ser una sucursal completa o zonas puntuales dentro de ella (Sección 8.3). Acceso al Copiloto acotado a ese mismo alcance. No puede ver datos operativos internos del Asset Owner ni de otros Partners. |
| **Viewer (Analista)** | Tenant, Sub-Tenant o Reseller | Usuario de solo lectura, existe en cualquiera de los tres niveles. | Consultar y exportar reportes en PDF/CSV dentro del alcance de su nivel. Sin permisos de configuración ni de gestión de Partners/usuarios. |
| **Service Account (Edge Gateway)** | Sistema | Sistema físico en sucursal/bodega. | **Para el MLP (v3.4):** autenticación por **access token (24h) + refresh token (90 días)** (Sección 8.7) para publicar telemetría y para solicitar al Model Manager la descarga del modelo del vertical asignado. Revocable server-side: `edge_gateways.status='revoked'` bloquea el siguiente refresh, ventana máxima de exposición 24h. El mecanismo de **certificado cliente mTLS** (también en Sección 8.7, escrito y validado en v3.3) queda como gancho para cuando un vertical o cliente lo exija contractualmente — no se descarta, se activa sin rediseño. |

**Regla de aislamiento explícita (ampliada en v3.0):** ningún rol por debajo del
SuperAdmin tiene visibilidad fuera de su alcance asignado — ni siquiera por omisión.
Concretamente: (a) un Partner Admin nunca ve datos operativos internos del Asset
Owner que no correspondan a una zona compartida, ni datos de otro Partner del mismo
Asset Owner; (b) un Tenant Operator/Viewer Regional nunca ve sucursales fuera de su
asignación, aunque pertenezcan al mismo tenant; (c) un Reseller Admin nunca ve
telemetría de sus Tenants por defecto; (d) nadie ve la existencia de Asset Owners,
Partners o Resellers ajenos a su propia jerarquía. La implementación completa de
esta regla vía Row-Level Security está en la Sección 8.

**MFA en el login (nuevo, v3.4 — Sección 3.1, decisión 10):** autenticación
multifactor viene de fábrica con Supabase Auth para todos los roles — es
configuración a nivel de proyecto (política de MFA obligatoria u opcional por rol),
no desarrollo. Se incluye en el MLP sin mover el estimado de tiempo de la Sección 7.

#### 4.1 Vista Restringida del Partner en el Frontend (nueva, v3.4)

La Sección 8.3 (RLS) ya garantiza que un Partner **nunca puede leer** datos fuera de
su alcance a nivel de base de datos, aunque alguien manipulara la UI o hiciera
llamadas directas a la API. Lo que no estaba enumerado en versiones anteriores es
qué **pantallas se renderizan** para cada rol de Partner en el frontend — una
decisión de producto encima de esa garantía de seguridad, no un mecanismo de
seguridad en sí mismo. Matriz explícita para el MLP:

| Pantalla / Módulo | Partner Admin | Partner Viewer |
| --- | --- | --- |
| Dwell Time / heatmap de sus zonas asignadas | ✅ | ✅ |
| Copiloto (acotado a su alcance, Sección 12.4) | ✅ | ✅ |
| Exportar reportes PDF/CSV | ✅ | ✅ |
| Módulo de Reventa (gestionar otros Partners) | ❌ | ❌ |
| Backoffice de Usuarios del Tenant | ❌ | ❌ |
| Configuración del Motor de Acciones (Sección 12.10) | ❌ | ❌ |
| Fleet / Edge Gateway, Model Registry | ❌ | ❌ |
| Facturación | ❌ | ❌ |

Un Partner Admin difiere de un Partner Viewer únicamente en permisos de escritura
*dentro* de su propio alcance (ej. configurar alertas de sus zonas si el negocio lo
habilita más adelante) — ninguno de los dos accede a las filas marcadas ❌, ni
siquiera en modo lectura, porque son módulos de gestión del Asset Owner, no de
consumo de datos.

---

### 5. User Flows y Customer Journeys

#### Flujo 1: Onboarding e Instalación de Infraestructura (Edge Deploy)

1. **Comercial/Contractual:** se firma el contrato con el **Asset Owner** (no con
   ninguna marca ni socio comercial). El SuperAdmin crea el tenant maestro y, como
   parte del alta, **asigna el vertical de industria** (retail, banca, logística,
   etc.) que determinará qué modelo YOLO usará ese cliente.
2. **Físico / Infraestructura:** se audita el equipo existente en la administración
   de la sede (ej. PC Windows del gerente o servidor local). Si no cumple los
   requisitos mínimos, se despliega el equipo de leasing tercerizado.
3. **Sistema:** se instala el Edge Gateway (vía Docker Desktop/Engine o binario
   empaquetado). El servicio arranca en segundo plano como daemon de sistema.
4. **Configuración de Credenciales:** el SuperAdmin genera un código de activación de
   un solo uso desde el portal, que se ingresa manualmente durante la instalación del
   Edge Gateway para vincularlo con la sede correspondiente, inyectando remotamente
   las URL RTSP y el `vertical_type` asignado. **Para el MLP (v3.4):** el canje del
   código emite un **access token (24h) + refresh token (90 días)** — no un
   certificado mTLS (Sección 8.7, decisión 5 de la Sección 3.1); el Edge Gateway
   renueva proactivamente antes de expirar, y la revocación (`edge_gateways.
   status='revoked'`) bloquea el siguiente refresh con ventana máxima de exposición
   de 24h.
5. **Descarga del Modelo (nuevo):** el Edge Gateway, al validar sus credenciales,
   consulta al Model Manager en la nube qué checkpoint corresponde a su vertical,
   descarga el archivo `.pt` correspondiente (ej. `yolo_retail.pt`) con reanudación
   por `Range` si la conexión se corta (Sección 9.1), verifica su checksum, y lo
   carga en memoria. Solo este modelo permanece cargado.
6. **Validación:** el Edge Gateway verifica la conexión RTSP, inicia los hilos de
   inferencia con el modelo correcto ya cargado, y envía un latido (Heartbeat) de
   estado "Online" a la nube.

**Variante MLP — onboarding self-service del Tenant (nuevo, v3.4, Sección 3.1
decisión 11):** el paso 1 admite una máquina de estados más ligera que "el
SuperAdmin crea el tenant manualmente" — un Asset Owner puede **auto-registrarse**
desde un formulario público, creando su fila en `tenants` directamente con
`status='onboarding'`. El SuperAdmin revisa y aprueba con **un clic** (confirma
plan comercial y `vertical_type`), pasando el tenant a `status='active'` — recién
ahí arranca el resto del Flujo 1 (pasos 2-6). La baja de un Tenant es simétrica:
pasar a `status='inactive'` dispara la política de retención de la Sección 8.5 y
la revocación de tokens del Edge Gateway (mecanismo de la decisión 5 arriba) — el
mismo camino de purga que ya usa el offboarding de Partner (Sección 12.12), ahora
aplicado a nivel de Tenant. **Gancho de evolución:** quitar el clic de aprobación
del SuperAdmin para hacerlo 100% self-service es eliminar un solo paso de la
máquina de estados, no rediseñarla.

#### Flujo 2: Mapeo Espacial de la Sede (Polígonos/ROIs)

1. **Captura:** el SuperAdmin (o el Asset Owner Admin, si se le habilita el permiso)
   solicita un "Snapshot de Calibración" a la cámara 1.
2. **Interfaz:** el portal renderiza la imagen. Se utiliza la herramienta de dibujo
   poligonal (clics) para trazar el contorno de la zona de interés (ej. la Góndola de
   Lácteos en retail, o una ventanilla de atención en banca).
3. **Etiquetado:** se asigna metadata: `ID: roi_lacteos_01`, `owner_type: TENANT`
   (por defecto, propiedad del Asset Owner), `Type: shelf`. El ROI **no** tiene
   dueño de Partner hasta que el Asset Owner decida compartirlo (ver Flujo 3).
4. **Guardado:** el portal actualiza el JSON de la sede en la base de datos cloud
   para que el Controlador Matemático comience a evaluar las intersecciones.

#### Flujo 3: Módulo de Reventa — El Asset Owner Provisiona a un Partner (nuevo;
reescrito v3.4 — alta/baja en un solo paso, Sección 3.1 decisión 3/2.1)

**Alta en un solo paso (v3.4):** versiones anteriores describían un asistente de
varios pasos (ingresar, crear Partner, asignar alcance, invitar, como pasos
separados de UI). La revisión de alcance confirmó que esto no necesita ser un
wizard — el Asset Owner Admin llena **un solo formulario** (nombre del Partner,
correo de contacto, qué sedes/zonas comparte) y **una sola acción** ejecuta las
tres operaciones de forma atómica:

1. **Formulario único:** el Asset Owner Admin, desde la sección "Partners" de su
   portal, llena nombre, correo de invitación, y selecciona de la lista de zonas de
   sus propias sedes cuáles quedan visibles para ese Partner (ej. únicamente las
   zonas etiquetadas como góndolas de lácteos en las 12 tiendas donde Nestlé tiene
   presencia).
2. **Ejecución atómica:** al enviar, el sistema en una sola transacción (a) crea la
   fila en `partners`, (b) reasigna el `owner_type`/`owner_partner_id` de las zonas
   seleccionadas al Partner recién creado — sin afectar la visibilidad que el
   propio Asset Owner tiene sobre esas mismas zonas, que conserva siempre (Sección
   8.3) —, y (c) envía la invitación con credenciales propias y el rol
   `Partner Admin`, acotado exactamente a lo seleccionado en el paso 1.
3. **Acceso por tiempo limitado (nuevo, v3.4 — Sección 3.1 decisión 3/2.2):** el
   mismo formulario permite fijar opcionalmente una fecha de expiración del acceso
   (`partners.access_expires_at`, Sección 8.0). Si se deja en blanco, el acceso es
   indefinido — el Asset Owner puede optar por eso libremente. Si se define, un job
   programado (misma cadencia batch del Motor Matemático, Sección 6) revisa
   diariamente: si `access_expires_at < now()` y `partners.status = 'active'`,
   ejecuta el **mismo camino de revocación del offboarding manual** (Sección
   12.12) — no es un mecanismo nuevo, es el offboarding ya construido, disparado
   por fecha en vez de por acción manual del Asset Owner. Útil para activaciones de
   marca por temporada (ej. una promoción de fin de año con un Partner puntual).
4. **Gestión continua:** el Asset Owner puede revocar o ampliar el acceso de un
   Partner en cualquier momento (incluyendo mover o quitar `access_expires_at`); el
   cambio se refleja de inmediato en lo que ese Partner puede consultar.

#### Flujo 4: Consumo Diario del Partner (ex-Marca / Trade Marketing)

1. **Ingreso:** el Partner Admin (ej. el Trade Manager de Nestlé) inicia sesión con
   las credenciales que le dio su Asset Owner.
2. **Filtrado automático:** el sistema muestra únicamente los ROIs cuyo `owner_id`
   corresponde a ese Partner — el filtrado ocurre en el mismo nivel de datos, no es
   una capa de UI que se pueda burlar cambiando parámetros.
3. **Visualización:** el usuario selecciona "Últimos 7 días". Observa que el *Dwell
   Time* en la góndola cayó de 45 a 10 segundos.
4. **Interacción Cognitiva:** el usuario hace clic en "Consultar a la IA". Claude
   solicita el snapshot más reciente (dentro del alcance permitido a ese Partner),
   analiza la imagen, nota estantes vacíos y redacta: *"La caída en el tiempo de
   permanencia concuerda con un quiebre de stock detectado en el nivel 2. Sugiero
   enviar a reponedor."*

#### Flujo 5: Consumo Operacional del Asset Owner (nuevo)

1. **Ingreso:** el Tenant Admin (Asset Owner) inicia sesión y ve el tablero
   operativo global — no filtrado por ningún Partner — con tráfico, colas y mapas de
   calor de todas sus sedes.
2. **Uso interno:** por ejemplo, un gerente de operaciones bancarias identifica que
   una sucursal tiene tiempos de espera elevados en ciertas horas y reasigna personal
   de caja; o un gerente de bodega identifica cuellos de botella en pasillos de
   picking.
3. **Valor dual:** este mismo tablero es la base sobre la cual el Asset Owner decide
   qué ROIs le conviene compartir en el Flujo 3 — la capa operativa y la capa de
   reventa comparten la misma fuente de datos, sin duplicar infraestructura.

#### Flujo 6: Referido de Tenant por un Reseller (nuevo, v3.3 — fuera del MLP,
diferido a v2.0 según Sección 3.1 decisión 2)

Cierra el ciclo de vida comercial del rol Reseller Admin, ya definido en la Sección
4. **Este flujo queda completo y validado en el documento pero inerte para el MLP**
— ningún caso de uso del lanzamiento lo requiere; se activa sin rediseño cuando
exista el primer acuerdo de canal real.

1. **Referido:** el Reseller Admin, desde su portal, inicia el alta de un nuevo
   Tenant en su cartera (nombre, contacto, vertical propuesto). El sistema crea la
   fila en `tenants` con `status='onboarding'` y `reseller_id` ya asignado a ese
   reseller — la escritura corre por el canal de aprovisionamiento, no da al
   reseller acceso a telemetría.
2. **Aprobación:** el referido queda pendiente de aprobación del SuperAdmin, que
   confirma el contrato, asigna/valida el vertical definitivo y pasa el tenant a
   `status='active'`. Solo entonces arranca el Flujo 1 (onboarding e instalación).
3. **Visibilidad acotada del Reseller:** a partir del alta, el Reseller Admin ve
   **metadata de gestión** de sus Tenants (nombre, estado, número de sedes) vía el
   RLS de `tenants` scoped por `reseller_id` (Sección 8.3) — **nunca** telemetría ni
   tableros operativos, mismo principio de mínimo privilegio que un Partner.
4. **Sin liquidación en la plataforma:** la comisión del Reseller sobre esos Tenants
   es un acuerdo externo (ver exclusión de alcance en la Sección 3). La plataforma
   provee la *atribución* (qué Tenants están bajo qué Reseller), no el cobro.

#### Flujo 7: Reemplazo de Hardware / DR del Edge Gateway (nuevo, v3.3)

Escenario real y frecuente en CENAM: la computadora prestada (BYOD) o el Mac Mini de
leasing que corre el Edge Gateway se daña, se roba, o se reemplaza. Sin un flujo
definido, el riesgo es duplicar `site`/`cameras` o perder la trazabilidad de qué
hardware sirvió a qué sede.

1. **Alta de reemplazo:** el SuperAdmin genera un código de activación de un solo
   uso **marcado como "reemplazo de `edge_id = X`"**. Este código reutiliza el
   `site_id` y las filas de `cameras` existentes — no crea sedes ni cámaras nuevas.
2. **Instalación:** se instala el Edge Gateway en el hardware nuevo y se canjea el
   código (mismo mecanismo del Flujo 1, paso 4). El nuevo gateway obtiene su propio
   certificado mTLS (Sección 8.7) y descarga el modelo del vertical ya asignado a
   esa sede.
3. **Trazabilidad y garantía:** la nueva fila de `edge_gateways` referencia a la
   anterior vía `replaced_edge_gateway_id` (FK a sí misma). El registro viejo pasa a
   `status='decommissioned'` y su certificado se **revoca** (Sección 8.7) — un
   gateway dado de baja no puede reconectarse aunque su certificado siga
   criptográficamente vigente.
4. **Continuidad de datos:** la telemetría histórica de la sede vive en la nube
   (particionada por `site`/`camera`, no por `edge_id`), así que el reemplazo del
   hardware no pierde ni un dato del histórico — solo se reanuda el flujo de
   ingesta desde el gateway nuevo.

Columnas nuevas en `edge_gateways` para soportar Flujos 7 y la Sección 8.7
(`replaced_edge_gateway_id`, ampliación del enum `status`, más
`refresh_token_hash`/`refresh_token_expires_at` para el mecanismo del MLP en
8.7.0, o `cert_serial`/`cert_expires_at` si se activa mTLS en 8.7.1): ver el DDL
completo en la Sección 8.7.

---

### 6. Arquitectura de Alto Nivel

```text
=============================================================================
  CAPA 1: EDGE (NODO EN LA COMPUTADORA EXISTENTE DEL CLIENTE)
=============================================================================
[Cámaras CCTV (Análogas/IP)] ──(RTSP)──► [DVR/NVR Local]
                                              │ (Red LAN)
                                              ▼
[ Computadora de Tienda/Sucursal/Bodega — Edge Gateway (Docker/Daemon) ]
  ├─ Decodificador de Video (Opencv / FFmpeg - Downsampling a 3-10 FPS)
  ├─ Model Manager (*NUEVO*)
  │    └─ Resuelve vertical_type asignado → descarga/cachea el checkpoint
  │       correspondiente desde el Model Registry cloud (ej. yolo_retail.pt) →
  │       verifica checksum SHA256 → carga en memoria SOLO ese modelo
  ├─ Motor de Inferencia (YOLOv8n CPU-Optimized o GPU si está disponible,
  │    usando el checkpoint resuelto por el Model Manager)
  ├─ Algoritmo de Tracking (ByteTrack - agnóstico al vertical, opera sobre
  │    bounding boxes sin importar qué checkpoint los generó)
  ├─ Anonimizador (Convierte Bounding Box a Vector Base XY)
  ├─ Cola Local Persistente (SQLite - Mecanismo Offline-Sync)
  └─ Agente Emisor (Envía JSON vía HTTPS a la nube)
                                              │
          ┌───────────────────────────────────┘
          ▼
=============================================================================
  CAPA 2: INFRAESTRUCTURA CLOUD Y CONTROLADOR (BACKEND)
=============================================================================
[ API Gateway / Balanceador de Carga ]
          │
          ├─────────────────────────────────────────┬─────────────────────┐
          ▼                                           ▼                     ▼
[ Controlador de Negocio ]                [ Almacenamiento ]     [ Model Registry (*NUEVO*) ]
  ├─ Motor Matemático (*)             ├─ DB Relacional (esquema  ├─ S3 versionado con los
  ├─ Calculador de Dwell Time         │  físico completo en la   │  checkpoints .pt por
  ├─ Gestor de Eventos/Webhooks       │  Sección 8: resellers →  │  vertical (retail,
  ├─ Módulo de Reventa (*NUEVO*)      │  tenants → sites →       │  banking, logistics...)
  ├─ Backoffice de Usuarios (*NUEVO*) │  cameras → zones; users, ├─ API de manifiesto/
  │    └─ CRUD de Partners, asignación│  user_site_assignments,  │  distribución con
  │       de zonas a owner_type=      │  partners — todo con RLS │  checksum firmado
  │       PARTNER; asignación de      │  de 3 niveles:           │
  │       sedes a usuarios operator/  │  tenant→site→partner)    │
  │       viewer regionales           └─ Time-Series             │
  │                                      (tracking_coordinates,   │
  │                                      PostgreSQL nativo +      │
  │                                      pg_partman — ver 8.6)    │
          │                                         ▲             └──────────┬──────────┘
          ▼                                         │                        │
[ Capa Agéntica (Enjambre Claude) ] ──────────────────┘                        │
  └─ Microservicios que consumen la Time-Series DB (con el mismo filtrado por  │
     tenant/partner que aplica al resto del sistema), solicitan snapshots al  │
     API Gateway y envían Prompts a la API de Anthropic (Claude).             │
                                                                                │
  El Edge Gateway consulta el Model Registry directamente vía HTTPS ──────────┘
  para resolver y descargar su checkpoint vertical (no pasa por el Controlador
  de Negocio; es un canal de distribución de artefactos, no de telemetría).

```

***(\*) Nota Explícita sobre el Motor Matemático (Batch vs. Streaming):** el Motor
Matemático (evaluación de intersecciones ROI) opera en modo **batch/polling** (ej.
ejecutándose cada 1 a 5 minutos sobre los datos recién ingresados en la Time-Series
DB), NO en streaming en tiempo real. Justificación: para un producto de analítica de
tendencias, una latencia de minutos en el tablero es totalmente aceptable y evita la
inmensa complejidad operativa de introducir infraestructura de streaming (Kafka,
Redis Streams, etc.) que no aporta valor comercial en esta etapa. Esto se puede
migrar a streaming en una fase futura si el negocio lo justifica, pero no es parte
del MLP.*

#### 6.1 Profundidad Algorítmica: Tracking y Re-identificación (ReID)

YOLO por sí solo no sabe si la persona en el frame 1 es la misma del frame 2. Para
calcular el *Dwell Time*, requerimos un algoritmo de Tracking Multi-Objeto (MOT).

* **Selección de Algoritmo:** utilizaremos **ByteTrack**. A diferencia de DeepSORT
  (que extrae un vector de características visuales y consume muchísima CPU/GPU),
  ByteTrack es puramente cinemático. Utiliza las cajas delimitadoras de YOLO y asocia
  objetos entre frames basándose en el movimiento y superposición espacial (Filtro de
  Kalman). Esto permite ejecutar el tracker en computadoras de oficina estándar sin
  saturar el procesador.
* **Independencia del Vertical (nuevo):** dado que ByteTrack opera únicamente sobre
  las coordenadas de las cajas delimitadoras que YOLO produce —sin importar si esas
  cajas provienen de `yolo_retail.pt` o `yolo_banking.pt`— **no existe una variante
  de ByteTrack por industria**. El Motor Base Multi-Vertical solo intercambia la capa
  de detección; el resto del pipeline (tracking, anonimización, cola, envío) es
  código único y compartido entre todos los verticales.
* **Ciclo de Vida del `person_id`:** ByteTrack asigna un ID temporal (ej.
  `ID_4022`). Si la persona es ocluida temporalmente (ej. pasa detrás de un pilar)
  por menos de 30 frames, el Filtro de Kalman predice su trayectoria y mantiene el
  ID.
* **Límites de ReID:** si la persona sale completamente de la cámara y vuelve a
  entrar minutos después, ByteTrack le asignará un nuevo ID. Esto es aceptable, ya
  que las métricas de *Dwell Time* se calculan por "sesión de permanencia frente al
  ROI", no rastreando el journey completo por toda la instalación.
* **Zona de Exclusión de Personal (nuevo, v3.4 — Sección 3.1, decisión 9):** una
  zona puede etiquetarse con `zone_type = 'staff_area'` (convención de valor sobre
  la columna ya existente `zones.zone_type`, sin migración de esquema — es texto
  libre por diseño, Sección 8.0) para marcar espacios donde solo debe operar
  personal (detrás de mostrador, bodega interna, caseta de seguridad). El Motor
  Matemático **excluye del conteo de clientes** cualquier detección cuya zona activa
  sea `staff_area` al calcular tráfico/dwell time agregado — sin esto, el personal
  que pasa horas frente a una cámara infla artificialmente las métricas de
  ocupación y sesga el Copiloto. Es una exclusión de conteo, no una zona de
  identificación de personal: sigue sin capturarse ningún dato biométrico ahí; solo
  cambia si esa detección de `person` cuenta como "cliente" en los agregados. La
  misma zona sirve además como base de la plantilla SOP "personal no presente en
  zona de caja" (Sección 12.10).

---

### 7. Infraestructura y Stack Tecnológico

Las elecciones tecnológicas priorizan el rendimiento en arquitecturas heterogéneas
(computadoras viejas vs nuevas) y la capacidad de intercambiar el modelo de detección
sin tocar el resto del stack.

* **Edge Hardware (El Nodo Local):**
* *Opción Default (BYOD):* computadora existente del cliente (Windows/Linux, x86_64).
* *Requisitos Mínimos:* Procesador Intel Core i3 (8va gen) / AMD Ryzen 3, 8GB RAM.
* *Opción Leasing (Fallback):* Mac Mini M2.

* **Edge Software:** `Python 3.11`, `YOLOv8 (Ultralytics)`, `ByteTrack`. Empaquetado
  en `Docker`.
  * *Gestión de Recursos:* si el instalador no detecta GPU (CUDA) ni NPU (Apple
    Silicon), el sistema carga automáticamente la variante **YOLOv8n (Nano)** o
    utiliza modelos compilados con `OpenVINO` optimizados para CPU Intel. El
    framerate se limitará dinámicamente a 3-5 FPS, lo cual es suficiente para
    capturar métricas de Dwell Time.
  * *Model Manager (nuevo):* módulo responsable de resolver el `vertical_type` del
    Edge Gateway, descargar el checkpoint correspondiente desde el Model Registry,
    verificar su checksum, y mantenerlo cacheado en disco local. **Los checkpoints
    de los demás verticales nunca se descargan ni se cargan en memoria** en un
    Edge Gateway dado — este es el mecanismo concreto que evita "contaminar" el
    código y ahorra RAM en modalidad BYOD, en contraste con la alternativa
    descartada de empaquetar todos los modelos dentro de la misma imagen Docker.
  * Si la descarga del modelo falla (ej. corte de internet durante una
    actualización), el Model Manager conserva el último checkpoint válido en caché
    y continúa operando con él hasta que la descarga se complete exitosamente.

* **Cloud Backend:** `Node.js (NestJS)` o `Python (FastAPI)`.
* **Base de Datos Principal:** `PostgreSQL` (16/17) con **particionamiento
  declarativo nativo + `pg_partman`** para la capa time-series (Sección 8.6). *Nota
  de portabilidad (v3.3):* versiones anteriores usaban `TimescaleDB`, que quedó
  **deprecado para proyectos nuevos de Supabase** — el destino de hosting de bajo
  costo/fallback del proyecto. El esquema ahora corre sin cambios sobre Supabase
  free tier (Postgres 17), RDS o Postgres local, usando solo extensiones
  disponibles en las tres.
* **Model Registry (nuevo):** bucket de object storage versionado (Cloudflare R2
  para el MLP — API compatible con S3, ver nota de Cloud Hosting abajo), con una API
  ligera de manifiesto (`GET /v1/models/{vertical_type}/manifest`) que devuelve la
  versión más reciente del checkpoint, su URL de descarga firmada y su checksum
  SHA256. La descarga soporta reanudación por `Range` y re-pedido de manifiesto ante
  expiración de URL firmada (Sección 9.1).
* **Motor Cognitivo:** `API de Anthropic (Claude)`. **Nota de vigencia
  (verificada 2026-07):** Claude 3.5 Sonnet — el modelo citado en versiones
  anteriores de este documento — fue **retirado por Anthropic en octubre 2025** y
  devuelve error 404. La estrategia de modelos vigente es por carga de trabajo:
  **Claude Haiku 4.5** ($1/$5 por MTok) para el Copiloto conversacional de baja
  latencia; **Claude Sonnet** (Sonnet 4.6 a $3/$15, o Sonnet 5 a $2/$10
  introductorio hasta 2026-08-31) para auditorías visuales y el Enjambre; **Batch
  API** (50% de descuento) para cargas nocturnas no interactivas que no requieran
  el sandbox de Managed Agents. Detalle completo y justificación de costos en la
  Sección 12.5. El código debe referenciar modelos vía configuración (no
  hardcodeados) para absorber futuros reemplazos sin release.
* **Cloud Hosting (reescrito v3.4 — Sección 3.1, decisión 12):** para el MLP,
  **Supabase (Postgres gestionado + Auth + MFA) + Cloudflare R2 (object storage,
  API compatible con S3) + Render/Cloud Run (backend) + GitHub (código/CI)**. El
  mismo bucket R2 que almacena snapshots de auditoría también aloja el Model
  Registry, en un bucket/prefijo separado con políticas de acceso propias.
  **Justificación (verificado contra documentación oficial de cada proveedor,
  2026-07):** una cuenta nueva de **AWS** recibe hasta $200 en créditos pero la
  cuenta **se cierra a los 6 meses** salvo que se convierta a plan pagado (más de
  30 servicios "always-free" no expiran, pero eso no evita el cierre de cuenta); una
  cuenta nueva de **GCP** recibe $300 válidos solo **90 días**. Ninguno de los dos
  sostiene una cuenta nueva de forma indefinida sin conversión a facturación activa
  desde el día uno — Supabase/Cloudflare R2/Render/Cloud Run/GitHub sí lo hacen en
  sus respectivos free tiers, sin ese reloj de expiración. **AWS/RDS quedan como
  ruta de escalamiento documentada** para Fase 4+ cuando el volumen lo justifique —
  es una migración de proveedor sobre una API equivalente (S3), no un rediseño de
  arquitectura (ver tabla Build-vs-Buy, Sección 7.3).

#### 7.1 Gestión de Flota (Fleet Management) y Actualizaciones

Administrar cientos de Edge Gateways de forma manual es inviable. Con el Motor
Multi-Vertical, **hay dos tipos de actualización independientes** que la flota debe
soportar: actualización de **código** (la imagen Docker del Edge Gateway) y
actualización de **modelo** (un nuevo checkpoint `.pt` para un vertical dado).

* **Mecanismo OTA (Over-The-Air):** **Portainer Community Edition** (self-hosted,
  gratis, sin límite de dispositivos de un tercero — decisión Build-vs-Buy de la
  Sección 7.3) para el MLP. BalenaOS o un cliente ligero de AWS IoT Greengrass
  quedan como alternativas si el volumen de flota en Fase 4+ lo justifica.
* **Actualización de Modelo (nuevo):** cuando el SuperAdmin publica una nueva versión
  de `yolo_retail.pt` en el Model Registry, los Edge Gateways de vertical retail la
  detectan en su próximo chequeo de manifiesto y la descargan de forma independiente
  al ciclo de release de código — esto permite mejorar la precisión de detección de
  un vertical sin forzar un despliegue completo de la aplicación.
* **Heartbeat y Telemetría del Sistema:** el Edge envía cada minuto métricas de
  salud: uso de CPU/RAM, temperatura, estado del contenedor, y ahora también la
  versión del modelo cargado actualmente.
* **Rollback Automático:** si se empuja una actualización (de código o de modelo) y
  el contenedor falla, entra en *crash loop*, o el nuevo checkpoint no supera un
  chequeo de sanidad básico al cargar, el agente local detecta la falla y restaura
  la versión anterior (Blue/Green deployment local), tanto para código como para
  modelo.

#### 7.2 Escalabilidad Local (Múltiples Cámaras)

Un supermercado puede tener entre 15 y 30 cámaras; una sucursal bancaria u bodega
puede tener una distribución distinta pero el mismo principio aplica.

* *Límite del Hardware:* un procesador de ofimática (Core i5 sin GPU) puede procesar
  de 2 a 4 cámaras simultáneas a 3 FPS usando YOLO nano.
* *Nota de RAM Multi-Vertical (nuevo):* todas las cámaras de una misma sede
  pertenecen al mismo `vertical_type` — un Edge Gateway nunca necesita cargar más de
  un checkpoint de detección a la vez, sin importar cuántas cámaras procese. Esto es
  lo que garantiza que el modelo multi-vertical no penalice el consumo de RAM en
  hardware prestado: el costo de memoria es el de **un** modelo YOLOv8n Nano
  (~6-13 MB según cuantización), no el de N modelos simultáneos.
* *Estrategia de Escalamiento:* para 15-30 cámaras, el modelo de software en equipo
  prestado no será suficiente. El cliente **deberá** proveer un servidor dedicado con
  GPU (ej. NVIDIA T4/RTX) o autorizar el alquiler de un clúster pequeño (ej. 3 Mac
  Minis en red local balanceando la carga). El Edge Gateway está diseñado para
  instanciarse múltiples veces (Workers) dividiéndose las URLs RTSP — todos los
  Workers de una misma sede comparten el mismo modelo cacheado en disco local, para
  no re-descargarlo por cada Worker.

#### 7.3 Decisiones Build-vs-Buy (nueva, v3.3; tabla actualizada v3.4 — Sección 3.1)

Registro explícito de las decisiones de construir vs. adoptar, para que el equipo no
las re-litigue en cada sprint. El criterio transversal: **construir solo lo que es
diferenciador** (el aislamiento B2B2B de tres niveles y el Motor Base multi-vertical
lo son; casi nada más lo es en el MLP). Todo lo "buy" elegido tiene costo cero o casi
cero hasta tener volumen real, coherente con la sensibilidad de precio del mercado.

| Componente | Decisión | Motivo (una línea) | Trade-off aceptado |
| --- | --- | --- | --- |
| Orquestación/sandboxing de agentes | **Buy — Claude Managed Agents, pero diferido a Fase 4 (v3.4)** | No es diferenciador (lo es el aislamiento B2B2B); construirlo son meses de infra sin ventaja competitiva. El MLP usa **Messages API directa** (Sección 12.4) para Copiloto y auditorías — sin sandbox, sin el multiplicador 15x de tokens (Sección 3.1, decisión 1). | Ninguno para el cliente (recibe las mismas funcionalidades); Fase 4 activa la Sección 12 completa sin reescribirla. |
| Auth / Identity Provider + MFA | **Buy — Supabase Auth** | Gratis dentro del mismo proyecto de DB; se integra nativamente con el patrón de GUCs de la Sección 8.2. MFA viene de fábrica (Sección 3.1, decisión 10) — configuración, no desarrollo. | Acoplamiento a Supabase (mitigado: es solo IdP; el RLS es portable). |
| Base de datos / Time-Series | **Buy — Postgres nativo + `pg_partman` sobre Supabase free tier** | Decisión forzada por la deprecación de TimescaleDB en Supabase (Sección 8.6); portable a RDS y local. | Pérdida de compresión columnar automática (mitigado con tiering a Glacier, 8.6). |
| Object storage (snapshots + Model Registry) | **Buy — Cloudflare R2 (v3.4)** | API compatible con S3; free tier sin reloj de expiración de cuenta, a diferencia de AWS/GCP (verificado, Sección 7). | Migrar a S3/AWS en Fase 4+ es cambio de endpoint sobre API equivalente, no rediseño. |
| Backend / Compute | **Buy — Render o Cloud Run (v3.4)** | Free tier sin expiración de cuenta; despliegue continuo desde GitHub sin infraestructura propia que operar. | Límites de free tier bajo carga alta (re-evaluar al escalar a Fase 4+). |
| Canal WhatsApp (Motor de Acciones) | **Buy — Meta Cloud API directo, sin BSP** | Meta lo exige (no hay "build"); WhatsApp es el canal dominante en CENAM. **Opt-in con costo pass-through explícito (v3.4)** — Slack, Telegram y correo son el default sin costo marginal (Sección 12.10). | El costo de Meta se refleja en la factura del cliente, no se absorbe en el COGS. |
| Orquestador OTA de flota | **Buy — Portainer Community Edition** | Gratis, self-hosted, sin límite de dispositivos de un tercero que pueda cambiar de términos. | Operar el orquestador nosotros (aceptable: es infra estándar). |
| Observabilidad/monitoreo | **Buy — Grafana Cloud free tier** | Evita sobre-ingeniería de un stack Prometheus+Grafana propio antes de tener volumen que lo justifique. | Límites del free tier (re-evaluar al escalar). |
| Facturación al Asset Owner | **Buy — Stripe** | Sin costo fijo hasta la primera transacción; construir facturación propia es riesgo PCI innecesario. | Comisión por transacción de Stripe (aceptable vs. riesgo de cumplimiento). |
| Credenciales del Edge Gateway | **Buy/Build ligero — access + refresh token (MLP, v3.4)**; **CA interna mTLS diferida a Fase 4+** (Sección 8.7) | Sin PKI, sin diferencias de implementación entre Windows/Linux/Mac; revocación real en ≤24h basta para el MLP (Sección 3.1, decisión 5). La CA interna sigue siendo la decisión correcta cuando un vertical la exija contractualmente, pero no antes. | Ventana de exposición de hasta 24h tras revocar (vs. revocación inmediata de mTLS) — aceptable para el perfil de riesgo del MLP. |
| Aislamiento B2B2B (RLS 3 niveles) | **Build** | **Es el diferenciador central.** No hay "buy" que dé aislamiento tenant→site→partner garantizado en DB. | Complejidad de RLS (mitigada con la suite pgTAP como gate, Sección 8.4). |
| Motor Base multi-vertical (Edge Gateway) | **Build** | Diferenciador: un solo código, modelo intercambiable por vertical (Sección 6.1). | Ingeniería propia de visión/tracking (núcleo del producto). |

---

### 8. Modelo de Datos y Arquitectura Multi-Tenant (Esquema Físico Ejecutable)

Esta sección reemplaza el esquema conceptual de v2.0 con el **esquema físico
completo**, en DDL ejecutable de PostgreSQL (nativo, sin extensiones no disponibles
en Supabase — ver Sección 8.6). Es la referencia autoritativa
para arrancar coding — cualquier discrepancia entre esta sección y el resto del
documento (que usa nombres de producto en prosa, ej. "ROI", "sede") se resuelve a
favor de esta sección para efectos de implementación.

> **Convención de nombres:** el producto sigue hablando de "sedes" y "ROIs" en la
> prosa comercial y de producto (Secciones 1-7, 9-12); esta sección define que la
> tabla física detrás de "sede" es `sites` y la tabla física detrás de "ROI" es
> `zones`. `Store` y `ROI` (nombres de v2.0) quedan deprecados como nombres de tabla.

#### 8.0 Diagrama ER Completo y Extensiones Requeridas

```text
resellers (canal/distribuidor)
    │ 1
    │ N (reseller_id, nullable)
    ▼
tenants (Asset Owner — cliente maestro; vertical_type)
    │ 1                                  │ 1
    │ N                                  │ N
    ▼                                    ▼
sites (sucursales)                   partners (sub-tenants comerciales)
    │ 1                                  │
    │ N                                  │ owner_partner_id (opcional)
    ▼                                    │
cameras                                  │
    │ 1                                  │
    │ N                                  │
    ▼                                    │
zones (ROIs, polígonos) ◄────────────────┘  (owner_type: TENANT | PARTNER)
    │ 1                              │ 1
    │ N (agregación batch)           │ N
    ▼                                ▼
zone_dwell_sessions            tracking_coordinates (particionada RANGE por "time", vía camera_id)

users (tenant_id | reseller_id, + partner_id opcional; role: admin/operator/viewer)
    │ N
    │ N  (tabla puente)
    ▼
user_site_assignments (user_id, site_id)

model_registry_entries (catálogo de checkpoints .pt por vertical_type)
edge_gateways (site_id, vertical_type, current_model_version, status, channel)
platform_admins + break_glass_audit_log (acceso interno auditado, Sección 8.5)
```

Extensiones de PostgreSQL requeridas antes de correr el DDL siguiente. **Nota de
portabilidad (v3.3):** `pgcrypto` y `citext` están disponibles en Supabase free
tier, RDS y Postgres local por igual. `pg_partman` está disponible en Supabase (y
en RDS/self-hosted); gestiona la creación y retención de particiones nativas — su
uso concreto se documenta en la Sección 8.6. **Ya no se usa `timescaledb`**: fue
deprecado para proyectos nuevos de Supabase (ver 8.6).

```sql
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS citext;
-- Gestión de particiones nativas (creación anticipada + retención). En Supabase
-- vive en el esquema `partman`; en self-hosted se instala con el paquete
-- contrib/partman. Ver Sección 8.6 para la configuración completa.
CREATE SCHEMA IF NOT EXISTS partman;
CREATE EXTENSION IF NOT EXISTS pg_partman SCHEMA partman;
```

#### DDL Base (todas las tablas, orden de dependencia)

```sql
-- ============================================================
-- Nivel 0: Canal / Distribuidor
-- ============================================================
CREATE TABLE resellers (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name        TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','inactive')),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ============================================================
-- Nivel 1: Tenants (Asset Owners) y Partners (sub-tenants)
-- ============================================================
CREATE TABLE tenants (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    reseller_id   UUID NULL REFERENCES resellers(id) ON DELETE SET NULL,
    name          TEXT NOT NULL,
    vertical_type TEXT NOT NULL CHECK (vertical_type IN ('retail','banking','logistics')),
    timezone      TEXT NOT NULL DEFAULT 'America/Guatemala',
    status        TEXT NOT NULL DEFAULT 'onboarding' CHECK (status IN ('active','inactive','onboarding')),
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_tenants_reseller_id ON tenants(reseller_id);

CREATE TABLE partners (
    id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id          UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    name               TEXT NOT NULL,
    status             TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','revoked')),
    -- Acceso por tiempo limitado (nuevo, v3.4 — Sección 3.1 decisión 3, Flujo 3).
    -- NULL = acceso indefinido (default). Si se define, un job diario revoca el
    -- Partner por el mismo camino del offboarding manual (Sección 12.12) cuando
    -- access_expires_at < now() — no es mecanismo nuevo, solo un disparador distinto.
    access_expires_at  TIMESTAMPTZ NULL,
    invited_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_partners_tenant_id ON partners(tenant_id);
-- Índice parcial: el job diario de expiración solo escanea partners activos con
-- fecha de expiración fijada — evita un seq-scan sobre toda la tabla.
CREATE INDEX idx_partners_access_expiry ON partners(access_expires_at)
  WHERE status = 'active' AND access_expires_at IS NOT NULL;

-- ============================================================
-- Nivel 2-3: Sites → Cameras (jerarquía de infraestructura física)
-- ============================================================
CREATE TABLE sites (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id   UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    name        TEXT NOT NULL,
    address     TEXT,
    timezone    TEXT NOT NULL DEFAULT 'America/Guatemala',
    status      TEXT NOT NULL DEFAULT 'onboarding' CHECK (status IN ('active','inactive','onboarding')),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_sites_tenant_id ON sites(tenant_id);

CREATE TABLE cameras (
    id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    site_id              UUID NOT NULL REFERENCES sites(id) ON DELETE CASCADE,
    name                 TEXT NOT NULL,
    -- Credenciales cifradas — ver Sección 8.5. Nunca se guarda el RTSP en texto plano.
    rtsp_url_ciphertext  BYTEA NOT NULL,
    rtsp_url_key_id      TEXT NOT NULL,
    status               TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','inactive')),
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_cameras_site_id ON cameras(site_id);

-- ============================================================
-- Nivel 4: Zones (ROIs) — dueño exclusivo Tenant o Partner
-- ============================================================
CREATE TABLE zones (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    camera_id         UUID NOT NULL REFERENCES cameras(id) ON DELETE CASCADE,
    owner_type        TEXT NOT NULL CHECK (owner_type IN ('TENANT','PARTNER')),
    owner_tenant_id   UUID NULL REFERENCES tenants(id) ON DELETE CASCADE,
    owner_partner_id  UUID NULL REFERENCES partners(id) ON DELETE CASCADE,
    name              TEXT NOT NULL,
    zone_type         TEXT NOT NULL DEFAULT 'shelf',
    coordinates       JSONB NOT NULL, -- [[x1,y1],[x2,y2],...]
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_zone_owner_exclusive CHECK (
        (owner_type = 'TENANT'  AND owner_tenant_id  IS NOT NULL AND owner_partner_id IS NULL) OR
        (owner_type = 'PARTNER' AND owner_partner_id IS NOT NULL AND owner_tenant_id  IS NULL)
    )
);
CREATE INDEX idx_zones_camera_id ON zones(camera_id);
CREATE INDEX idx_zones_owner_tenant ON zones(owner_tenant_id);
CREATE INDEX idx_zones_owner_partner ON zones(owner_partner_id);
```

> **Nota de diseño:** en vez del patrón polimórfico `owner_type + owner_id UUID`
> (sin integridad referencial real), se usan dos columnas FK nulleables con un
> `CHECK` que exige exactamente una de las dos — Postgres puede entonces validar la
> integridad referencial de verdad (`ON DELETE CASCADE` funciona correctamente para
> ambos casos). Es una mejora deliberada sobre el `owner_id` plano de v2.0.

```sql
-- ============================================================
-- Time-Series: tracking_coordinates (particionada nativa) y agregados batch
-- ============================================================
-- v3.3: se reemplaza la hypertable de TimescaleDB por particionamiento declarativo
-- nativo de PostgreSQL (RANGE por "time"), gestionado por pg_partman. La clave de
-- partición ("time") ya forma parte de la PK, requisito de Postgres para tablas
-- particionadas. La configuración de pg_partman (create_parent + retención) vive en
-- la Sección 8.6. Ver esa sección para la justificación completa y la mitigación de
-- la pérdida de compresión columnar.
CREATE TABLE tracking_coordinates (
    "time"     TIMESTAMPTZ NOT NULL,
    camera_id  UUID NOT NULL REFERENCES cameras(id) ON DELETE CASCADE,
    person_id  TEXT NOT NULL,
    x          INTEGER NOT NULL,
    y          INTEGER NOT NULL,
    PRIMARY KEY (camera_id, "time", person_id)
) PARTITION BY RANGE ("time");
-- Índice sobre la tabla particionada: Postgres lo propaga a cada partición.
CREATE INDEX idx_tracking_camera_time ON tracking_coordinates(camera_id, "time" DESC);
-- Nota: create_parent de pg_partman crea una partición DEFAULT y las particiones
-- del rango inicial; ver Sección 8.6. En un entorno sin pg_partman, crear al menos
-- una partición explícita antes de insertar (ej. la del mes corriente).

-- Salida batch del Motor Matemático (Sección 6) — Dwell Time real por zona
CREATE TABLE zone_dwell_sessions (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    zone_id        UUID NOT NULL REFERENCES zones(id) ON DELETE CASCADE,
    person_id      TEXT NOT NULL,
    entered_at     TIMESTAMPTZ NOT NULL,
    exited_at      TIMESTAMPTZ,
    dwell_seconds  INTEGER,
    computed_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_zone_dwell_zone_id ON zone_dwell_sessions(zone_id);

-- ============================================================
-- Usuarios y asignación granular a sucursales
-- ============================================================
CREATE TABLE users (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id   UUID NULL REFERENCES tenants(id) ON DELETE CASCADE,
    reseller_id UUID NULL REFERENCES resellers(id) ON DELETE CASCADE,
    partner_id  UUID NULL REFERENCES partners(id) ON DELETE CASCADE,
    email       CITEXT NOT NULL UNIQUE,
    role        TEXT NOT NULL CHECK (role IN ('admin','operator','viewer')),
    status      TEXT NOT NULL DEFAULT 'invited' CHECK (status IN ('active','invited','disabled')),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_partner_requires_tenant CHECK (partner_id IS NULL OR tenant_id IS NOT NULL),
    CONSTRAINT chk_user_not_dual_scope CHECK (NOT (tenant_id IS NOT NULL AND reseller_id IS NOT NULL))
);
CREATE INDEX idx_users_tenant_id ON users(tenant_id);
CREATE INDEX idx_users_reseller_id ON users(reseller_id);
CREATE INDEX idx_users_partner_id ON users(partner_id);

CREATE TABLE user_site_assignments (
    user_id      UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    site_id      UUID NOT NULL REFERENCES sites(id) ON DELETE CASCADE,
    assigned_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, site_id)
);
CREATE INDEX idx_usa_site_id ON user_site_assignments(site_id);

-- ============================================================
-- Model Registry y flota de Edge Gateways
-- ============================================================
CREATE TABLE model_registry_entries (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    vertical_type    TEXT NOT NULL CHECK (vertical_type IN ('retail','banking','logistics')),
    version          TEXT NOT NULL,
    s3_key           TEXT NOT NULL,
    checksum_sha256  TEXT NOT NULL,
    released_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    is_current       BOOLEAN NOT NULL DEFAULT false
);

CREATE TABLE edge_gateways (
    id                     TEXT PRIMARY KEY,
    site_id                UUID NOT NULL REFERENCES sites(id) ON DELETE CASCADE,
    vertical_type          TEXT NOT NULL,
    current_model_version  TEXT,
    channel                TEXT NOT NULL DEFAULT 'stable' CHECK (channel IN ('stable','canary')),
    last_heartbeat_at      TIMESTAMPTZ,
    status                 TEXT NOT NULL DEFAULT 'offline' CHECK (status IN ('online','offline','degraded'))
);
CREATE INDEX idx_edge_gateways_site_id ON edge_gateways(site_id);
```

> **Nota de diseño (`users`):** v2.0 no definía cómo un usuario de Partner se
> relaciona con la tabla de usuarios; se agregó `partner_id` (nullable) a `users`
> para que un usuario de Partner sea `tenant_id = <Asset Owner padre>` +
> `partner_id = <su Partner>`, en vez de introducir una cuarta jerarquía de tablas.
> El `role` (`admin/operator/viewer`) se interpreta según el scope activo del
> usuario — es el mismo enum tanto para un admin de Tenant como para un admin de
> Partner o de Reseller. **Valida que esta interpretación te sirva** antes de
> generar el código de autenticación.

---

#### 8.1 Jerarquía de Sucursales (Multi-Sede por Cliente)

`sites` es la entidad intermedia formal entre `tenants` y `cameras` (ya incluida en
el DDL base de 8.0). Cada `camera` pertenece a exactamente una `site`, y cada `site`
pertenece a exactamente un `tenant` — un Asset Owner con 40 sucursales tiene 40 filas
en `sites`, todas bajo el mismo `tenant_id`.

**Vistas agregadas con `security_invoker` (PostgreSQL 15+):**

```sql
-- Tráfico diario por sucursal — respeta el RLS de quien la consulta
CREATE VIEW site_traffic_daily
WITH (security_invoker = true) AS
SELECT
    c.site_id,
    date_trunc('day', tc."time") AS day,
    count(DISTINCT tc.person_id) AS unique_visitors,
    count(*) AS total_detections
FROM tracking_coordinates tc
JOIN cameras c ON c.id = tc.camera_id
GROUP BY c.site_id, date_trunc('day', tc."time");

-- Comparativo entre sucursales del mismo tenant (ej. Sucursal A vs Sucursal B)
CREATE VIEW site_traffic_comparison
WITH (security_invoker = true) AS
SELECT
    s.id   AS site_id,
    s.name AS site_name,
    date_trunc('week', tc."time") AS week,
    count(DISTINCT tc.person_id) AS unique_visitors
FROM tracking_coordinates tc
JOIN cameras c ON c.id = tc.camera_id
JOIN sites   s ON s.id = c.site_id
GROUP BY s.id, s.name, date_trunc('week', tc."time");
```

`security_invoker = true` es la pieza clave: sin ella, una vista en Postgres corre
con los privilegios de quien la creó (típicamente un rol con permisos amplios),
**ignorando el RLS de la sesión que la consulta** — sería una fuga de aislamiento
trivial de introducir por accidente. Con `security_invoker`, `site_traffic_comparison`
consultada por un Tenant Admin (`role = 'admin'`) automáticamente devuelve todas las
sucursales del tenant, y consultada por un Operator regional automáticamente se
acota a sus sucursales asignadas — sin lógica adicional, porque el RLS de
`tracking_coordinates` (Sección 8.3) ya resuelve el filtro por fila.

---

#### 8.2 Gestión de Usuarios y Asignación desde el Backoffice

La tabla `users` y la tabla puente `user_site_assignments` (ambas en el DDL de 8.0)
implementan la asignación granular: **un usuario puede tener acceso a N sucursales**,
y esa asignación la controla el Tenant Admin desde el backoffice, no el SuperAdmin.

**Caso "acceso a todas las sucursales" (rol `admin` de tenant):** un `admin` no
necesita filas en `user_site_assignments` — su RLS efectivo es "todas las sucursales
donde `sites.tenant_id = su tenant_id`", sin importar la tabla puente. Esto evita
tener que mantener sincronizada una fila por cada sucursal cada vez que se abre una
nueva sede.

**Caso "acceso limitado" (rol `operator`/`viewer` regional):** el backoffice
inserta una fila en `user_site_assignments` por cada sucursal habilitada:

```sql
-- El Tenant Admin asigna al usuario X las sucursales "Zona 10" y "Zona 4"
INSERT INTO user_site_assignments (user_id, site_id)
VALUES
  ('11111111-1111-1111-1111-111111111111', '<site_id_zona_10>'),
  ('11111111-1111-1111-1111-111111111111', '<site_id_zona_4>');
```

**Inyección en el contexto de sesión:** al autenticar, el backend resuelve el `role`
y las sucursales asignadas del usuario, y las inyecta como variables de sesión de
Postgres (GUCs) antes de ejecutar cualquier query en nombre de ese usuario:

```sql
-- Ejecutado por el backend al abrir la conexión/transacción de este usuario
SET LOCAL app.current_tenant_id      = '<tenant_id del usuario>';
SET LOCAL app.current_partner_id     = '';   -- vacío: no es sesión de partner
SET LOCAL app.current_actor_role     = 'operator';
SET LOCAL app.current_user_site_ids  = '<site_id_1>,<site_id_2>';
```

> **Nota de nomenclatura (corrección v3.2, descubierta por ejecución real):** la
> GUC de rol se llama `app.current_actor_role` — **no** `app.current_role` como en
> versiones anteriores. `current_role` es palabra reservada del estándar SQL y
> `SET app.current_role = ...` es un **error de sintaxis** en PostgreSQL (el
> parser la intercepta incluso calificada); la única forma de fijarla con ese
> nombre sería `set_config()`, lo que habría convertido cada test y cada snippet
> de sesión en una trampa. El nombre `current_actor_role` evita el problema por
> completo.

Funciones helper para leer esas GUCs de forma segura desde cualquier policy o vista
— **`STABLE LEAKPROOF PARALLEL SAFE`, requisito no negociable de la arquitectura**:

```sql
CREATE OR REPLACE FUNCTION app_current_tenant_id() RETURNS UUID
LANGUAGE sql STABLE LEAKPROOF PARALLEL SAFE AS $$
  SELECT NULLIF(current_setting('app.current_tenant_id', true), '')::UUID
$$;

CREATE OR REPLACE FUNCTION app_current_partner_id() RETURNS UUID
LANGUAGE sql STABLE LEAKPROOF PARALLEL SAFE AS $$
  SELECT NULLIF(current_setting('app.current_partner_id', true), '')::UUID
$$;

CREATE OR REPLACE FUNCTION app_current_role() RETURNS TEXT
LANGUAGE sql STABLE LEAKPROOF PARALLEL SAFE AS $$
  SELECT NULLIF(current_setting('app.current_actor_role', true), '')
$$;

CREATE OR REPLACE FUNCTION app_current_site_ids() RETURNS UUID[]
LANGUAGE sql STABLE LEAKPROOF PARALLEL SAFE AS $$
  SELECT CASE
    WHEN NULLIF(current_setting('app.current_user_site_ids', true), '') IS NULL
    THEN ARRAY[]::UUID[]
    ELSE string_to_array(current_setting('app.current_user_site_ids', true), ',')::UUID[]
  END
$$;
```

Estas cuatro funciones son las que consumen todas las políticas RLS de la Sección
8.3 — se definen una sola vez y se reutilizan en cada tabla/vista protegida.

**Por qué `LEAKPROOF` y qué implica operativamente:** (a) *Corrección de
rendimiento:* el planner de Postgres solo empuja predicados que contienen funciones
por debajo de una barrera de seguridad (RLS) si están marcadas `LEAKPROOF`; sin la
marca, filtros aparentemente triviales pueden ejecutarse *después* de materializar
filas, degradando consultas sobre `tracking_coordinates` (millones de filas) de
index-scan a seq-scan. (b) *Seguridad:* estas funciones solo leen GUCs de la propia
sesión y no emiten mensajes de error dependientes de datos de filas, por lo que la
marca es legítima — nunca marcar `LEAKPROOF` una función que pueda filtrar
contenido de filas vía errores o `RAISE`. (c) *Operación:* `ALTER FUNCTION ...
LEAKPROOF` requiere rol superusuario. En Postgres autoadministrado (EC2) no hay
fricción; en servicios gestionados (RDS, Supabase) el rol administrativo estándar
**no** es superusuario — la migración que crea estas funciones debe ejecutarse por
el canal privilegiado del proveedor (en RDS, solicitar vía soporte o usar una
instancia donde el atributo sea aplicable; validar en la prueba de concepto de
infraestructura **antes** de comprometer proveedor). Si el proveedor elegido no lo
permite, la alternativa es inlinear `current_setting(...)` directamente en cada
policy (las funciones built-in relevantes ya son leakproof), manteniendo las
funciones helper solo como documentación — pero la decisión por defecto de este
documento es `LEAKPROOF` explícito.

---

#### 8.3 Aislamiento de Tres Niveles: Tenant → Site → Partner

Con `zones` ya definida (owner exclusivo `TENANT` o `PARTNER`, Sección 8.0) y las
funciones helper de 8.2, la política `tracking_coordinates_isolation` generaliza los
tres contextos pedidos — tenant completo, tenant acotado por sucursal, y partner:

```sql
ALTER TABLE tracking_coordinates ENABLE ROW LEVEL SECURITY;
ALTER TABLE tracking_coordinates FORCE ROW LEVEL SECURITY; -- aplica incluso al dueño de la tabla

CREATE POLICY tracking_coordinates_isolation ON tracking_coordinates
FOR SELECT
USING (
  -- Contexto PARTNER: solo cámaras donde el partner tiene al menos una zona propia
  ( app_current_partner_id() IS NOT NULL AND EXISTS (
      SELECT 1 FROM zones z
      WHERE z.camera_id = tracking_coordinates.camera_id
        AND z.owner_type = 'PARTNER'
        AND z.owner_partner_id = app_current_partner_id()
  ))
  OR
  -- Contexto TENANT, rol admin: todas las sucursales del tenant
  ( app_current_partner_id() IS NULL AND app_current_role() = 'admin' AND EXISTS (
      SELECT 1 FROM cameras c JOIN sites s ON s.id = c.site_id
      WHERE c.id = tracking_coordinates.camera_id
        AND s.tenant_id = app_current_tenant_id()
  ))
  OR
  -- Contexto TENANT, rol operator/viewer: solo sucursales asignadas
  ( app_current_partner_id() IS NULL AND app_current_role() IN ('operator','viewer') AND EXISTS (
      SELECT 1 FROM cameras c
      WHERE c.id = tracking_coordinates.camera_id
        AND c.site_id = ANY (app_current_site_ids())
  ))
);
```

**Nota de granularidad:** esta política filtra a nivel de `camera_id` para el
contexto Partner, no a nivel de polígono — si una cámara tiene una zona del Asset
Owner y otra zona de un Partner, el Partner técnicamente podría hacer `SELECT`
directo sobre coordenadas de esa cámara que caen fuera de su polígono. Por diseño,
**el API nunca expone `tracking_coordinates` en crudo a un Partner**; el único
camino de lectura para un Partner es a través de `zone_dwell_sessions` (que sí es
estrictamente por `zone_id`, ver política abajo) o de las vistas agregadas. La RLS
sobre la tabla cruda queda como defensa en profundidad, no como el único control.

```sql
ALTER TABLE zone_dwell_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE zone_dwell_sessions FORCE ROW LEVEL SECURITY;

CREATE POLICY zone_dwell_sessions_isolation ON zone_dwell_sessions
FOR SELECT
USING (
  EXISTS (
    SELECT 1 FROM zones z
    WHERE z.id = zone_dwell_sessions.zone_id
      AND (
        -- Contexto TENANT: zonas propias del tenant...
        (z.owner_type = 'TENANT'  AND app_current_partner_id() IS NULL
             AND z.owner_tenant_id = app_current_tenant_id())
        OR
        -- ...Y ADEMÁS las zonas que el tenant cedió a sus propios Partners.
        -- (Corrección v3.2: sin esta rama, asignar una zona a un Partner la
        -- volvía INVISIBLE para el Asset Owner, contradiciendo el Flujo 3, que
        -- garantiza que el Asset Owner "conserva siempre" su visibilidad.)
        (z.owner_type = 'PARTNER' AND app_current_partner_id() IS NULL
             AND EXISTS (
               SELECT 1 FROM partners p
               WHERE p.id = z.owner_partner_id
                 AND p.tenant_id = app_current_tenant_id()
             ))
        OR
        -- Contexto PARTNER: exclusivamente sus zonas asignadas.
        (z.owner_type = 'PARTNER' AND app_current_partner_id() IS NOT NULL
             AND z.owner_partner_id = app_current_partner_id())
      )
  )
);
```

**Nota sobre usuarios regionales:** para `operator`/`viewer` acotados por sucursal,
la rama TENANT se restringe adicionalmente vía la cadena `zones.camera_id →
cameras.site_id = ANY (app_current_site_ids())` cuando `app_current_role() IN
('operator','viewer')` — mismo patrón de la política de `tracking_coordinates`.

**RLS completo de las ocho tablas restantes (escrito y validado por ejecución en
v3.3).** Versiones anteriores decían "la misma política aplica a `sites`, `cameras`
y `zones`... se omiten por brevedad" — pero nunca se escribieron, y faltaban por
completo `users`, `partners`, `tenants`, `resellers` y `user_site_assignments`. Una
tabla sin `ENABLE/FORCE ROW LEVEL SECURITY` y sin políticas es una fuga: cualquier
rol de aplicación la lee entera. A continuación el DDL real de las ocho, validado
por ejecución contra PostgreSQL 16.

**Pitfall resuelto — recursión mutua entre políticas.** Si la política de `sites`
subconsulta `zones` y la de `zones` subconsulta `sites`/`cameras`, Postgres entra en
`infinite recursion detected in policy` al evaluar RLS anidado. La solución
idiomática (y la que usa Supabase) es encapsular las verificaciones de *pertenencia*
en funciones `SECURITY DEFINER` cuyo dueño tiene `BYPASSRLS` (el rol `postgres` en
Supabase/self-hosted): la consulta interna de la función no re-dispara RLS, cortando
el ciclo. Estas funciones devuelven solo booleanos/escalares — nunca filas — por lo
que no filtran datos entre contextos. Se marcan `STABLE SECURITY DEFINER` con
`SET search_path = public` (no `LEAKPROOF`: leen tablas; ese requisito aplica solo a
los helpers de GUC de 8.2).

```sql
-- Tres GUCs de contexto adicionales que necesita el RLS de gestión.
CREATE OR REPLACE FUNCTION app_current_reseller_id() RETURNS UUID
LANGUAGE sql STABLE LEAKPROOF PARALLEL SAFE AS $$
  SELECT NULLIF(current_setting('app.current_reseller_id', true), '')::UUID $$;
CREATE OR REPLACE FUNCTION app_current_user_id() RETURNS UUID
LANGUAGE sql STABLE LEAKPROOF PARALLEL SAFE AS $$
  SELECT NULLIF(current_setting('app.current_user_id', true), '')::UUID $$;
-- Contexto de aprovisionamiento SuperAdmin (onboarding): tenant objetivo fijado por
-- el backend interno tras validar identidad SuperAdmin.
CREATE OR REPLACE FUNCTION app_provision_tenant_id() RETURNS UUID
LANGUAGE sql STABLE LEAKPROOF PARALLEL SAFE AS $$
  SELECT NULLIF(current_setting('app.provision_tenant_id', true), '')::UUID $$;

-- Helpers de PERTENENCIA (SECURITY DEFINER; rompen la recursión mutua).
CREATE OR REPLACE FUNCTION sec_tenant_owns_site(p_site UUID, p_tenant UUID)
RETURNS BOOLEAN LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public AS $$
  SELECT EXISTS (SELECT 1 FROM sites s WHERE s.id = p_site AND s.tenant_id = p_tenant) $$;
CREATE OR REPLACE FUNCTION sec_tenant_owns_camera(p_cam UUID, p_tenant UUID)
RETURNS BOOLEAN LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public AS $$
  SELECT EXISTS (SELECT 1 FROM cameras c JOIN sites s ON s.id = c.site_id
                 WHERE c.id = p_cam AND s.tenant_id = p_tenant) $$;
CREATE OR REPLACE FUNCTION sec_partner_has_zone_on_site(p_site UUID, p_partner UUID)
RETURNS BOOLEAN LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public AS $$
  SELECT EXISTS (SELECT 1 FROM zones z JOIN cameras c ON c.id = z.camera_id
                 WHERE c.site_id = p_site
                   AND z.owner_type = 'PARTNER' AND z.owner_partner_id = p_partner) $$;
CREATE OR REPLACE FUNCTION sec_partner_has_zone_on_camera(p_cam UUID, p_partner UUID)
RETURNS BOOLEAN LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public AS $$
  SELECT EXISTS (SELECT 1 FROM zones z WHERE z.camera_id = p_cam
                   AND z.owner_type = 'PARTNER' AND z.owner_partner_id = p_partner) $$;
CREATE OR REPLACE FUNCTION sec_partner_tenant(p_partner UUID)
RETURNS UUID LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public AS $$
  SELECT p.tenant_id FROM partners p WHERE p.id = p_partner $$;
CREATE OR REPLACE FUNCTION sec_partner_belongs_to_tenant(p_partner UUID, p_tenant UUID)
RETURNS BOOLEAN LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public AS $$
  SELECT EXISTS (SELECT 1 FROM partners p WHERE p.id = p_partner AND p.tenant_id = p_tenant) $$;

-- ---------- resellers ----------
ALTER TABLE resellers ENABLE ROW LEVEL SECURITY;
ALTER TABLE resellers FORCE ROW LEVEL SECURITY;
CREATE POLICY resellers_read ON resellers
FOR SELECT USING ( id = app_current_reseller_id() );

-- ---------- tenants ----------
ALTER TABLE tenants ENABLE ROW LEVEL SECURITY;
ALTER TABLE tenants FORCE ROW LEVEL SECURITY;
CREATE POLICY tenants_read ON tenants
FOR SELECT USING (
  ( app_current_partner_id() IS NULL AND app_current_reseller_id() IS NULL
      AND tenants.id = app_current_tenant_id() )
  OR ( app_current_partner_id() IS NOT NULL
      AND sec_partner_belongs_to_tenant(app_current_partner_id(), tenants.id) )
  OR ( app_current_reseller_id() IS NOT NULL
      AND tenants.reseller_id = app_current_reseller_id() )  -- metadata de gestión, Sección 4
);

-- ---------- partners ----------
ALTER TABLE partners ENABLE ROW LEVEL SECURITY;
ALTER TABLE partners FORCE ROW LEVEL SECURITY;
CREATE POLICY partners_read ON partners
FOR SELECT USING (
  ( app_current_partner_id() IS NULL AND app_current_role() = 'admin'
      AND partners.tenant_id = app_current_tenant_id() )
  OR ( partners.id = app_current_partner_id() )
);
CREATE POLICY partners_write ON partners
FOR INSERT WITH CHECK ( app_current_partner_id() IS NULL AND app_current_role() = 'admin'
  AND partners.tenant_id = app_current_tenant_id() );
CREATE POLICY partners_update ON partners
FOR UPDATE USING ( app_current_partner_id() IS NULL AND app_current_role() = 'admin'
  AND partners.tenant_id = app_current_tenant_id() );

-- ---------- sites ----------
ALTER TABLE sites ENABLE ROW LEVEL SECURITY;
ALTER TABLE sites FORCE ROW LEVEL SECURITY;
CREATE POLICY sites_read ON sites
FOR SELECT USING (
  ( app_current_partner_id() IS NULL AND app_current_role() = 'admin'
      AND sites.tenant_id = app_current_tenant_id() )
  OR ( app_current_partner_id() IS NULL AND app_current_role() IN ('operator','viewer')
      AND sites.id = ANY (app_current_site_ids()) )
  OR ( app_current_partner_id() IS NOT NULL
      AND sec_partner_has_zone_on_site(sites.id, app_current_partner_id()) )
);
CREATE POLICY sites_provision ON sites
FOR INSERT WITH CHECK ( sites.tenant_id = app_provision_tenant_id() );

-- ---------- cameras ----------
ALTER TABLE cameras ENABLE ROW LEVEL SECURITY;
ALTER TABLE cameras FORCE ROW LEVEL SECURITY;
CREATE POLICY cameras_read ON cameras
FOR SELECT USING (
  ( app_current_partner_id() IS NULL AND app_current_role() = 'admin'
      AND sec_tenant_owns_camera(cameras.id, app_current_tenant_id()) )
  OR ( app_current_partner_id() IS NULL AND app_current_role() IN ('operator','viewer')
      AND cameras.site_id = ANY (app_current_site_ids()) )
  OR ( app_current_partner_id() IS NOT NULL
      AND sec_partner_has_zone_on_camera(cameras.id, app_current_partner_id()) )
);
CREATE POLICY cameras_provision ON cameras
FOR INSERT WITH CHECK ( sec_tenant_owns_site(cameras.site_id, app_provision_tenant_id()) );

-- ---------- zones ----------
ALTER TABLE zones ENABLE ROW LEVEL SECURITY;
ALTER TABLE zones FORCE ROW LEVEL SECURITY;
CREATE POLICY zones_read ON zones
FOR SELECT USING (
  ( app_current_partner_id() IS NULL AND app_current_role() = 'admin'
      AND (
        (zones.owner_type = 'TENANT' AND zones.owner_tenant_id = app_current_tenant_id())
        OR (zones.owner_type = 'PARTNER'
             AND sec_partner_belongs_to_tenant(zones.owner_partner_id, app_current_tenant_id()))
      ) )
  OR ( app_current_partner_id() IS NULL AND app_current_role() IN ('operator','viewer')
      AND EXISTS (SELECT 1 FROM cameras c WHERE c.id = zones.camera_id
                    AND c.site_id = ANY (app_current_site_ids())) )
  OR ( zones.owner_type = 'PARTNER' AND zones.owner_partner_id = app_current_partner_id() )
);
-- Reasignación de owner (Módulo de Reventa, Flujo 3): Tenant Admin del tenant dueño.
CREATE POLICY zones_update ON zones
FOR UPDATE USING ( app_current_partner_id() IS NULL AND app_current_role() = 'admin'
  AND sec_tenant_owns_camera(zones.camera_id, app_current_tenant_id()) );
CREATE POLICY zones_provision ON zones
FOR INSERT WITH CHECK ( sec_tenant_owns_camera(zones.camera_id, app_provision_tenant_id()) );

-- ---------- users ----------
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE users FORCE ROW LEVEL SECURITY;
CREATE POLICY users_read ON users
FOR SELECT USING (
  ( users.id = app_current_user_id() )                                  -- perfil propio
  OR ( app_current_partner_id() IS NULL AND app_current_role() = 'admin'
      AND users.tenant_id = app_current_tenant_id() )                   -- tenant admin
  OR ( app_current_partner_id() IS NOT NULL AND app_current_role() = 'admin'
      AND users.partner_id = app_current_partner_id() )                 -- partner admin
  OR ( app_current_reseller_id() IS NOT NULL
      AND users.reseller_id = app_current_reseller_id() )               -- reseller admin
);
CREATE POLICY users_write ON users
FOR INSERT WITH CHECK ( app_current_role() = 'admin' AND (
    ( app_current_partner_id() IS NULL AND users.tenant_id = app_current_tenant_id() )
    OR ( app_current_partner_id() IS NOT NULL AND users.partner_id = app_current_partner_id() )
) );

-- ---------- user_site_assignments ----------
ALTER TABLE user_site_assignments ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_site_assignments FORCE ROW LEVEL SECURITY;
CREATE POLICY usa_read ON user_site_assignments
FOR SELECT USING (
  ( user_site_assignments.user_id = app_current_user_id() )
  OR ( app_current_partner_id() IS NULL AND app_current_role() = 'admin'
      AND sec_tenant_owns_site(user_site_assignments.site_id, app_current_tenant_id()) )
);
CREATE POLICY usa_write ON user_site_assignments
FOR INSERT WITH CHECK ( app_current_partner_id() IS NULL AND app_current_role() = 'admin'
  AND sec_tenant_owns_site(user_site_assignments.site_id, app_current_tenant_id()) );
```

> **Nota sobre dos caminos de escritura (deliberado).** Las altas que hace el
> **Tenant Admin** desde el backoffice (partners, usuarios, reasignación de owner de
> zonas, asignaciones a sucursales) pasan por RLS con `WITH CHECK` acotado al tenant
> de la sesión — el mismo principio de defensa en profundidad del resto del sistema.
> Las altas de **onboarding del SuperAdmin** (crear el tenant, sus sedes y cámaras)
> usan el contexto de aprovisionamiento `app.provision_tenant_id`, que el backend
> interno solo fija tras validar identidad SuperAdmin — nunca expuesto a un rol de
> tenant/partner. La creación del propio `resellers` y del primer `tenant` es una
> operación de plataforma que corre por el canal interno (rol con `BYPASSRLS`),
> igual que el acceso a `platform_admins`/`break_glass_audit_log` de la Sección 8.5.

**Validación por ejecución (v3.3).** El DDL anterior se corrió contra PostgreSQL 16
con un rol de aplicación no-superusuario, confirmando: tenant admin ve sus 2 sedes,
1 partner y 2 zonas (propia + cedida); Partner ve exactamente su zona (1), la sede
donde la tiene (1), su tenant padre (1) y **cero** partners ajenos; operator acotado
a Zona 10 ve esa cámara pero **cero** cámaras de Zona 4; reseller ve solo el tenant
de su cartera; y las políticas de `tracking_coordinates`/`zone_dwell_sessions` de
v3.2 siguen funcionando sin recursión al activar RLS sobre `sites`/`cameras`/`zones`.

**Política de escritura para el pipeline de ingesta (corrección v3.2):** las
políticas anteriores son `FOR SELECT`. Con `FORCE ROW LEVEL SECURITY`, una tabla
sin política de `INSERT` **rechaza todas las escrituras**, incluidas las del propio
backend — comportamiento correcto por defecto (deny-by-default), pero el servicio de
ingesta necesita su política explícita, acotada al `site` del Edge Gateway
autenticado (el backend fija `app.current_ingest_site_id` al validar el JWT del
gateway, nunca a partir del payload):

```sql
CREATE OR REPLACE FUNCTION app_current_ingest_site_id() RETURNS UUID
LANGUAGE sql STABLE LEAKPROOF PARALLEL SAFE AS $$
  SELECT NULLIF(current_setting('app.current_ingest_site_id', true), '')::UUID
$$;

CREATE POLICY tracking_coordinates_ingest ON tracking_coordinates
FOR INSERT
WITH CHECK (
  EXISTS (
    SELECT 1 FROM cameras c
    WHERE c.id = tracking_coordinates.camera_id
      AND c.site_id = app_current_ingest_site_id()
  )
);
```

Esto cierra un vector real: un Edge Gateway comprometido (está físicamente en la
sede del cliente) no puede inyectar telemetría hacia cámaras de otra sede u otro
tenant aunque falsifique `camera_id` en el payload — la política lo rechaza a nivel
de base de datos.

**Política de INSERT para `zone_dwell_sessions` (corrección v3.3, antes ausente):**
la versión anterior *mencionaba* que el Motor Matemático escribía "con su propia
política `FOR INSERT` equivalente", pero nunca se escribió — y con `FORCE ROW LEVEL
SECURITY` eso significa que el Motor Matemático **no podía insertar ni una fila**.
El Motor corre bajo contexto de servicio con `app.motor_site_id` fijado al `site`
del lote en proceso, y la política verifica la cadena `zone → camera → site`:

```sql
CREATE OR REPLACE FUNCTION app_motor_site_id() RETURNS UUID
LANGUAGE sql STABLE LEAKPROOF PARALLEL SAFE AS $$
  SELECT NULLIF(current_setting('app.motor_site_id', true), '')::UUID $$;

CREATE POLICY zone_dwell_sessions_ingest ON zone_dwell_sessions
FOR INSERT WITH CHECK (
  EXISTS (SELECT 1 FROM zones z JOIN cameras c ON c.id = z.camera_id
          WHERE z.id = zone_dwell_sessions.zone_id AND c.site_id = app_motor_site_id())
);
```

Validado por ejecución: el Motor inserta con `motor_site_id` correcto y es
rechazado con un `site` ajeno.

**Alcance de Partner a nivel de sucursal completa:** como `zones.owner_partner_id`
se asigna por zona individual, para "asignarle una sucursal completa a una marca" el
Módulo de Reventa simplemente crea/reasigna **todas** las zonas de esa sucursal al
mismo `partner_id` en una sola operación — no requiere una tabla `partner_site_
assignments` separada, evitando dos fuentes de verdad para el mismo concepto de
scope.

---

#### 8.4 Gestión de Ambientes (Dev/QA/Staging/Prod — arquitectura completa;
Dev+Prod para el MLP)

> **MLP (v3.4 — Sección 3.1, decisión 4):** para el lanzamiento se usan únicamente
> **Dev + Prod**, con la **suite pgTAP completa (Sección 8.4 abajo) como gate
> obligatorio** de toda promoción Dev→Prod — el pipeline de migraciones descrito
> más abajo (levantar instancia efímera, correr migraciones, correr pgTAP,
> verificar reversibilidad) no se recorta, solo se recorta el *número de
> ambientes intermedios* entre Dev y Prod. **Gancho de activación:** QA/Staging
> (la tabla completa de abajo) se agregan como nodos adicionales al mismo pipeline
> cuando el volumen de clientes lo justifique — no es un rediseño del pipeline de
> CI, es insertar un ambiente más en la misma cadena de promoción.

**Separación por ambiente — instancias, no solo esquemas (arquitectura completa):**

| Ambiente | Aislamiento recomendado | Justificación |
| --- | --- | --- |
| **Dev (local)** | Contenedor Docker efímero, un solo esquema | Ciclo de vida de minutos; no vale la pena una instancia completa. |
| **QA** *(post-MLP)* | Instancia/proyecto Postgres separado | Corre la suite de aislamiento (pgTAP) contra un clon real de la topología de extensiones (`pg_partman`, `pgcrypto`, `citext`, RLS) sin compartir recursos con Staging. |
| **Staging** *(post-MLP)* | Instancia/proyecto Postgres separado, con IaC idéntico a Prod | Debe ser un espejo fiel de Prod (misma versión de Postgres, mismas extensiones, mismas políticas RLS y misma configuración de particionamiento) — es el último gate antes de producción. |
| **Prod** | Instancia dedicada, backups PITR | — |

Se descarta la separación por esquema-único-compartido entre QA/Staging/Prod: el
riesgo de una política RLS mal aplicada en un ambiente "de prueba" que en realidad
comparte el mismo clúster que producción no vale el ahorro de costo, dado que la
sensibilidad del dato (rastreo de personas) es alta. **Esto aplica igual en el MLP
recortado:** Dev y Prod nunca comparten clúster, aunque no exista un QA/Staging
intermedio — el ahorro operativo del MLP es en número de ambientes, no en el
principio de aislamiento físico entre pruebas y producción.

**Datos sintéticos para QA/Staging (no solo `tracking_coordinates`):**

```sql
-- Semilla mínima: 1 reseller, 2 tenants, sucursales, partner, usuarios de prueba.
-- (Corrección v3.2: la versión anterior usaba literales tipo 'r1'/'t1' en columnas
-- UUID — falla con "invalid input syntax for type uuid". Se usan UUIDs fijos
-- legibles; el sufijo identifica la entidad. Este bloque es ejecutable tal cual.)
INSERT INTO resellers (id, name) VALUES
  ('00000000-0000-4000-8000-0000000000e1', 'Reseller Demo Centroamérica');

INSERT INTO tenants (id, reseller_id, name, vertical_type) VALUES
  ('00000000-0000-4000-8000-0000000000a1', '00000000-0000-4000-8000-0000000000e1',
     'La Torre (retail demo)', 'retail'),
  ('00000000-0000-4000-8000-0000000000a2', NULL, 'Banco Demo', 'banking');

INSERT INTO sites (id, tenant_id, name) VALUES
  ('00000000-0000-4000-8000-0000000000b1', '00000000-0000-4000-8000-0000000000a1', 'La Torre Zona 10'),
  ('00000000-0000-4000-8000-0000000000b2', '00000000-0000-4000-8000-0000000000a1', 'La Torre Zona 4'),
  ('00000000-0000-4000-8000-0000000000b3', '00000000-0000-4000-8000-0000000000a2', 'Sucursal Banco Centro');

-- Usuarios de prueba: un admin, un operator acotado a Zona 10, un viewer de partner
INSERT INTO users (id, tenant_id, email, role) VALUES
  ('00000000-0000-4000-8000-0000000000c1', '00000000-0000-4000-8000-0000000000a1', 'admin@qa.demo',    'admin'),
  ('00000000-0000-4000-8000-0000000000c2', '00000000-0000-4000-8000-0000000000a1', 'operator@qa.demo', 'operator');
INSERT INTO user_site_assignments (user_id, site_id) VALUES
  ('00000000-0000-4000-8000-0000000000c2', '00000000-0000-4000-8000-0000000000b1');

INSERT INTO partners (id, tenant_id, name) VALUES
  ('00000000-0000-4000-8000-0000000000d1', '00000000-0000-4000-8000-0000000000a1', 'Nestlé Demo');
INSERT INTO users (id, tenant_id, partner_id, email, role) VALUES
  ('00000000-0000-4000-8000-0000000000c3', '00000000-0000-4000-8000-0000000000a1',
   '00000000-0000-4000-8000-0000000000d1', 'viewer@partner.demo', 'viewer');

-- Generador de tracking sintético (pseudocódigo del script, no SQL puro):
-- para cada camera_id activa, simular un random walk de N personas por hora
-- durante el rango de fechas de prueba, insertando en tracking_coordinates.
```

**Suite de aislamiento automatizada (pgTAP), corre antes de cada promoción de
ambiente:**

```sql
-- tests/isolation/01_tenant_isolation.sql
-- (Los UUIDs corresponden a la semilla de arriba: ...a1 = tenant demo retail,
--  ...a2 = tenant demo banking, ...b1/...b2 = sites del tenant a1, ...d1 = partner.)
BEGIN;
SELECT plan(2);

SET LOCAL app.current_tenant_id = '00000000-0000-4000-8000-0000000000a1';
SET LOCAL app.current_partner_id = '';
SET LOCAL app.current_actor_role = 'admin';

SELECT ok(
  (SELECT count(*) FROM tracking_coordinates) =
  (SELECT count(*) FROM tracking_coordinates tc JOIN cameras c ON c.id = tc.camera_id
     JOIN sites s ON s.id = c.site_id
     WHERE s.tenant_id = '00000000-0000-4000-8000-0000000000a1'),
  'Tenant a1 (admin) solo ve filas de sus propias cámaras'
);

SELECT is(
  (SELECT count(*) FROM tracking_coordinates tc JOIN cameras c ON c.id = tc.camera_id
     JOIN sites s ON s.id = c.site_id
     WHERE s.tenant_id = '00000000-0000-4000-8000-0000000000a2')::int,
  0,
  'Tenant a1 nunca ve filas del tenant a2, aunque existan en la tabla física'
);

SELECT * FROM finish();
ROLLBACK;
```

```sql
-- tests/isolation/02_site_scoped_isolation.sql
BEGIN;
SELECT plan(1);

SET LOCAL app.current_tenant_id = '00000000-0000-4000-8000-0000000000a1';
SET LOCAL app.current_partner_id = '';
SET LOCAL app.current_actor_role = 'operator';
SET LOCAL app.current_user_site_ids = '00000000-0000-4000-8000-0000000000b1';

SELECT is(
  (SELECT count(*) FROM tracking_coordinates tc JOIN cameras c ON c.id = tc.camera_id
     WHERE c.site_id = '00000000-0000-4000-8000-0000000000b2')::int,
  0,
  'Operator asignado solo a Zona 10 no ve ninguna fila de Zona 4, aunque ambas sean del mismo tenant'
);

SELECT * FROM finish();
ROLLBACK;
```

```sql
-- tests/isolation/03_partner_isolation.sql
BEGIN;
SELECT plan(2);

SET LOCAL app.current_tenant_id = '';
SET LOCAL app.current_partner_id = '00000000-0000-4000-8000-0000000000d1';
SET LOCAL app.current_actor_role = 'viewer';

SELECT is(
  (SELECT count(*) FROM zone_dwell_sessions zds JOIN zones z ON z.id = zds.zone_id
     WHERE z.owner_type = 'TENANT')::int,
  0,
  'Partner d1 nunca ve sesiones de dwell time de zonas propiedad del tenant'
);

SELECT is(
  (SELECT count(*) FROM zone_dwell_sessions zds JOIN zones z ON z.id = zds.zone_id
     WHERE z.owner_type = 'PARTNER'
       AND z.owner_partner_id <> '00000000-0000-4000-8000-0000000000d1')::int,
  0,
  'Partner d1 nunca ve zonas asignadas a otros Partners del mismo tenant'
);

SELECT * FROM finish();
ROLLBACK;
```

```sql
-- tests/isolation/04_tenant_keeps_visibility_of_ceded_zones.sql
-- (Nuevo en v3.2 — protege la corrección de la política zone_dwell_sessions:
--  el Asset Owner debe seguir viendo las zonas que cedió a un Partner.)
BEGIN;
SELECT plan(1);

SET LOCAL app.current_tenant_id = '00000000-0000-4000-8000-0000000000a1';
SET LOCAL app.current_partner_id = '';
SET LOCAL app.current_actor_role = 'admin';

SELECT ok(
  (SELECT count(*) FROM zone_dwell_sessions zds JOIN zones z ON z.id = zds.zone_id
     WHERE z.owner_type = 'PARTNER'
       AND z.owner_partner_id = '00000000-0000-4000-8000-0000000000d1') > 0,
  'El Asset Owner conserva visibilidad de las zonas cedidas a sus Partners (Flujo 3)'
);

SELECT * FROM finish();
ROLLBACK;
```

```sql
-- tests/isolation/05_partner_can_write_finding.sql
-- (Nuevo en v3.3 — protege el fix de agent_findings_write: un subagente en sesión
--  de Partner DEBE poder escribir un hallazgo; antes fallaba silenciosamente.)
BEGIN;
SELECT plan(2);

SET LOCAL app.current_tenant_id  = '';
SET LOCAL app.current_partner_id = '00000000-0000-4000-8000-0000000000d1';
SET LOCAL app.current_actor_role = 'viewer';

-- 1) INSERT en contexto Partner: no debe lanzar excepción de RLS.
SELECT lives_ok($$
  INSERT INTO agent_findings (tenant_id, partner_id, site_id, task_type, summary, detail, run_id)
  VALUES ('00000000-0000-4000-8000-0000000000a1',
          '00000000-0000-4000-8000-0000000000d1',
          '00000000-0000-4000-8000-0000000000b1',
          'stock_audit', 'quiebre góndola lácteos', '{}'::jsonb, gen_random_uuid())
$$, 'Subagente en sesión de Partner puede escribir un hallazgo de su propio partner');

-- 2) Escribir un hallazgo atribuido a OTRO tenant debe ser rechazado por RLS.
SELECT throws_ok($$
  INSERT INTO agent_findings (tenant_id, partner_id, task_type, summary, detail, run_id)
  VALUES ('00000000-0000-4000-8000-0000000000a2',
          '00000000-0000-4000-8000-0000000000d1',
          'stock_audit', 'x', '{}'::jsonb, gen_random_uuid())
$$, '42501', 'Un Partner no puede escribir hallazgos atribuidos a otro tenant');

SELECT * FROM finish();
ROLLBACK;
```

```sql
-- tests/isolation/06_management_tables_isolation.sql
-- (Nuevo en v3.3 — cubre el RLS de las tablas de gestión recién escrito.)
BEGIN;
SELECT plan(3);

-- Partner no ve partners ajenos de su mismo tenant.
SET LOCAL app.current_tenant_id = '';
SET LOCAL app.current_partner_id = '00000000-0000-4000-8000-0000000000d1';
SET LOCAL app.current_actor_role = 'viewer';
SELECT is(
  (SELECT count(*) FROM partners WHERE id <> '00000000-0000-4000-8000-0000000000d1')::int,
  0, 'Un Partner nunca ve la existencia de otros Partners del mismo tenant');

-- Operator acotado a Zona 10 no ve cámaras de Zona 4.
SET LOCAL app.current_tenant_id = '00000000-0000-4000-8000-0000000000a1';
SET LOCAL app.current_partner_id = '';
SET LOCAL app.current_actor_role = 'operator';
SET LOCAL app.current_user_site_ids = '00000000-0000-4000-8000-0000000000b2';
SELECT is(
  (SELECT count(*) FROM cameras)::int, 0,
  'Operator asignado a Zona 4 no ve cámaras (que están en Zona 10)');

-- agent_run_metrics: tabla interna, cero filas para cualquier rol de aplicación.
SET LOCAL app.current_tenant_id = '00000000-0000-4000-8000-0000000000a1';
SET LOCAL app.current_actor_role = 'admin';
SELECT is(
  (SELECT count(*) FROM agent_run_metrics)::int, 0,
  'agent_run_metrics es interna: deny-by-default para todo rol de aplicación');

SELECT * FROM finish();
ROLLBACK;
```

**Pipeline de migraciones con rollback:** cada cambio de esquema/política vive como
un par de archivos versionados `NNN_descripcion.up.sql` / `NNN_descripcion.down.sql`
(herramienta agnóstica — Sqitch, Flyway o `node-pg-migrate` funcionan igual de bien
sobre este patrón). El pipeline de CI, en orden:

1. Levanta una instancia Postgres efímera con las extensiones del proyecto
   (`pg_partman`, `pgcrypto`, `citext`) — la misma topología de Supabase.
2. Corre todas las migraciones `up` en orden.
3. Corre la suite pgTAP completa (los seis tests de arriba y sus variantes) — si
   falla cualquiera, el pipeline se detiene, **no se promueve el ambiente**.
4. Como prueba de reversibilidad real (no solo un archivo `down.sql` de adorno):
   aplica la última migración, la revierte (`down`), y la vuelve a aplicar (`up`) —
   si algún paso falla, el pipeline se detiene igual.
5. **Gate de calidad del Copiloto/Enjambre (nuevo, v3.2):** antes de la promoción
   Staging → Prod, corre la suite de evaluación del Copiloto (Sección 12.9) —
   ~20 casos golden por vertical activo, calificados por LLM-as-judge con rúbrica,
   más revisión humana del reporte de evaluación. Aplica cuando el release toca
   prompts, herramientas MCP, versión de modelo o lógica agéntica; un release
   puramente de esquema puede saltar este gate con aprobación explícita.
6. Solo si 1-5 pasan, el pipeline promueve la migración al siguiente ambiente
   (Dev → QA → Staging → Prod, con aprobación manual explícita antes de Prod).

**Ambiente dedicado de pruebas de carga/performance:** instancia sizada como una
fracción representativa de Prod (mismo tipo de instancia, menor capacidad), sometida
a carga sintética con `k6` o `Locust` apuntando a `POST /v1/telemetry/ingest`
simulando el volumen esperado (N Edge Gateways × M eventos/segundo cada uno), y
validando que el particionamiento nativo + retención de `pg_partman` y el job de
tiering a Glacier (Sección 8.6) no degraden la latencia de las vistas agregadas de
8.1 a medida que crece el
histórico.

**Ambiente piloto para cambios de configuración del Edge (`bytetrack.yaml`):** los
Edge Gateways marcados `channel = 'canary'` en la tabla `edge_gateways` (columna
agregada en el DDL de 8.0) reciben cualquier cambio de configuración de tracking
(ej. ajustes de `bytetrack.yaml` — umbrales de Filtro de Kalman, frames de oclusión
tolerados) antes que la flota `stable`. Promoción a `stable` requiere: (a) un período
mínimo de observación (ej. 48-72h) sin incremento de errores en el heartbeat de
salud, y (b) aprobación manual — este es el mismo mecanismo de rollback Blue/Green
ya descrito en la Sección 7.1, aplicado ahora también a config, no solo a código o
modelo.

---

#### 8.5 Operación Interna y Acceso Administrativo

**Rol "break-glass" para soporte/ingeniería (acceso cross-tenant auditado):**

```sql
CREATE TABLE platform_admins (
    id      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email   CITEXT NOT NULL UNIQUE,
    status  TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','disabled'))
);

CREATE TABLE break_glass_audit_log (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    platform_admin_id   UUID NOT NULL REFERENCES platform_admins(id),
    reason              TEXT NOT NULL,
    ticket_id           TEXT NOT NULL,
    tenant_id_accessed  UUID,
    started_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    ended_at            TIMESTAMPTZ
);
```

El flujo obligatorio es: (1) la aplicación **inserta primero** una fila en
`break_glass_audit_log` con `reason`, `ticket_id` y `tenant_id_accessed` no nulos —
sin esto, no hay forma de generar el permiso; (2) solo entonces la aplicación fija
la GUC `app.break_glass_admin_id`; (3) una política adicional, presente únicamente
en las tablas donde el soporte puede necesitar mirar datos de un tenant específico,
permite el `SELECT` mientras exista una sesión de break-glass activa **para ese
tenant en particular**:

```sql
-- Corrección v3.2 (defecto de seguridad): la versión anterior otorgaba acceso a
-- TODOS los tenants mientras existiera cualquier sesión break-glass abierta, y no
-- verificaba el timeout en la propia política. Esta versión: (a) acota el acceso
-- exactamente al tenant declarado en la auditoría (tenant_id_accessed pasa a ser
-- NOT NULL); (b) impone el timeout duro de 4 horas en la política misma, de modo
-- que una sesión "olvidada" expira aunque el proceso que debía cerrarla muera.
ALTER TABLE break_glass_audit_log ALTER COLUMN tenant_id_accessed SET NOT NULL;

CREATE POLICY tracking_coordinates_break_glass ON tracking_coordinates
FOR SELECT
USING (
  current_setting('app.break_glass_admin_id', true) IS NOT NULL
  AND current_setting('app.break_glass_admin_id', true) <> ''
  AND EXISTS (
    SELECT 1
    FROM break_glass_audit_log b
    JOIN platform_admins pa ON pa.id = b.platform_admin_id AND pa.status = 'active'
    JOIN cameras c ON c.id = tracking_coordinates.camera_id
    JOIN sites   s ON s.id = c.site_id
    WHERE b.platform_admin_id = current_setting('app.break_glass_admin_id', true)::UUID
      AND b.tenant_id_accessed = s.tenant_id
      AND b.ended_at IS NULL
      AND b.started_at > now() - interval '4 hours'
  )
);
```

`ended_at` se fija al cerrar la sesión; el timeout duro de 4 horas queda además
garantizado dentro de la política (defensa en profundidad: aunque el cierre
aplicativo falle, el permiso muere solo). Las tablas `platform_admins` y
`break_glass_audit_log` operan también con `FORCE ROW LEVEL SECURITY` y sin
política de lectura para roles de aplicación — solo el rol interno de la plataforma
las consulta; un tenant o partner jamás puede enumerar sesiones de soporte.

**Retención y purga de `tracking_coordinates`:** la política de negocio (13 meses
para telemetría analítica, 30 días para snapshots en S3, Sección 10.2) se implementa
técnicamente sobre particionamiento nativo + `pg_partman` — el DDL completo, la
justificación del cambio desde TimescaleDB y la mitigación de la pérdida de
compresión columnar están en la **Sección 8.6**. La purga de snapshots en S3 se
gestiona vía lifecycle policy del bucket, no en SQL.

**Backup/DR con verificación de RLS post-restore:** los backups (PITR del proveedor
gestionado) capturan el estado del esquema, incluyendo las políticas RLS. El riesgo
real no es que el backup pierda las políticas — es que un **restore manual mal
scripteado** (ej. un `pg_restore` parcial, o una migración manual de emergencia)
deje una tabla con RLS deshabilitado sin que nadie lo note hasta que ya es tarde.
Por eso, **ningún restore se considera terminado hasta que la suite pgTAP completa
de la Sección 8.4 corre en verde contra la instancia restaurada** — esto aplica
tanto a un simulacro de DR programado como a un incidente real.

**Cifrado de credenciales sensibles (`cameras.rtsp_url`):** el DDL de 8.0 ya refleja
esta decisión — no existe una columna `rtsp_url` en texto plano. Se usa cifrado por
sobre (envelope encryption) vía KMS: la aplicación cifra la URL con una Data
Encryption Key (DEK) antes de insertar, guarda solo el `rtsp_url_ciphertext` (BYTEA)
y el `rtsp_url_key_id` (referencia al key id de KMS usado para envolver la DEK) —
la base de datos nunca ve la credencial en claro ni la clave de descifrado. Como
alternativa más simple para una primera iteración del MLP, `pgcrypto`
(`pgp_sym_encrypt`/`pgp_sym_decrypt`) con la clave simétrica inyectada solo en
tiempo de ejecución (nunca en el esquema) es aceptable, a costa de que la DB sí
participa en el cifrado/descifrado.

**Observabilidad — accesos denegados, salud del tracker, alertas:** una limitación
real de RLS en Postgres es que un `SELECT` bloqueado por una política simplemente
devuelve cero filas — no genera una alerta ni queda "denegado" en ningún log por
defecto. Por eso el aislamiento de tres niveles se defiende en dos capas, no una
sola:

* **Capa API (control primario y auditable):** el backend valida la propiedad del
  recurso solicitado (`tenant_id`/`site_id`/`partner_id` del token contra el
  recurso pedido) **antes** de tocar la base de datos, y registra como evento de
  seguridad cualquier intento fuera de alcance — este es el log que efectivamente
  se puede alertar (ej. "Partner X intentó pedir el `zone_id` de un competidor").
* **Capa RLS (defensa en profundidad, silenciosa por diseño):** cubre el caso de un
  bug en la capa API o una query directa a la base — nunca debería dispararse en
  operación normal, así que si el conteo de "cero filas por RLS" diverge del
  conteo esperado por la capa API, es señal de que algo en la capa API está mal.
* **Salud del tracker y de la flota:** `edge_gateways.last_heartbeat_at` y
  `status` (ya definidos en 8.0) alimentan una alerta simple: `now() -
  last_heartbeat_at > umbral` dispara "Edge Gateway offline". Se complementa con
  el conteo de fallos de descarga de modelo (Model Manager, Sección 7) y la
  versión de modelo activa por Edge Gateway, para detectar flota "atascada" en una
  versión vieja tras un release.

---

#### 8.6 Capa Time-Series sobre Postgres Nativo + pg_partman (reescrita v3.3)

**Decisión bloqueante de portabilidad.** Versiones anteriores de este documento
construían `tracking_coordinates` como una *hypertable* de TimescaleDB. Verificado
contra la documentación oficial de Supabase (2026-07): **TimescaleDB está deprecado
para proyectos nuevos de Supabase** — solo sigue disponible en proyectos antiguos
creados sobre PostgreSQL 15, y con soporte hasta ~mayo 2026; los proyectos nuevos
(PostgreSQL 17) no lo ofrecen. Como el destino de hosting de bajo costo y el
fallback del proyecto es Supabase free tier — y como el mismo esquema debe correr
idéntico en Supabase, RDS y el Postgres local de la computadora de respaldo (esto es
una decisión de **portabilidad**, no solo de costo) — la capa time-series se
rediseña sobre **particionamiento declarativo nativo de PostgreSQL + `pg_partman`**,
que usa solo lo que las tres plataformas ofrecen.

**Modelo de particionamiento.** `tracking_coordinates` se declara
`PARTITION BY RANGE ("time")` (DDL en 8.0). `pg_partman` automatiza lo que antes
hacían `create_hypertable` + `add_retention_policy`: crea particiones futuras por
anticipado y elimina las que exceden la retención. La configuración (validada contra
la documentación de pg_partman 5.x):

```sql
-- create_parent: crea la partición DEFAULT y las particiones del rango inicial,
-- y registra la tabla en partman.part_config para mantenimiento automático.
SELECT partman.create_parent(
  p_parent_table := 'public.tracking_coordinates',
  p_control      := 'time',
  p_interval     := '1 month',   -- una partición por mes
  p_premake      := 3            -- mantener 3 meses futuros creados por adelantado
);

-- Retención: 13 meses (equivale a add_retention_policy). retention_keep_table=false
-- hace DROP de la partición vencida en vez de solo desadjuntarla.
UPDATE partman.part_config
   SET retention = '13 months',
       retention_keep_table = false,
       infinite_time_partitions = true
 WHERE parent_table = 'public.tracking_coordinates';

-- El mantenimiento (crear futuras, purgar vencidas) lo dispara run_maintenance_proc.
-- En Supabase/self-hosted se agenda con pg_cron (disponible en Supabase); en RDS,
-- con un event scheduler externo. Cadencia diaria es suficiente para particiones
-- mensuales.
-- SELECT cron.schedule('partman-maintenance', '0 3 * * *',
--   $$CALL partman.run_maintenance_proc()$$);
```

**Pérdida explícita: compresión columnar automática.** TimescaleDB comprimía chunks
antiguos (>90% típico en este perfil de datos) y esa era, en v3.2, la palanca que
mantenía el almacenamiento dentro del rango de $15-27/sede/mes de la Sección 10.1.
Postgres nativo **no tiene un equivalente directo** a esa compresión columnar por
chunk. Mitigaciones, en orden de preferencia (ninguna toca RLS ni aislamiento):

1. **Compresión TOAST + tipos ajustados (gratis, primera línea).** `x`/`y` como
   `INTEGER` ya son compactos; `person_id` es el mayor consumidor. Donde el pipeline
   lo permita, migrar `person_id` a un entero por-cámara reduce fila y peso de
   índice. TOAST comprime valores grandes automáticamente. Recorte esperado modesto
   pero sin trabajo operativo.
2. **`pg_squeeze` en las particiones frías (disponible en self-hosted/RDS; en
   Supabase depende del plan).** Reorganiza y compacta particiones cerradas
   (>1 mes) sin bloqueo largo. No alcanza el ratio de Timescale, pero recupera
   bloat y mejora densidad.
3. **Tiering a S3 Glacier para el histórico >3 meses (la mitigación de costo
   real).** Como cada partición mensual es una tabla independiente, se puede
   `DETACH PARTITION` la de >3 meses, exportarla comprimida (`COPY ... TO PROGRAM
   'zstd'`) a S3 Glacier, y hacer `DROP`. El histórico interanual (para comparativos
   año contra año, Sección 10.2) se rehidrata bajo demanda — es lectura rara y no
   interactiva. Esto mueve el 80% del volumen (los meses fríos) a almacenamiento de
   ~$0.004/GB, dejando en Postgres solo los ~3 meses calientes.
4. **Particiones más pequeñas (semanales) si el patrón de acceso lo justifica** —
   mejora la poda de particiones (partition pruning) en consultas por rango de
   fechas, a costa de más objetos que gestionar.

**Reevaluación del presupuesto de almacenamiento (Sección 10.1):** con el tiering a
Glacier del punto 3, el costo de almacenamiento *caliente* en Postgres baja
respecto al escenario Timescale-comprimido (menos datos residentes), mientras el
histórico frío cuesta centavos. El rango de infraestructura de $15-27/sede/mes **se
mantiene**; la diferencia es operativa (un job de tiering en vez de una política de
compresión declarativa), no de orden de magnitud en costo. Se documenta como
trade-off, no como amenaza al modelo financiero.

**El RLS no cambia.** Las políticas de la Sección 8.3 se evalúan igual sobre una
tabla particionada — Postgres aplica RLS a nivel de la tabla padre y lo propaga a
todas las particiones. La suite pgTAP de la Sección 8.4 corre contra la tabla
particionada (con al menos dos particiones pobladas) en el ambiente de pruebas de
carga, para verificar que la poda de particiones no altere el comportamiento de
aislamiento. La política de INSERT de ingesta (`tracking_coordinates_ingest`,
Sección 8.3) también se propaga sin cambios.

**Reconciliación de timestamps (Sección 9) intacta:** la inserción de telemetría
con timestamp UTC antiguo (llegada tardía por sincronización offline) enruta
automáticamente a la partición correcta por el valor de `"time"` — mismo
comportamiento que ofrecía la hypertable, sin código adicional. Si la data llega
tan tarde que su partición ya fue purgada por retención, el INSERT cae en la
partición DEFAULT (creada por `create_parent`); un chequeo periódico de la partición
DEFAULT no vacía alerta sobre data anómalamente tardía.

---

#### 8.7 Credenciales del Edge Gateway: MLP (Access + Refresh Token) y Fase 4+ (mTLS) —
reestructurada v3.4 (Sección 3.1, decisión 5)

Versiones anteriores (pre-v3.3) mencionaban "JWT/API Key" para la Service Account
del Edge Gateway (Sección 4) sin especificar almacenamiento, rotación ni
revocación — un gap de seguridad para un dispositivo que vive físicamente en la
sede del cliente y es, por tanto, el punto más expuesto de la arquitectura. v3.3
resolvió esto con una CA interna y certificados mTLS. La revisión de alcance del
MLP confirmó que **mTLS es más PKI de la que el MLP necesita**: el mecanismo que
sigue se construye una sola vez y cubre el MLP completo, con mTLS documentado como
evolución para cuando un vertical o cliente lo exija contractualmente — no un
prototipo a reemplazar después.

##### 8.7.0 MLP: Autenticación por Access Token + Refresh Token

**Mecanismo:** al canjear el código de activación de un solo uso (Flujo 1, paso 4,
o Flujo 7 para reemplazo), el backend emite un **access token** (JWT firmado,
stateless, 24h de vigencia, claims `edge_gateway_id`/`site_id`/`vertical_type`) y un
**refresh token** (opaco, 90 días de vigencia, su hash — nunca el valor en claro —
se persiste en `edge_gateways`). El Edge Gateway usa el access token para publicar
telemetría y consultar el Model Registry; cuando expira o le quedan pocas horas,
llama proactivamente a `POST /v1/edge/token/refresh` con el refresh token vigente
para obtener un par nuevo.

```sql
ALTER TABLE edge_gateways
  ADD COLUMN refresh_token_hash        TEXT,        -- hash (sha256), nunca el token en claro
  ADD COLUMN refresh_token_expires_at  TIMESTAMPTZ,
  ADD COLUMN last_token_refresh_at     TIMESTAMPTZ,
  ADD COLUMN replaced_edge_gateway_id  TEXT NULL REFERENCES edge_gateways(id);

-- Ampliación del enum de status para soportar baja/reemplazo (Flujo 7) — el mismo
-- enum sirve tanto para MLP (refresh token) como para Fase 4+ (mTLS, 8.7.1).
ALTER TABLE edge_gateways DROP CONSTRAINT IF EXISTS edge_gateways_status_check;
ALTER TABLE edge_gateways ADD CONSTRAINT edge_gateways_status_check
  CHECK (status IN ('online','offline','degraded','revoked','decommissioned'));

CREATE UNIQUE INDEX idx_edge_gateways_refresh_hash ON edge_gateways(refresh_token_hash)
  WHERE refresh_token_hash IS NOT NULL;
```

**Revocación real (Sección 3.1, decisión 5):** revocar un gateway es
`UPDATE edge_gateways SET status = 'revoked' WHERE id = ...` — sin tocar
certificados ni CRL. La query que ejecuta `POST /v1/edge/token/refresh` es la única
puerta de revocación, y rota el refresh token en cada uso (previene el reuso de un
refresh token robado):

```sql
UPDATE edge_gateways
   SET refresh_token_hash = $nuevo_hash,
       refresh_token_expires_at = now() + interval '90 days',
       last_token_refresh_at = now()
 WHERE id = $edge_gateway_id
   AND refresh_token_hash = $hash_del_token_presentado
   AND refresh_token_expires_at > now()
   AND status NOT IN ('revoked', 'decommissioned')
RETURNING id;
```

Si la query devuelve **cero filas** (token equivocado, expirado, o `status`
revocado/decomisionado), el backend rechaza el refresh con un único mensaje
genérico — no distingue la causa al cliente, para no filtrar cuál de las tres
condiciones falló. **Ventana de exposición tras revocar: máximo 24h** — el access
token vigente sigue funcionando hasta su propia expiración (es stateless, no se
puede invalidar antes sin mantener una lista de revocación adicional, que es
exactamente la complejidad que el MLP evita), pero el siguiente intento de refresh
—a más tardar en 24h— falla y el gateway queda sin forma de renovar acceso.

**Validado por ejecución (v3.4):** contra PostgreSQL 16, un gateway con
`status='online'` y hash correcto refresca exitosamente (1 fila, hash rotado); el
mismo intento con `status='revoked'` devuelve 0 filas aunque el hash y la
expiración sean válidos; un hash incorrecto o una expiración vencida también
devuelven 0 filas.

**Reemplazo de hardware (Flujo 7):** el gateway nuevo obtiene su propio par
access+refresh token al canjear el código de reemplazo; el gateway viejo pasa a
`status='decommissioned'`, lo que por sí solo ya bloquea cualquier refresh futuro
del hash viejo — no se requiere revocación de certificado porque no hay
certificado.

##### 8.7.1 Fase 4+: mTLS (gancho contractual, no descartado)

El mecanismo de certificado cliente mTLS ya diseñado y validado en v3.3 permanece
como la opción de mayor garantía para cuando un vertical o cliente lo exija
contractualmente (ej. banca, Sección 3.1 decisión 6). Se activa **sin rediseño**:
las columnas de abajo se agregan sobre el mismo `edge_gateways`, y el enum de
`status` ya definido en 8.7.0 sirve para ambos mecanismos sin cambios.

**Por qué mTLS es superior a un JWT de larga duración (motivo original, sigue
vigente para el caso Fase 4+):** un JWT de larga duración almacenado en la sede es
un secreto exfiltrable que sobrevive hasta su expiración. Un certificado cliente
mTLS: (a) sobrevive reinicios sin flujo de refresh (vive en el volumen de Docker);
(b) funciona idéntico en Windows/Linux/macOS; (c) permite revocación server-side
inmediata contra el estado en DB, sin esperar expiración (cero ventana de
exposición, vs. las ≤24h del mecanismo de refresh token del MLP); y (d) la clave
privada nunca viaja por la red (se genera localmente; solo el CSR sale al canjear
el código de activación).

**Emisión:** al canjear el código de activación, el Edge Gateway genera su par de
claves localmente y envía un CSR; el backend actúa como CA interna y emite el
certificado cliente, registrando su serial y expiración:

```sql
ALTER TABLE edge_gateways
  ADD COLUMN cert_serial     TEXT UNIQUE,
  ADD COLUMN cert_expires_at TIMESTAMPTZ;
```

**Revocación contra estado en DB (no solo criptográfica):** en cada handshake mTLS,
el backend valida el certificado criptográficamente **y además** consulta
`edge_gateways.status` para ese `cert_serial`. Si `status IN ('revoked',
'decommissioned')`, la conexión se rechaza aunque el certificado siga vigente —
mismo enum, mismo principio de revocación real que 8.7.0, solo que sin ventana de
exposición.

**Rotación automática antes de expiración:** los certificados se emiten con
vigencia acotada (ej. 90 días). El Edge Gateway llama proactivamente a un endpoint
de renovación (`POST /v1/edge/cert/renew`, autenticado con el certificado aún
vigente) cuando le quedan ~2 semanas — obtiene un certificado nuevo sin
intervención manual y sin ventana de desconexión. Si el gateway estuvo offline y su
certificado expiró, el flujo de renovación cae de vuelta al canje de un código de
activación nuevo (misma mecánica de reemplazo del Flujo 7).

**Nota de operación interna:** la CA interna y su clave privada son un activo de
plataforma; viven en el mismo KMS que envuelve las DEKs de `cameras.rtsp_url`
(Sección 8.5), nunca en el esquema ni en el código. La rotación de la CA raíz es un
procedimiento documentado aparte (fuera del MLP, pero la arquitectura de emisión no
lo impide).

---

### 9. APIs, Sincronización y Solución Offline (Offline-Sync Resolution)

El sistema de sedes es propenso a caídas de internet. El Edge Gateway nunca debe
perder métricas. Para garantizar la estabilidad a largo plazo y evitar que
actualizaciones en el backend rompan los Edge Gateways ya desplegados en campo,
**los endpoints seguirán un versionado semántico estricto (ej. `/v1/`, `/v2/`).**

#### Mecanismo de Cola Persistente Local

* **Base de Datos Local:** el Edge Gateway incrustará una base de datos ligera y
  veloz, como **SQLite** o **RocksDB**. Cada inferencia calculada se inserta primero
  en esta cola local.
* **Worker de Envío (Asíncrono):** un hilo separado lee por lotes desde SQLite y hace
  `POST` a la nube. Si recibe `HTTP 200 OK`, elimina el lote de la cola local.
* **Política de Reintentos:** si la nube no responde, el worker aplica un
  *Exponential Backoff* antes de reintentar, para no saturar la red local cuando
  vuelva la conexión.
* **Política de Evicción (Descarte):** para evitar que el disco duro de la
  computadora del comercio se llene, SQLite tendrá un límite duro (ej. retención de
  7 días). Si se supera, se borrarán los registros más antiguos (FIFO).
* **Reconciliación de Timestamps:** como el Timestamp se estampa en UTC en el
  momento exacto de la inferencia local, la tabla particionada enruta la data
  antigua a la partición mensual correspondiente por el valor de `"time"` (Sección
  8.6), sin afectar la integridad de los gráficos históricos en el dashboard.

#### 9.1 Descargas OTA Resumibles y Expiración de URL Firmada (nueva, v3.3)

El Model Manager del Edge Gateway (Secciones 5, 7, 7.1) descarga checkpoints `.pt`
(6-13 MB, Sección 7.2) desde una URL firmada de S3 (`GET /v1/models/{vertical_type}/
manifest` devuelve la URL, Sección 9 más abajo). Especificación de robustez:

* **Reanudación por `Range` (sin trabajo de servidor):** las URLs firmadas de S3
  soportan nativamente el header `Range`. El worker de descarga persiste el offset
  de bytes recibidos en la cola local (SQLite) y, tras un corte, reanuda con
  `Range: bytes=<offset>-` en vez de reiniciar — crítico en las conexiones
  intermitentes típicas de las sedes de CENAM.
* **TTL de la URL firmada: 1 hora.** Suficiente incluso para el peor caso de
  descarga de 13 MB sobre un enlace lento; no se justifica un TTL mayor que
  ampliaría la ventana de exposición de la URL.
* **Manejo de expiración a mitad de descarga:** si la URL vence antes de completar
  (respuesta `403` de S3 por firma expirada), el worker **no reintenta la URL
  vencida** — vuelve a pedir el manifiesto (`GET /v1/models/{vertical_type}/
  manifest`) para obtener una URL fresca, y reanuda desde el offset ya descargado
  con `Range`. El reintento usa el **mismo backoff exponencial** de la cola de
  telemetría (Sección 9, "Política de Reintentos"), por consistencia de patrón —
  un solo mecanismo de backoff en todo el Edge Gateway.
* **Integridad al final:** completada la descarga (nueva o reanudada), el Model
  Manager valida el checksum SHA256 contra el del manifiesto **antes** de reemplazar
  el checkpoint activo (patrón blue/green a nivel de modelo, Sección 7.1). Un
  archivo reensamblado de fragmentos con un byte corrupto se detecta aquí y dispara
  una descarga limpia desde cero.

#### API Interna (Edge hacia Cloud)

**`POST /v1/telemetry/ingest`**

* **Payload (JSON Batch):**

```json
{
  "edge_id": "nodo_win10_gt_01",
  "events": [
    {"timestamp": "2026-07-16T19:02:21Z", "cam_id": "cam_01", "p_id": "4022", "x": 450, "y": 720}
  ]
}
```

#### API de Distribución de Modelos (nuevo)

**`GET /v1/models/{vertical_type}/manifest`**

* Llamada por el Model Manager del Edge Gateway al iniciar o al recibir una
  notificación de nueva versión disponible.
* **Respuesta (JSON):**

```json
{
  "vertical_type": "retail",
  "version": "1.3.0",
  "download_url": "https://s3.amazonaws.com/.../yolo_retail_1.3.0.pt?signed=...",
  "checksum_sha256": "a1b2c3...",
  "released_at": "2026-06-01T00:00:00Z"
}
```

* El Edge Gateway descarga el archivo, valida el checksum, y solo entonces reemplaza
  el checkpoint activo en memoria (patrón blue/green a nivel de modelo, coherente con
  el mecanismo de rollback descrito en la Sección 7.1).

#### API de Gestión de Partners (nuevo, uso del Asset Owner)

**`POST /v1/tenants/{tenant_id}/partners`** — crea un nuevo Partner.

**`PATCH /v1/tenants/{tenant_id}/partners/{partner_id}/zone-access`** — asigna o
revoca el acceso de un Partner a una o más `zone_id` (o a una `site_id` completa,
lo que reasigna todas sus zonas de una vez — ver Sección 8.3), cambiando
`owner_type`/`owner_tenant_id`/`owner_partner_id` según corresponda en la tabla
`zones`. Solo invocable por un `Tenant Admin` autenticado del `tenant_id` dueño de
esas zonas — el backend valida la cadena `zones.camera_id → cameras.site_id →
sites.tenant_id` antes de permitir la reasignación, y esa misma validación es la
que además queda registrada como evento de seguridad si alguna vez no coincide
(Sección 8.5).

---

### 10. Requisitos No Funcionales y Economía Unitaria

#### 10.1 Estimación de Economía Unitaria (Costos por Sede / Mes) — Modelo B2B2B

Para validar la viabilidad del modelo SaaS bajo el nuevo esquema comercial, a
continuación se presentan estimaciones de referencia. **El Asset Owner es el único
que paga a la plataforma**; el ingreso adicional que obtiene revendiendo sub-accesos
a sus Partners es, para efectos de nuestra economía unitaria, un incentivo de
adopción y retención, no una línea de ingreso que factureamos directamente.

**Reescrita en v3.2.** La estimación anterior usaba un solo número de costo de IA
para todos los planes y un modelo de tokens optimista. Esta versión: (a) separa la
economía en **dos planes** con perfiles de costo de IA radicalmente distintos; (b)
modela el consumo de tokens del Enjambre Cognitivo con los **multiplicadores reales
documentados por Anthropic** en su ingeniería de sistemas multiagente ("How we
built our multi-agent research system"): los agentes individuales consumen **~4x**
más tokens que una interacción de chat simple, y los sistemas multiagente **~15x**
más; y (c) usa el pricing oficial vigente verificado (2026-07): Haiku 4.5 $1/$5
por MTok, Sonnet 4.6 $3/$15, Sonnet 5 $2/$10 (introductorio hasta 2026-08-31,
luego $3/$15), runtime de Managed Agents $0.08 por hora-sesión activa (solo estado
`running`), cache reads a 0.1x del precio de input, Batch API a 50% de descuento
(**no aplicable dentro de sesiones de Managed Agents** — verificado contra la
página oficial de pricing; esto condiciona la arquitectura de las cargas nocturnas,
ver abajo).

**Costos comunes a ambos planes:**

* **Infraestructura Cloud (v3.4: Supabase + Render/Cloud Run + Cloudflare R2 para
  el MLP; Sección 7/3.1 decisión 12):** balanceo, backend, PostgreSQL gestionado con
  particionamiento nativo + `pg_partman` y tiering del histórico frío a Cloudflare
  R2/Glacier equivalente (Sección 8.6, lo que hace sostenible la retención de 13
  meses sin la compresión columnar de Timescale), Model Registry (object storage +
  tráfico de descarga de checkpoints, infrecuente y de pocos MB): **~$15 - $27 USD
  / mes por sede**. AWS/RDS quedan como ruta de escalamiento para Fase 4+.
* **Ancho de Banda de Subida:** JSON en kilobytes + snapshots bajo demanda:
  **~$2 USD / mes por sede**.
* **Motor de Acciones (Sección 12.10) — fuera del COGS:** Slack, Telegram y correo
  tienen costo marginal cero y ya están incluidos en el rango de infraestructura de
  arriba. **WhatsApp Business API es un add-on opt-in cuyo costo de Meta se
  factura directamente al cliente como línea aparte** — nunca se absorbe en el COGS
  de la plataforma ni se mezcla con los rangos de este documento, precisamente para
  que el pricing de los planes de abajo no dependa de cuántos clientes eligen
  WhatsApp.

**Plan Base (capa operativa + Copiloto conversacional):**

* Supuesto de volumen: ~30 consultas/mes del Asset Owner al Copiloto + ~5
  consultas/mes por Partner activo (2 Partners típicos) + ~30 auditorías visuales
  de quiebre de stock/mes.
* Copiloto (Messages API directa, Haiku 4.5, agente individual con herramientas
  MCP): baseline de chat ~5K tokens × multiplicador 4x ≈ **20K tokens por
  consulta** (16K input / 4K output). 40 consultas/mes ≈ 640K input + 160K output
  ≈ **$1.4 - $2 USD/mes** (menos con cache hits sobre system prompt y tools).
* Auditorías visuales (Sonnet, agente individual, ~3 snapshots por auditoría a
  ~1.5K tokens de imagen c/u): ~25K input + 2K output por auditoría ≈ $0.11; ×30 ≈
  **$3.2 USD/mes** — o **~$1.6 USD/mes vía Batch API** (las auditorías del Plan
  Base no son interactivas: se ejecutan como lote nocturno sobre la Messages API,
  no sobre Managed Agents, precisamente para capturar el 50% de descuento).
* **COGS Plan Base: $20 - $35 USD / mes por sede.** El objetivo original de
  $22-41 se sostiene para este plan.

**Plan Enterprise (todo lo anterior + Enjambre Cognitivo diario + Copiloto en vivo):**

* Ejecución diaria del Enjambre (Managed Agents, orquestador + subagentes,
  Sección 12): baseline de chat ~5K tokens × multiplicador **15x** ≈ 75K tokens
  como piso teórico por corrida; el modelado central incluye además snapshots
  (visión) y resultados de herramientas: **~100K input + 12K output por corrida**
  (central) a **200K input + 25K output** (pesimista, sedes grandes con muchas
  zonas).
* Costo por corrida con Sonnet 4.6: central ≈ $0.30 input + $0.18 output + $0.04
  runtime (≈30 min `running`) ≈ **$0.52**; con prompt caching agresivo (system,
  tools y esquemas compartidos entre subagentes, ~60% del input servido de cache a
  0.1x) baja a **~$0.36**. Pesimista sin optimización: **~$1.06**.
* 30 corridas/mes: **$11 - $32 USD/mes por sede** solo el Enjambre.
* Copiloto en vivo con mayor volumen (Haiku 4.5): **$2 - $4 USD/mes**.
* **COGS Plan Enterprise: $30 - $65 USD / mes por sede.**

**Conclusión honesta del recálculo:** el Plan Enterprise con ejecución diaria del
Enjambre **no cabe** en el COGS objetivo original de $22-41/sede — el multiplicador
15x lo hace aritméticamente imposible en el extremo pesimista. Las opciones eran
tres: degradar el aislamiento/calidad (inaceptable — restricción no negociable),
mentirle al modelo financiero (inaceptable), o **re-preciar el plan que consume el
enjambre**. Se elige lo tercero:

* **Pricing Plan Base:** ~$150 - $200 USD / mes por sede (COGS $20-35 → margen
  bruto ≥ 80%). Incluye tableros operativos, Copiloto conversacional, auditorías
  nocturnas batch, y hasta 2 sub-accesos de Partner.
* **Pricing Plan Enterprise:** ~$400 - $500 USD / mes por sede (COGS $30-65 →
  margen bruto ≥ 84% incluso en el extremo pesimista). Incluye ejecución diaria del
  Enjambre Cognitivo, Copiloto en vivo priorizado y el Motor de Acciones (12.10).
  El precio se ancla comercialmente en el valor documentado por el mercado de
  referencia (Agrex.ai reporta reducciones de 20-30% en tiempos de cola de
  checkout; una sola mejora de ese orden en una sede de supermercado paga el plan
  varias veces).
* **Add-on de Reventa:** cada Partner adicional más allá del bundle: ~$25 - $40
  USD / mes por Partner activo — refleja el costo marginal real (consultas
  adicionales al Copiloto) sin convertirnos en el motor de facturación de la
  relación Asset Owner-Partner (exclusión de alcance, Sección 3).
* Con una sede promedio del Plan Base en $175 + 2 Partners adicionales (~$60), el
  ingreso ronda **$235 USD/mes** contra COGS de $20-35 (**margen > 80%**); una sede
  Enterprise en $450 + 2 Partners ronda **$510 USD/mes** contra COGS de $30-65
  (**margen > 85%**).
* *(Si el cliente requiere hardware en leasing, el costo del alquiler se transfiere
  a la tarifa mensual, igual que en el esquema original.)*

**Palancas de optimización que protegen estos márgenes sin tocar seguridad**
(ninguna debilita RLS ni el aislamiento por sesiones — restricción no negociable):

1. **Cadencia configurable del Enjambre:** el default Enterprise es diario, pero
   sedes de bajo tráfico pueden operar con enjambre profundo semanal + auditoría
   ligera diaria (agente individual, 4x en vez de 15x) — recorta el costo de IA
   ~60% sin cambio arquitectónico.
2. **Subagentes en Haiku 4.5:** las tareas de extracción/verificación de los
   subagentes (leer agregados vía MCP, revisar un snapshot puntual) corren en Haiku
   (5x más barato que Sonnet 4.6); Sonnet se reserva para el orquestador y la
   síntesis. (Patrón validado por el propio paper de Anthropic: orquestador capaz +
   workers más económicos.)
3. **Patrón de artefactos (Sección 12.7):** los subagentes devuelven referencias,
   no telemetría cruda — reduce el input del orquestador y de paso la superficie de
   exposición de datos.
4. **Prompt caching disciplinado:** system prompts y definiciones de herramientas
   congeladas byte-a-byte (el cache es prefix-match) — cache reads a 0.1x.
5. **Batch API para lo no interactivo:** toda carga nocturna que no necesite el
   sandbox/estado de Managed Agents corre como batch sobre la Messages API al 50%.
   Managed Agents se reserva para lo que genuinamente lo requiere (Sección 12.4).
6. **Sonnet 5 introductorio:** mientras rija el pricing de $2/$10 (hasta
   2026-08-31), el Enjambre puede correr en Sonnet 5 con ~33% de ahorro adicional
   sobre Sonnet 4.6; presupuestar siempre con el precio estándar $3/$15 para no
   construir el modelo financiero sobre una promoción.

#### 10.2 Postura de Seguridad y Cumplimiento (Baseline Comercial)

El objetivo de esta postura de seguridad es igualar el nivel de confianza comercial
que ofrecen líderes de la industria (como Agrex AI) sin recurrir a sobre-ingeniería
en la fase del MLP. El modelo B2B2B añade un requisito de aislamiento adicional que
se documenta explícitamente a continuación.

**Implementado desde el MLP (Baseline Operativo):**

* **Encriptación en Tránsito:** todas las comunicaciones entre el Edge y la Nube, y
  entre el Edge Gateway y el Model Registry, utilizan cifrado seguro mediante
  TLS/HTTPS.
* **Encriptación en Reposo:** las bases de datos cloud (PostgreSQL)
  operarán con *encryption at rest* nativo provisto por el cloud (ej. AWS RDS
  Encryption). El bucket S3 del Model Registry también opera con encryption at rest.
* **Control de Acceso Basado en Roles (RBAC) con Aislamiento de Tres Niveles
  (actualizado v3.2):** se utiliza el modelo Multi-Tenant `tenant → site → partner`
  definido en la Sección 4 (IAM) para
  garantizar tres cosas simultáneamente: (a) los datos de cada Asset Owner permanecen
  aislados de otros Asset Owners, (b) los datos de cada Partner permanecen aislados
  de otros Partners del mismo Asset Owner, y (c) un Partner nunca ve datos operativos
  del Asset Owner que no le fueron explícitamente compartidos vía el Módulo de
  Reventa. Dentro de cada Asset Owner, además, un usuario puede acotarse a una o
  varias sucursales específicas (rol `operator`/`viewer` regional); y un Reseller de
  canal no tiene acceso a telemetría de sus Tenants por defecto. El detalle de
  implementación (RLS, tablas físicas) vive en la Sección 8.
* **Política de Retención de Datos Explícita:** la telemetría analítica (coordenadas
  anonimizadas) se guarda por 13 meses para permitir comparativas interanuales. Los
  snapshots fotográficos utilizados para auditorías de IA se purgan de los
  servidores (S3) automáticamente tras 30 días.
* **Ventaja Diferencial (BYOD / Zero-Video Egress):** a nivel comercial, se
  comunicará agresivamente que, dado que el software opera dentro del propio
  hardware del comercio, **el video crudo nunca sale de la red local (LAN) del
  cliente**. Esta arquitectura nativa es funcionalmente equivalente o superior a la
  costosa opción "on-premise" que los competidores venden como feature premium,
  mitigando drásticamente el escrutinio de los departamentos de Ciberseguridad,
  independientemente del vertical del cliente (retail, banca o logística).

**Roadmap Futuro (NO es requisito del MLP):**

* **Certificación SOC 2 Type II:** este es un proceso de auditoría externa formal
  (no una simple implementación técnica) que toma entre 6 y 12 meses. Se recomienda
  perseguirlo **solo** cuando un cliente *Enterprise* lo exija explícitamente como
  condición contractual — el vertical banca, en particular, probablemente lo exija
  antes que retail o logística — y tras asegurar que los controles operativos ya son
  consistentes.
* **Cumplimiento GDPR / Leyes Locales Equivalentes:** dado que el MLP ya opera bajo
  el principio técnico de "Zero Biometrics" (sin extraer caras ni datos de
  identificación), la mayor parte de la barrera de cumplimiento ya está superada por
  diseño. Solo resta documentar formalmente las políticas legales de privacidad para
  cuando un cliente corporativo las solicite en fases de escalabilidad posteriores.

---

### 11. Riesgos Técnicos y Decisiones Abiertas

#### Decisiones Tomadas

* **Hardware Agnóstico:** el modelo base será correr software sobre hardware
  existente, con degradación de modelos (YOLO nano) para asegurar compatibilidad.
* **Tracking Local Limitado:** se usará ByteTrack intra-cámara, aceptando que una
  persona que sale y regresa será contada como un nuevo identificador.
* **Cliente Contractual Único (nuevo):** la plataforma solo contrata y factura al
  Asset Owner. Esto simplifica el modelo legal/comercial pero traslada al Asset Owner
  toda la responsabilidad de gestionar sus propios acuerdos con Partners — decisión
  deliberada para no asumir riesgo de intermediación de pagos ni de disputas
  comerciales entre terceros en el MLP.
* **Modularidad de Modelo, no de Código (nuevo):** la expansión a nuevos verticales
  se resuelve intercambiando un checkpoint `.pt`, nunca bifurcando el código del Edge
  Gateway o del backend. Cualquier feature que requiera lógica distinta por vertical
  (más allá de qué se detecta) queda fuera del alcance del Motor Base y debe
  evaluarse caso por caso antes de construirse.

#### Riesgos y Consideraciones

* **Calidad de Flujo (Artifacting):** si el NVR del cliente tiene pérdida de paquetes
  en la LAN, el RTSP llegará corrupto, generando "falsos negativos" en YOLO.
* **Riesgo de Propiedad Intelectual:** al estar inspirados funcionalmente en
  plataformas competidoras (ej. Agrex AI), existe el riesgo de mimetismo excesivo.
  **Mitigación:** es estricto que el diseño de UI/UX, nombres de producto,
  terminología de marketing (copywriting) y estructuración visual de los reportes se
  desarrollen desde cero. La inspiración es a nivel de *Business Logic* y problema
  resuelto, no de clonación de producto comercial.
* **Riesgo de Aislamiento Multi-Tenant de Dos Niveles (nuevo):** el nuevo modelo de
  datos introduce una superficie de fuga de datos más compleja que el esquema
  original (Asset Owner ↔ Partner, y Partner ↔ Partner). **Mitigación:** toda consulta
  a la Time-Series DB y a la API de Reventa debe validar `owner_type` + `owner_id`
  en el nivel de la capa de datos (no solo en la UI), y debe existir una suite de
  pruebas automatizadas de "fuga entre tenants" antes de cualquier release a
  producción (ver también el roadmap de ejecución técnica del proyecto).
* **Riesgo de Calidad Desigual Entre Verticales (nuevo):** `yolo_retail.pt` será el
  modelo más maduro por ser el vertical piloto; los checkpoints de verticales
  futuros (`yolo_banking.pt`, `yolo_logistics.pt`) probablemente requieran más
  iteración antes de alcanzar una precisión comercialmente aceptable. **Mitigación:**
  no comercializar un vertical nuevo hasta que su checkpoint pase el mismo umbral de
  validación que se exigió a retail antes de su lanzamiento.
* **Riesgo Comercial de la Relación Asset Owner-Partner (nuevo):** como la
  plataforma no media la relación comercial entre el Asset Owner y sus Partners
  (Sección 3), un Asset Owner podría sobre-prometer a sus Partners un nivel de
  servicio o SLA que la plataforma no garantiza contractualmente. **Mitigación:** los
  términos de servicio deben dejar explícito que el SLA de la plataforma aplica
  únicamente frente al Asset Owner; cualquier compromiso del Asset Owner hacia sus
  propios Partners es ajeno a nuestra responsabilidad contractual.
* **Riesgo de Acceso Interno No Auditado (nuevo, v3.0):** el equipo de soporte o
  ingeniería podría necesitar mirar datos de un tenant específico para depurar un
  incidente, lo que en principio contradice el aislamiento estricto. **Mitigación:**
  el mecanismo *break-glass* de la Sección 8.5 exige que la auditoría (motivo,
  ticket) se registre **antes** de que el acceso exista técnicamente, nunca después
  — y cierra automáticamente por timeout. Ningún ingeniero tiene acceso cross-tenant
  permanente por defecto.
* **Riesgo de Vistas que Omiten `security_invoker` (nuevo, v3.0):** cualquier vista
  o función futura sobre datos multi-tenant que se cree sin `security_invoker =
  true` (Sección 8.1) corre con los privilegios de quien la creó, no de quien la
  consulta — es la forma más fácil de introducir una fuga de aislamiento por
  accidente en un cambio aparentemente inocuo. **Mitigación:** la suite pgTAP de la
  Sección 8.4 debe incluir un test que enumere todas las vistas sobre tablas
  protegidas por RLS y falle si alguna no tiene `security_invoker = true`, no solo
  probar los casos de uso conocidos.
* **Riesgo de Desborde de Costo de Tokens del Enjambre (nuevo, v3.2):** los
  sistemas multiagente consumen ~15x los tokens de una interacción de chat (dato
  documentado por Anthropic, no estimación propia), y el consumo real por sede
  depende del número de zonas, snapshots y Partners activos — una sede atípica
  puede duplicar el modelo central de la Sección 10.1. **Mitigación:** (a)
  presupuesto de tokens por corrida a nivel de aplicación con corte duro y alerta
  cuando una sede excede 2x su promedio móvil; (b) telemetría de `model_usage` por
  sesión/thread (Sección 12.8) alimentando un tablero interno de COGS por sede;
  (c) las palancas 1-6 de la Sección 10.1 se aplican en orden antes de considerar
  cualquier cambio que toque aislamiento o calidad; (d) revisión mensual de
  pricing vigente de Anthropic (los precios citados fueron verificados 2026-07 y
  pueden cambiar).

---

### 12. Enjambre Cognitivo: Arquitectura sobre Claude Managed Agents (B2B2B)

Esta sección formaliza cómo la "Capa Agéntica (Enjambre Claude)" de la Sección 6 se
implementa concretamente sobre **Claude Managed Agents** (Anthropic, beta pública
desde abril 2026), y corrige un supuesto incorrecto que circuló en una iteración
paralela del documento de refactorización — verificado contra la documentación
oficial vigente, no contra la transcripción de esa discusión.

#### 12.1 Aislamiento Real: Sesiones Separadas, no Sub-Agentes de una Sesión

La documentación oficial de multiagent orchestration es explícita: **"All agents
share the same sandbox, filesystem, and vault credentials, but each agent runs in
its own session thread"** — lo único aislado entre sub-agentes de **una misma
sesión** es el hilo de conversación, no el acceso a archivos ni a credenciales. Los
`vault_ids` se fijan a nivel de sesión y aplican a todos los hilos de esa sesión por
igual.

**Corrección aplicada:** el gating de seguridad B2B2B **no puede** lograrse con
sub-agentes dentro de una sola sesión de Managed Agents — un sub-agente de "Trade
Marketing" de un Partner y un sub-agente de "Operaciones" del Asset Owner en la
misma sesión comparten sandbox y vault, técnicamente indistinguibles en cuanto a
acceso.

* **Mecanismo correcto:** una **sesión separada por contexto de aislamiento** —
  una sesión (con su propio `vault_ids` scoped) por Asset Owner, y una sesión
  distinta por cada Partner que interactúe con el Copiloto. Nunca se reutiliza la
  misma sesión/sandbox entre un Partner y su Asset Owner, ni entre dos Partners.
* **Uso correcto de multiagent orchestration:** sigue siendo válido *dentro* de un
  mismo contexto ya aislado — ej. el Tenant Admin pide "compara mis 40 sucursales"
  y el coordinador reparte el trabajo entre sub-agentes especializados, todos
  dentro del scope de ese mismo `tenant_id`, sin cruzar nunca hacia datos de un
  Partner.
* **Nota de madurez (actualizada v3.2, verificada contra documentación oficial):**
  multiagent orchestration **ya no está en research preview** — forma parte de la
  beta pública de Managed Agents (header `managed-agents-2026-04-01`), con estos
  límites documentados: el roster de subagentes se declara en el campo
  `multiagent: {type: "coordinator", agents: [...]}` del agente coordinador (no en
  `tools`), máximo 20 agentes en el roster, máximo 25 threads concurrentes por
  sesión, y **un solo nivel de delegación** (un subagente no puede delegar a su
  vez). Cada subagente corre en su propio *thread* con historial de conversación
  aislado, pero — y este es el punto de seguridad — **todos los threads de una
  sesión comparten el contenedor y el filesystem**, y los `vault_ids` se fijan a
  nivel de sesión y aplican a todos los threads por igual. La corrección de
  diseño de esta sección (aislamiento por sesiones separadas, no por subagentes)
  sigue siendo válida con el producto en beta pública; seguirá siendo válida en GA
  porque es una propiedad del modelo de datos del producto, no de su madurez.

#### 12.2 Punto de Conexión: Agente ↔ RLS de PostgreSQL

El agente **nunca** consulta PostgreSQL con credenciales propias ni con un
`tenant_id` que él mismo decida. El flujo correcto:

1. Nuestro backend, **antes** de crear la sesión Managed Agents, resuelve el
   contexto del usuario que la solicita (`tenant_id`/`site_id`/`partner_id`, igual
   que en la Sección 8.2) y lo asocia a un `vault_id` scoped a esa sesión.
2. El agente solo tiene acceso a un **MCP server interno** (propio, no de
   terceros) que expone `tracking_coordinates` / `zone_dwell_sessions` / vistas
   agregadas como *tools* (ej. `get_zone_dwell(zone_id)`), nunca acceso SQL directo.
3. El MCP server interno resuelve el contexto de autorización **del lado del
   servidor**, a partir del `vault_id` de la sesión (que fija las GUCs `SET LOCAL
   app.current_tenant_id...` de la Sección 8.2) — **no** a partir de ningún
   parámetro que el agente pase en la llamada al tool.

**Detalle verificado del mecanismo de vaults (refuerza este diseño):** en Managed
Agents, las credenciales de un vault **nunca entran al sandbox**. Las llamadas MCP
se enrutan por un proxy del lado de Anthropic que inyecta la credencial *después*
de que la petición sale del contenedor; el código que corre en el sandbox —
incluido cualquier código que el propio agente escriba — no puede leer ni exfiltrar
la credencial, ni siquiera bajo prompt injection. Cada credencial MCP está atada a
una URL de servidor específica, y las credenciales tipo `environment_variable`
aparecen dentro del sandbox como un placeholder opaco que solo se sustituye por el
valor real en el egreso, y únicamente hacia los hosts permitidos declarados en la
credencial. Implicación de diseño: el token de base de datos scoped por
tenant/partner vive en el vault de esa sesión, con `allowed_hosts` limitado al
host de nuestro MCP interno — un agente de un Partner no tiene forma técnica de
presentar la credencial de otro contexto, porque jamás la ve.

**Por qué esto es inmune a prompt injection:** aunque un snapshot con texto oculto,
o un mensaje de un Partner, intente instruir al agente para que "actúe como si
fuera otro tenant" o pida datos fuera de su alcance, el MCP server interno ignora
cualquier `tenant_id`/`partner_id` que el agente intente pasar explícitamente en la
tool call — el contexto de autorización nunca viaja en el prompt ni en los
argumentos de la herramienta, vive exclusivamente en el `vault_id` de la sesión que
nuestro propio backend fijó antes de que el agente recibiera un solo mensaje del
usuario. Es el mismo principio ya establecido en la Sección 8.5 ("toda consulta
debe validar propiedad en la capa API, no solo en la UI/prompt"), aplicado ahora
también a la capa agéntica.

#### 12.3 Nota de Compliance por Vertical

**Confirmado contra documentación oficial:** *"Managed Agents is not currently
eligible for Zero Data Retention or HIPAA Business Associate Agreement (BAA)
coverage"* — los datos de una sesión (historial de conversación, estado del
sandbox, outputs) se almacenan server-side por diseño al ser stateful.

**Matiz sobre self-hosted sandboxes (verificado contra documentación oficial
vigente):** los *self-hosted sandboxes* (`config: {type: "self_hosted"}` en el
environment de Managed Agents) son una vía **parcial** de mitigación: la ejecución
de herramientas — bash, operaciones de archivos, código — corre en un contenedor
que nosotros controlamos, mediante un worker de polling saliente (Anthropic nunca
abre conexiones hacia nuestra red), manteniendo filesystem y egreso "dentro del
perímetro". **Pero el "agent loop" (orquestación, razonamiento del modelo) sigue
corriendo en infraestructura de Anthropic**, y ese tráfico de tokens sigue sin
cobertura ZDR/BAA — self-hosted sandboxes resuelve *dónde vive la ejecución de
herramientas*, no la elegibilidad de ZDR/HIPAA BAA en sí misma. Dos limitaciones
operativas verificadas que afectan nuestro diseño si se adopta esta vía: (a) las
credenciales de vault tipo `environment_variable` **no están soportadas** en
self-hosted (la sustitución ocurre en el egreso gestionado por Anthropic, que aquí
no existe) — las credenciales del MCP interno deben mantenerse del lado del host
vía custom tools; (b) el montaje de recursos (`file`, `github_repository`) pasa a
ser responsabilidad nuestra. Para el MLP, el default es sandbox cloud de Anthropic;
self-hosted queda como opción de negociación para clientes banca que lo exijan.

**Restricción a validar antes de habilitar el Enjambre Cognitivo en banca:**
aunque el principio "Zero Biometrics" (coordenadas anonimizadas, no rostros) reduce
la sensibilidad del dato que pasaría por el agente, hay que confirmar con
compliance si la regulación bancaria local igual exige BAA para cualquier dato
asociado a una sucursal financiera, sin importar si es o no PII en sentido
estricto.

**Fallback sin Managed Agents:** para el vertical `banking` (o cualquier cliente
que bloquee esto), el Copiloto puede implementarse sobre la **Messages API
directa** (Sección 12.4) con el mismo patrón de MCP interno + RLS — se pierde
sesión larga/multi-tool autónomo, pero se mantiene el resto de garantías de
compliance ya vigentes de la plataforma (Sección 10.2).

#### 12.4 Arquitectura del "Copiloto en Vivo" vs. Tareas Asíncronas del Enjambre

Managed Agents está diseñado para sesiones largas, con estado persistente y tareas
autónomas multi-paso — no para la latencia conversacional sub-segundo de un chat
interactivo. **No se asume que Managed Agents cubre ambos casos con una sola
arquitectura:**

| Caso de uso | Arquitectura recomendada | Justificación |
| --- | --- | --- |
| **Copiloto en vivo** (chat interactivo, Flujo 4, Sección 5) | **Messages API directa** (no Managed Agents) | Interacción de baja latencia, pregunta-respuesta acotada; no necesita sandbox, sesión persistente ni multi-tool autónomo — solo contexto ya filtrado por RLS vía el MCP interno de 12.2. |
| **Auditoría de quiebre de stock / tareas del Enjambre** (asíncronas, multi-paso) | **Managed Agents** (o Batch API si la tarea no necesita sandbox — ver 12.5) | Encaja con el diseño: pedir snapshot, analizar, escribir hallazgo, sesión que persiste mientras corre. Se beneficia de sandboxing y de multiagent orchestration (ya en beta pública, ver 12.1) para paralelizar auditorías de varias zonas a la vez. |

**Resolución explícita de la tensión de latencia (nueva, v3.2).** El patrón
orquestador-subagentes es efectivamente síncrono desde la perspectiva del
resultado final: el orquestador espera a que los subagentes terminen antes de
sintetizar — minutos, no segundos. La decisión de este documento es **no** intentar
que el enjambre responda en vivo:

1. **El Copiloto en vivo usa un camino de baja latencia separado** (Messages API
   directa + streaming, Haiku 4.5, herramientas MCP de solo-lectura sobre
   agregados ya calculados). Promesa comercial: primera palabra en pantalla en
   ~1-3 segundos, respuesta completa < 15 segundos. El Copiloto en vivo **nunca
   dispara el enjambre** ni espera por él.
2. **El Enjambre de análisis profundo corre asíncrono y programado** — vía
   *scheduled deployments* de Managed Agents (cron nativo del producto: cada
   disparo crea una sesión nueva por contexto de aislamiento) o vía nuestro propio
   scheduler. Sus resultados se materializan en Postgres (patrón de artefactos,
   12.7) y llegan al usuario como hallazgos en el tablero, reportes y alertas del
   Motor de Acciones (12.10) — no como una respuesta de chat.
3. **El puente entre ambos:** cuando el Copiloto en vivo recibe una pregunta que
   requiere análisis profundo, responde con lo que ya existe (el hallazgo más
   reciente del enjambre, con su timestamp) y ofrece encolar una corrida profunda
   cuyo resultado se notifica al terminar. La promesa comercial se ajusta en
   consecuencia: "respuestas inmediatas sobre tus datos; análisis profundo entregado
   en minutos" — nunca se vende el enjambre como chat en tiempo real.

#### 12.5 Validación Financiera y Estrategia de Modelos (reescrita v3.2)

**Verificado contra la página oficial de pricing de Anthropic (2026-07):**

* Runtime de Managed Agents: **$0.08 USD por hora-sesión**, medido al milisegundo,
  facturado **solo mientras la sesión está en estado `running`** — el tiempo
  `idle` (esperando input o confirmación de herramienta) no cobra. Confirmado.
* Los tokens de la sesión se facturan a las tarifas estándar del modelo; prompt
  caching aplica normalmente (reads a 0.1x). Confirmado — y el ejemplo oficial de
  Anthropic (sesión de 1h en Opus: $0.625 de tokens vs $0.08 de runtime) confirma
  que **los tokens son ~85-90% del costo total**, no el runtime.
* **El descuento de Batch API (50%) NO aplica a sesiones de Managed Agents** —
  las sesiones son stateful e interactivas, no existe modo batch. Tampoco aplican
  fast mode ni el multiplicador de data residency. Confirmado explícitamente en la
  documentación de pricing. **Consecuencia arquitectónica:** las cargas nocturnas
  que no necesitan sandbox ni multi-tool autónomo (ej. las auditorías simples del
  Plan Base) se implementan como lotes sobre la Messages API/Batch API a mitad de
  precio; Managed Agents se reserva para el Enjambre del Plan Enterprise, que sí
  usa sandbox, sesiones persistentes y orquestación multiagente.
* Costos accesorios dentro de sesión: web search $10 por 1,000 búsquedas (el
  Enjambre no la usa por diseño — sus fuentes son la telemetría propia); web fetch
  sin cargo adicional.

**Estrategia de modelos vigente (Claude 3.5 Sonnet está retirado desde oct-2025 y
no debe aparecer en ningún código):**

| Carga de trabajo | Modelo | Justificación |
| --- | --- | --- |
| Copiloto en vivo (chat, Flujo 4) | **Claude Haiku 4.5** ($1/$5) | Latencia y costo mínimos; suficiente para Q&A sobre agregados vía MCP. |
| Orquestador del Enjambre + síntesis | **Claude Sonnet** (4.6 a $3/$15; Sonnet 5 a $2/$10 intro hasta 2026-08-31) | Razonamiento multi-paso y visión de snapshots con costo controlado. |
| Subagentes de extracción/verificación | **Claude Haiku 4.5** | Tareas acotadas de lectura y verificación; 3-5x más barato que el orquestador. |
| Auditorías batch nocturnas (Plan Base) | **Sonnet vía Batch API** ($1.50/$7.50 en 4.6) | 50% de descuento; no requieren sandbox. |
| Escalación puntual (casos ambiguos que el orquestador marca) | **Claude Opus 4.8** ($5/$25) | Solo bajo demanda explícita; nunca como default de COGS. |

Los IDs de modelo viven en configuración por ambiente (nunca hardcodeados), y el
pipeline de QA (12.9) corre la suite de evaluación completa antes de promover
cualquier cambio de modelo a producción.

El recálculo completo del COGS con el multiplicador multiagente de ~15x — y el
re-pricing del Plan Enterprise que resulta de él — está integrado en la Sección
10.1; esta sección queda como registro de las tarifas verificadas y de la
estrategia de modelos que alimenta ese cálculo.

#### 12.6 Paralelizabilidad por Subagente: Cuándo el Multiagente Vale sus 15x (nueva, v3.2)

El paper de ingeniería de Anthropic es explícito: los sistemas multiagente
sobresalen en tareas **paralelizables de exploración amplia** y desperdician
tokens (sin ganancia de calidad, a veces con pérdida) en tareas **secuenciales o
con dependencias fuertes de contexto compartido**. Evaluación de cada subagente
propuesto bajo ese criterio:

| Tarea propuesta | ¿Genuinamente paralelizable? | Veredicto de diseño |
| --- | --- | --- |
| **Visión y Planogramas** — auditar N zonas/góndolas de una sede con snapshots independientes ("¿hay quiebre de stock en la góndola X?") | **Sí.** Cada zona es independiente: snapshot propio, criterio propio, resultado propio. No comparten estado entre sí. | **Multiagente.** El orquestador reparte zonas entre subagentes (Haiku) que corren en paralelo y escriben su hallazgo vía el patrón de artefactos (12.7). Es el caso de libro de texto de breadth-first. |
| **Comparativo inter-sucursal** ("compara mis 40 sucursales") | **Sí**, en la fase de recolección: un subagente por lote de sucursales lee agregados vía MCP. La síntesis final es del orquestador. | **Multiagente en recolección, orquestador único en síntesis.** |
| **Trade Marketing** — generar el insight comercial del período para un Partner (tendencia de dwell time → hipótesis → recomendación) | **No.** Es una cadena secuencial donde cada paso depende del anterior y del contexto completo del Partner. Partirla en subagentes duplica contexto en cada uno (el costo 15x) sin paralelismo real que cosechar. | **Agente individual con pasos** (~4x, no 15x): un solo agente Sonnet que lee los artefactos ya producidos por el enjambre de visión y los agregados del período, y razona la narrativa completa con todo el contexto en una sola ventana. |
| **Redacción del reporte ejecutivo del período** | **No.** Coherencia narrativa exige una sola voz con visión completa. | **Agente individual**, consumiendo artefactos. |

**Regla de decisión para futuros subagentes:** un subagente nuevo se aprueba solo
si (a) sus unidades de trabajo son independientes entre sí, (b) el contexto que
necesita cada unidad es un subconjunto pequeño del contexto total (si cada
subagente necesita *todo* el contexto, el multiplicador es puro desperdicio), y
(c) el volumen de unidades justifica el overhead de orquestación (≥ ~5 unidades
por corrida como referencia). En caso contrario, la tarea se implementa como
agente individual con pasos.

#### 12.7 Patrón de Artefactos: Flujo de Datos Subagente ↔ Base de Datos (nueva, v3.2)

Los subagentes **no** devuelven telemetría cruda ni análisis extensos por el hilo
de conversación al orquestador. El flujo es:

1. Cada subagente escribe su resultado completo en Postgres mediante
   una herramienta MCP de escritura (`write_finding`), que ejecuta el INSERT bajo
   el mismo contexto RLS de la sesión (Sección 12.2) — el subagente de un tenant
   no puede escribir hallazgos atribuidos a otro tenant ni leer los de un Partner
   ajeno, porque las GUCs de la conexión ya están fijadas del lado del servidor.
2. El subagente devuelve al orquestador **solo una referencia ligera**: el
   `finding_id` y un resumen de una línea.
3. El orquestador sintetiza a partir de referencias y resúmenes; si necesita el
   detalle de un hallazgo específico, lo lee puntualmente vía MCP
   (`get_finding(finding_id)`), no lo arrastra por defecto.

```sql
-- Artefactos del Enjambre — misma disciplina RLS que el resto del esquema.
CREATE TABLE agent_findings (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id      UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    partner_id     UUID NULL REFERENCES partners(id) ON DELETE CASCADE,
    site_id        UUID NULL REFERENCES sites(id) ON DELETE CASCADE,
    zone_id        UUID NULL REFERENCES zones(id) ON DELETE SET NULL,
    task_type      TEXT NOT NULL,          -- 'stock_audit' | 'queue_analysis' | ...
    severity       TEXT NOT NULL DEFAULT 'info'
                   CHECK (severity IN ('info','warning','action_required')),
    summary        TEXT NOT NULL,          -- una línea; esto es lo que viaja al orquestador
    detail         JSONB NOT NULL,         -- hallazgo completo; se lee bajo demanda
    snapshot_s3_key TEXT,                  -- referencia, nunca la imagen inline
    run_id         UUID NOT NULL,          -- corrida del enjambre que lo produjo
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_agent_findings_tenant_run ON agent_findings(tenant_id, run_id);
CREATE INDEX idx_agent_findings_site ON agent_findings(site_id, created_at DESC);

ALTER TABLE agent_findings ENABLE ROW LEVEL SECURITY;
ALTER TABLE agent_findings FORCE ROW LEVEL SECURITY;

-- Lectura: mismo patrón de tres ramas de la Sección 8.3 (tenant ve lo suyo y lo
-- cedido; partner ve exclusivamente lo suyo; operator/viewer acotado por site).
CREATE POLICY agent_findings_read ON agent_findings
FOR SELECT USING (
  ( app_current_partner_id() IS NOT NULL
      AND agent_findings.partner_id = app_current_partner_id() )
  OR
  ( app_current_partner_id() IS NULL
      AND agent_findings.tenant_id = app_current_tenant_id()
      AND ( app_current_role() = 'admin'
            OR agent_findings.site_id = ANY (app_current_site_ids()) ) )
);

-- Escritura: solo dentro del contexto activo de la sesión agéntica.
-- Corrección v3.3: la versión anterior exigía SIEMPRE
-- `agent_findings.tenant_id = app_current_tenant_id()`. Pero en una sesión de
-- contexto PARTNER la convención (Sección 8.2 / test pgTAP 03) fija
-- app.current_tenant_id = '' (→ NULL), por lo que la comparación nunca era cierta
-- y un subagente en sesión de Partner NO PODÍA escribir un hallazgo. Se agrega la
-- rama Partner, derivando el tenant_id del hallazgo del tenant padre del partner.
CREATE POLICY agent_findings_write ON agent_findings
FOR INSERT WITH CHECK (
  -- Contexto tenant
  ( app_current_partner_id() IS NULL
      AND agent_findings.tenant_id = app_current_tenant_id() )
  OR
  -- Contexto partner: tenant_id derivado del padre, no de la GUC (que es NULL)
  ( app_current_partner_id() IS NOT NULL
      AND agent_findings.partner_id = app_current_partner_id()
      AND agent_findings.tenant_id = sec_partner_tenant(app_current_partner_id()) )
);
```

**Validado por ejecución (v3.3):** un subagente en sesión de Partner (`current_
partner_id = d1`, `current_tenant_id = ''`) ahora inserta correctamente un hallazgo
atribuido a su partner y al tenant padre; e intentar escribir un hallazgo atribuido
a *otro* tenant es rechazado por la política. El test pgTAP nuevo
`05_partner_can_write_finding.sql` (Sección 8.4) ejecuta este INSERT y confirma que
ya no falla.

**Beneficio doble, medible:** (a) *tokens* — el hilo del orquestador transporta
resúmenes de ~30 tokens en lugar de hallazgos de ~2-4K tokens; con 10-20
subagentes por corrida, esto recorta el input del orquestador en un orden de
magnitud y es una de las palancas que sostienen el COGS de la Sección 10.1; (b)
*seguridad* — los datos completos nunca transitan por el contexto conversacional
de ningún agente que no los necesite, reduciendo la superficie de exposición entre
Partners incluso dentro de sesiones correctamente aisladas. Los snapshots viajan
como claves S3, jamás inline entre agentes.

#### 12.8 Observabilidad del Enjambre sin Contenido Conversacional (nueva, v3.2)

Requisito en tensión: necesitamos trazabilidad operativa del Enjambre (¿por qué
esta corrida costó 3x?, ¿por qué este subagente falló?) sin registrar el contenido
de las conversaciones — que puede contener datos confidenciales del Asset Owner o
de un Partner, y cuya retención crearía un canal lateral entre contextos que el
RLS no gobierna. Resolución: **se persisten patrones de decisión y estructura de
interacción; nunca mensajes.**

Fuentes de datos (todas disponibles en la API de Managed Agents sin leer
contenido): los eventos `span.model_request_start`/`span.model_request_end` (este
último trae `model_usage`: input/output/cache tokens por request), los eventos de
estado de sesión y de threads (`session.thread_created`,
`session.thread_status_*`), la duración `running` de la sesión (base del costo
$0.08/h), y los resultados de outcome del grader (12.9).

```sql
-- Métricas por corrida — SIN columnas de contenido. La ausencia de un campo
-- "message"/"prompt"/"response" en este esquema es deliberada y se protege en
-- code review: agregar contenido conversacional aquí es un cambio de contrato
-- de privacidad, no una mejora de logging.
CREATE TABLE agent_run_metrics (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id              UUID NOT NULL,
    tenant_id           UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    partner_id          UUID NULL REFERENCES partners(id) ON DELETE CASCADE,
    session_ref         TEXT NOT NULL,      -- id de sesión CMA (identificador, no contenido)
    thread_count        INTEGER NOT NULL DEFAULT 0,
    model_requests      INTEGER NOT NULL DEFAULT 0,
    input_tokens        BIGINT NOT NULL DEFAULT 0,
    output_tokens       BIGINT NOT NULL DEFAULT 0,
    cache_read_tokens   BIGINT NOT NULL DEFAULT 0,
    running_seconds     INTEGER NOT NULL DEFAULT 0,
    tool_call_count     INTEGER NOT NULL DEFAULT 0,
    tool_error_count    INTEGER NOT NULL DEFAULT 0,
    findings_written    INTEGER NOT NULL DEFAULT 0,
    outcome_result      TEXT,               -- 'satisfied' | 'needs_revision' | ...
    started_at          TIMESTAMPTZ NOT NULL,
    ended_at            TIMESTAMPTZ
);
CREATE INDEX idx_arm_tenant_started ON agent_run_metrics(tenant_id, started_at DESC);

-- RLS de agent_run_metrics (decisión explícita v3.3): tabla EXCLUSIVAMENTE interna,
-- igual que platform_admins y break_glass_audit_log. FORCE RLS + SIN política de
-- lectura para roles de aplicación (deny-by-default total). Un tenant/partner nunca
-- consulta su propio consumo por esta tabla — las métricas por sesión/thread son
-- información operativa de la plataforma, no del cliente. Si el negocio decide
-- exponer COGS por sede al Asset Owner, se hará vía una VISTA AGREGADA separada
-- (ej. tokens/mes por site, sin detalle por corrida) con su propio security_invoker
-- y su propia política — no dando acceso directo a esta tabla.
ALTER TABLE agent_run_metrics ENABLE ROW LEVEL SECURITY;
ALTER TABLE agent_run_metrics FORCE ROW LEVEL SECURITY;
-- (Sin CREATE POLICY: solo el rol interno de la plataforma la consulta.)
```

**Por qué interna y no visible al tenant (decisión, no omisión):** exponer
`agent_run_metrics` directamente filtraría patrones de uso (a qué horas corre el
enjambre, cuántos threads, cuántos errores) que son detalle de implementación de la
plataforma, y crearía una segunda superficie a mantener bajo RLS sin valor para el
cliente. El dato que *sí* podría querer un Asset Owner — su costo agregado — se sirve
mejor por una vista de resumen con su propio contrato, dejando esta tabla como
telemetría operativa pura. Validado por ejecución: con RLS forzado y sin política, un
rol de aplicación obtiene cero filas.

Con esto, operaciones puede responder "¿qué sede está fuera de presupuesto de
tokens?", "¿qué proporción de corridas termina con hallazgos accionables?", "¿subió
la tasa de errores de herramienta tras el último release?" — sin que ningún
ingeniero (fuera de una sesión break-glass auditada, Sección 8.5) pueda leer qué
preguntó un Partner ni qué respondió su agente. Las alertas operativas (corrida
> 2x presupuesto, `tool_error_count` anómalo, sesión `running` > umbral) se
definen sobre esta tabla. Los IDs de sesión permiten, en un incidente real y solo
bajo break-glass, correlacionar con la traza que retiene Anthropic — la decisión
de *no* espejear esa traza en nuestra infraestructura es exactamente el punto de
esta sección.

#### 12.9 Evaluación de Calidad del Copiloto y del Enjambre (nueva, v3.2)

La suite pgTAP (8.4) prueba que el aislamiento no se rompa; nada probaba que las
*respuestas* fueran buenas. Metodología de evaluación de calidad, integrada como
gate del pipeline (paso 5 de la Sección 8.4):

1. **Conjunto golden inicial: ~20 casos por vertical activo**, representativos de
   consultas reales, definidos con el equipo comercial y actualizados con casos de
   producción anonimizados. Para retail (vertical piloto), la distribución de
   partida: 6 casos de footfall/tráfico ("¿cómo se comparó el tráfico de Zona 10
   vs Zona 4 esta semana?"), 4 de dwell time/planograma ("¿en qué góndola cayó más
   la permanencia?"), 4 de colas ("¿a qué horas se degrada el tiempo de espera en
   cajas?"), 3 de alcance/aislamiento en positivo ("como Partner, ¿qué veo de mis
   zonas?" — la respuesta debe cubrir exactamente su alcance), y 3 adversariales
   de negocio ("¿cómo le fue a la competencia en esta tienda?" — la respuesta
   correcta es un rechazo claro con explicación del alcance). Cada caso fija: la
   consulta, el contexto de datos sintéticos (semilla de 8.4), la respuesta de
   referencia y los criterios de aprobación.
2. **Evaluación LLM-as-judge con rúbrica explícita.** Un modelo evaluador (Sonnet,
   con temperatura de configuración estable) califica cada respuesta contra tres
   dimensiones, cada una con criterios binarios verificables — no "vibes":
   **exactitud** (¿los números citados coinciden con los datos sintéticos?, ¿las
   comparaciones son aritméticamente correctas?), **uso correcto de fuentes**
   (¿cada afirmación se apoya en datos realmente disponibles en el alcance del
   usuario del caso?, ¿cero datos inventados o fuera de alcance?), y
   **completitud** (¿responde lo preguntado?, ¿señala limitaciones relevantes,
   ej. datos parciales del período?). Umbral de release: 100% en uso de
   fuentes/alcance (un solo caso que cite datos fuera de alcance bloquea el
   release), ≥90% en exactitud, ≥85% en completitud.
3. **Revisión humana antes de cada release a producción:** una persona revisa el
   reporte del judge completo (no solo el score) y una muestra de respuestas —
   los jueces LLM fallan en modos correlacionados con los sistemas que evalúan, y
   la firma humana es el control de esa correlación. El reporte firmado queda
   adjunto al release.
4. **Para las tareas del Enjambre en producción**, se usa además el mecanismo
   nativo de *Outcomes* de Managed Agents (`user.define_outcome` + rúbrica): el
   grader integrado del producto evalúa cada corrida contra criterios verificables
   ("el hallazgo referencia un `finding_id` existente", "toda zona auditada tiene
   veredicto") e itera hasta satisfacerlos o agotar `max_iterations` — con sus
   resultados (`satisfied`/`needs_revision`/`failed`) registrados en
   `agent_run_metrics.outcome_result` (12.8) como señal continua de calidad, sin
   registrar contenido.
5. **Ciclo de vida del set:** todo bug de calidad reportado por un cliente se
   convierte en caso golden antes de cerrarse (regresión permanente), y el set se
   re-pondera trimestralmente contra la distribución real de consultas.

#### 12.10 Motor de Acciones: Paridad con la Capa Agéntica de Agrex.ai (nueva, v3.2)

**Brecha identificada (verificada contra el material público de Agrex.ai,
2026-07):** el competidor ya opera en producción una capa agéntica con (a)
consultas en lenguaje natural sobre datos históricos de video, (b) agentes de
monitoreo autónomo 24/7, y (c) **acciones automáticas sin humano en el loop**:
alertas por WhatsApp, Slack y SMS, actualización de sistemas ERP y disparo de
workflows de compliance; publica además métricas de referencia de 20-30% de
reducción en tiempos de espera de cola por alertas inteligentes de staffing.
Nuestro documento cubría (a) con el Copiloto, pero (b)/(c) solo existían como un
"Gestor de Eventos/Webhooks" sin especificación. Sin acciones automáticas, en un
head-to-head perdemos la demo. Especificación del **Motor de Acciones**:

* **Reglas de acción (deterministas, base del MLP):** el Asset Owner (y cada
  Partner, dentro de su alcance) define reglas umbral sobre los agregados y sobre
  `agent_findings`: "si la cola de cajas supera N personas por M minutos → alerta
  al gerente de turno"; "si la auditoría visual de quiebre de stock (Copiloto,
  Sección 12.4/12.5) escribe un hallazgo `action_required` en una zona de Nestlé →
  notificar al contacto del Partner". Evaluadas por el Motor Matemático en su mismo
  ciclo batch (1-5 min) — sin infraestructura nueva de streaming, coherente con la
  Sección 6. **Para el MLP, `agent_findings` se alimenta de la auditoría vía
  Messages API directa** (una fila por auditoría), no del Enjambre — mismo sumidero
  de datos (Sección 12.7) que reutiliza sin cambios cuando el Enjambre se active en
  Fase 4 y empiece a escribir muchas más filas por corrida.
* **Canales del MLP (reordenado v3.4 — Sección 3.1, decisión 7):** **Slack
  (incoming webhooks), Telegram (Bot API) y correo son el default, con costo
  marginal cero.** **WhatsApp Business API es opt-in desde el día 1** si el cliente
  lo prefiere (sigue siendo el canal de mayor adopción en CENAM) — pero su costo de
  Meta se refleja **explícitamente en la factura del cliente como línea aparte**,
  no se absorbe en el COGS de la plataforma (Sección 10.1). Roadmap: SMS y webhooks
  salientes genéricos para integración ERP (la actualización directa de ERP de
  terceros queda fuera del MLP; se expone el webhook firmado para que el cliente
  integre).
* **Plantillas de SOP de Compliance (nuevo, v3.4 — Sección 3.1, decisión 8):**
  mismo motor de reglas-por-umbral de arriba, con plantillas pre-configuradas que
  el Asset Owner activa por sede/zona sin escribir la regla desde cero:
  * **Personal no presente en zona de caja** durante horario operativo (umbral: cero
    detecciones en la zona `staff_area` de caja por más de N minutos en horario de
    apertura).
  * **Apertura/cierre fuera de horario** (primera/última detección de persona en la
    sede fuera de la ventana configurada).
  * **Cliente sin atender** (persona en zona de espera/caja por más de N minutos sin
    que se registre personal en la zona adyacente).
  No es una capacidad nueva del motor — son más filas de configuración de reglas
  sobre la misma infraestructura de umbral y canal ya construida. Plantillas
  adicionales por vertical (banca, logística) se agregan igual, sin tocar el motor.
* **Acciones originadas por el Enjambre — Fase 4 (paridad "agéntica" real, se
  activa junto con la Sección 12 completa):** los agentes no improvisan acciones —
  disponen de una herramienta MCP `trigger_action(rule_template, target, payload)`
  cuyo catálogo está acotado por tenant/partner vía el mismo scoping RLS de 12.2: un
  agente solo puede disparar acciones del catálogo de su propio contexto, hacia
  destinatarios registrados por ese contexto. "Sin humano en el loop" aplica a la
  *ejecución* (nadie aprueba cada alerta), no a la *definición* (todo tipo de acción
  y destinatario fue configurado explícitamente por un humano del tenant). Esto nos
  da el titular competitivo de Agrex — alertas automáticas accionadas por IA — con
  una superficie de riesgo acotada y auditable. **En el MLP, el mismo titular
  competitivo ya se cumple sin esta pieza:** las reglas deterministas de arriba más
  las plantillas de SOP producen exactamente el mismo tipo de alerta automática sin
  humano en el loop de ejecución — la diferencia de Fase 4 es que el *disparo* de
  la acción puede originarse en el razonamiento del agente, no solo en un umbral
  numérico.
* **Auditoría:** toda acción disparada se registra (regla/agente origen, contexto,
  canal, destinatario, timestamp, payload) en una tabla `action_log` bajo el mismo
  RLS — el Asset Owner audita todo lo suyo; cada Partner, lo propio.
* **Métricas de valor:** el tablero correlaciona alertas de cola con la evolución
  del tiempo de espera para que el cliente mida su propia mejora contra el
  benchmark de mercado (20-30%). Nuestras promesas comerciales citan el rango del
  mercado como referencia externa y las mediciones propias del cliente como
  evidencia — nunca inventamos un porcentaje propio sin datos.

Con 12.4 (Copiloto en lenguaje natural), 12.6-12.7 (enjambre de monitoreo
programado) y este Motor de Acciones, la plataforma iguala las tres capacidades
agénticas visibles de Agrex.ai, y las supera en el eje que ellos no tienen:
la reventa B2B2B con aislamiento de tres niveles garantizado en la base de datos.

#### 12.11 Alertas Escalonadas Antes de Pérdida de Datos Offline (nueva, v3.3)

La cola local persistente del Edge Gateway (SQLite) descarta por FIFO tras un límite
duro de retención (ej. 7 días, Sección 9). Si una sede queda sin internet varios
días, el riesgo no es solo "gateway offline" — es **pérdida irrecuperable de
telemetría** cuando la cola local se llena y empieza a evictar. Un aviso binario
"offline/online" no comunica esa urgencia creciente. Especificación de alertas
escalonadas, reutilizando la infraestructura existente:

Un job programado (misma cadencia batch del Motor Matemático, Sección 6) compara
`edge_gateways.last_heartbeat_at` contra umbrales graduados:

| Umbral sin heartbeat | Acción | Canal |
| --- | --- | --- |
| **Día 1** | Aviso no bloqueante en el tablero del Asset Owner | UI |
| **Día 3** | Correo al Asset Owner | Email |
| **Día 5** | **Alerta urgente** vía el Motor de Acciones (12.10) | WhatsApp/Slack |

La alerta del día 5 **no es una acción improvisada por un agente** — es una regla
pre-configurada del catálogo del Motor de Acciones (12.10), disparada por el job de
salud, no por el Enjambre. El mensaje debe indicar **explícitamente cuántos días
quedan antes de la pérdida irrecuperable** por evicción FIFO: p.ej. "Sede La Torre
Zona 10 sin conexión hace 5 días. La cola local retiene 7 días — se perderá
telemetría de forma irrecuperable en ~2 días si no se restablece la conexión."
Esto convierte un dato técnico (heartbeat viejo) en una acción clara para el
personal de la sede, que es exactamente el patrón de valor del Motor de Acciones.

La cadencia y los umbrales son configurables por tenant (una sede rural con
conectividad intermitente conocida puede tolerar umbrales más laxos que una sucursal
bancaria urbana). El job de salud ya existe en germen en la Sección 8.5
("Salud del tracker y de la flota"); esta sección lo formaliza con la escalera de
severidad y el puente al Motor de Acciones.

#### 12.12 Offboarding de Partner y Derecho al Olvido sobre `agent_findings` (nueva, v3.3)

Cuando un Asset Owner revoca a un Partner (`partners.status='revoked'`, Flujo 3),
hay que distinguir dos cosas que versiones anteriores mezclaban:

1. **Visibilidad del Asset Owner sobre los hallazgos del Partner revocado — ya
   resuelta por diseño.** La política `agent_findings_read` (Sección 12.7) da al
   Tenant Admin acceso a los hallazgos por `tenant_id`, sin importar el `partner_id`
   ni el estado del Partner. Es decir: revocar a un Partner **no** hace desaparecer
   los hallazgos históricos de la vista del Asset Owner — coherente con el mismo
   principio del Flujo 3 (el Asset Owner conserva siempre visibilidad sobre lo que
   ocurrió en su infraestructura). No se requiere ningún cambio para esto.

2. **Purga por solicitud legal (derecho al olvido) — requiere acción explícita y
   auditada.** Distinta del timer pasivo de retención de 13 meses (que sigue siendo
   el comportamiento por defecto si nadie invoca borrado). Cuando un Partner ejerce
   un derecho de supresión, se expone un endpoint dedicado y auditado:

   **`DELETE /v1/tenants/{tenant_id}/partners/{partner_id}/data`** — solo invocable
   por un Tenant Admin autenticado del `tenant_id` dueño (validación de la cadena
   `partner → tenant`), registrado como evento de seguridad. Purga:
   * las filas de `agent_findings` con ese `partner_id`;
   * las referencias a snapshots en S3 asociadas (`snapshot_s3_key`) — el objeto S3
     se borra vía la API de S3, no solo la referencia en DB;
   * opcionalmente, `zone_dwell_sessions` de las zonas que fueron exclusivas de ese
     Partner, según lo que exija la solicitud legal concreta.

   La operación es **idempotente y auditada** (queda registro de quién purgó qué y
   cuándo, en un log de supresiones que sobrevive a la purga misma — se guarda el
   hecho de la supresión, no el dato suprimido). El diseño distingue deliberadamente
   *retención por defecto* (13 meses, pasiva) de *supresión bajo demanda* (activa,
   auditada) para no borrar datos que el negocio aún necesita solo porque un Partner
   se dio de baja, ni retener datos que legalmente deben desaparecer solo porque el
   timer no venció.

---

### 13. Roadmap de Implementación por Fases

> **MLP recortado (v3.4 — Sección 3.1):** las Fases 1-3 de abajo son el MLP que se
> construye primero, reescritas para reflejar el recorte de madurez operativa que
> el cliente nunca ve. Estimado total: **8-13 semanas** (antes del recorte,
> 10-19 — detalle por fase en la Sección 3.1). Ningún feature de cliente se
> recorta; lo que cambia de fase a fase respecto a v3.3 es: credenciales del Edge
> por refresh token en vez de mTLS (Fase 1), Reseller/Flujo 6 sale por completo del
> plan de ejecución del MLP y queda diferido a v2.0 (ya no aparece en ninguna
> fase), y toda la maquinaria de Managed Agents se confirma exclusivamente en
> Fase 4.

1. **Fase 1: Tubería de Datos Básica, Model Manager, Esquema Físico y Pruebas
   Off-Spec (MLP Interno) — estimado 2-3 semanas**
   * *Objetivo:* instalar el Edge Gateway (Docker) en una computadora de oficina
     genérica vieja para testear el "Lowest Common Denominator". Integrar YOLO Nano +
     ByteTrack, **construir el Model Manager con soporte para un único vertical
     piloto (`yolo_retail.pt`)** — incluyendo desde el primer commit las **descargas
     OTA resumibles por `Range` y el manejo de expiración de URL firmada** de la
     Sección 9.1 (la conectividad intermitente de CENAM es la condición de
     operación normal, no un caso extremo, así que la robustez de descarga no se
     puede diferir) —, y probar el mecanismo de cola local offline (SQLite). **El
     aprovisionamiento del Edge Gateway usa autenticación por access token (24h) +
     refresh token (90 días)** (Sección 8.7.0, Sección 3.1 decisión 5) desde el
     primer Flujo 1 — sin PKI, revocación real vía `edge_gateways.status='revoked'`
     bloqueando el siguiente refresh (ventana máxima de exposición 24h). El
     mecanismo mTLS (Sección 8.7.1) queda documentado y validado en este mismo
     documento como gancho de Fase 4+, no se construye en Fase 1. En paralelo,
     **levantar el esquema físico completo de la Sección 8** (`tenants` → `sites` →
     `cameras` → `zones` → `tracking_coordinates` **particionada nativamente con
     `pg_partman`, Sección 8.6** — no como hypertable de TimescaleDB, portable a
     Supabase/Render/Cloud Run desde el día uno (Sección 3.1 decisión 12) —, más
     `users`/`user_site_assignments`/`partners` con su columna
     `access_expires_at`), con **RLS completo de las tablas de gestión** (Sección
     8.3) activo desde el primer commit y la suite pgTAP de aislamiento corriendo
     en CI — no se pospone la seguridad multi-tenant a una fase posterior. **La
     tabla `resellers` y su RLS quedan escritos y validados en el esquema pero sin
     ningún flujo de UI ni backend que los active** (diferido a v2.0, Sección 3.1
     decisión 2) — no se elimina del esquema, simplemente no se construye encima de
     ella en el MLP. Ambientes: **Dev + Prod únicamente**, suite pgTAP como gate
     obligatorio de toda promoción (Sección 8.4). **Aplicar las decisiones
     Build-vs-Buy de la Sección 7.3** al arrancar cada componente de infraestructura
     (Postgres nativo, Auth + MFA, orquestador OTA, observabilidad) para no
     re-litigarlas sprint a sprint.
   * *Entregable:* Base de Datos Time-Series (particionada, sin TimescaleDB)
     recibiendo batches de telemetría de forma estable sin colapsar la PC del
     cliente, con el Edge Gateway autenticado por access+refresh token resolviendo y
     cargando su modelo de vertical correctamente al arrancar (con reanudación de
     descarga verificada bajo corte de conexión simulado, y revocación de
     credencial verificada por ejecución), y los tres niveles de aislamiento
     (tenant/site/partner) validados por pruebas automatizadas sobre **todas** las
     tablas del esquema — no solo las de telemetría — antes de escribir una sola
     pantalla de UI.

2. **Fase 2: El Producto Transaccional B2B2B (Mapeo, Backoffice, Partners y
   Tableros) — estimado 3-5 semanas**
   * *Objetivo:* crear la herramienta de administración para dibujar los polígonos
     (zonas) sobre el video, **incluyendo la convención `zone_type='staff_area'`**
     para exclusión de personal del conteo de clientes (Sección 6.1, Sección 3.1
     decisión 9) desde el mismo mapeo de zonas — no es una fase aparte, es un valor
     más del mismo campo. Desarrollar el cálculo lógico (batch) de intersecciones en
     la nube, alimentando `zone_dwell_sessions` (excluyendo `staff_area` del
     agregado de clientes). **Construir el Backoffice de Usuarios** (alta de
     usuarios `operator`/`viewer`, asignación granular a sucursales vía
     `user_site_assignments`, MFA vía Supabase Auth) **y el Módulo de Reventa de
     Partners en un solo paso** (Flujo 3 reescrito v3.4: un formulario → alta +
     asignación de zonas + invitación, en una transacción atómica — no un asistente
     de varios pasos), incluyendo el campo opcional `access_expires_at` y el job
     diario que revoca por expiración (mismo camino que el offboarding manual de
     12.12). **Implementar la matriz de vista restringida del Partner** (Sección
     4.1) en el frontend — qué módulos renderiza un Partner Admin/Viewer, encima de
     la garantía de RLS ya construida. Desplegar los tableros frontend (React),
     incluyendo las vistas agregadas de comparación inter-sucursal (Sección 8.1).
   * *Entregable:* Dashboard visual mostrando Mapas de Calor, Dwell Time real por
     zona (con personal excluido del conteo) y comparativos entre sucursales,
     funcionando correctamente para los tres perfiles de prueba (Tenant Admin,
     Operator regional, Partner con vista restringida verificada), con alta/baja de
     Partner en un solo paso y acceso por tiempo limitado operando, listo para venta
     comercial bajo el esquema B2B2B.

3. **Fase 3: Gestión de Flota, Registry Multi-Vertical, Operación Interna y Valor
   Premium Cognitivo — estimado 3-5 semanas**
   * *Objetivo:* implementar el orquestador OTA (**Portainer Community Edition**,
     Sección 7.3) para gestionar los Edge Nodes remotamente, incluyendo la
     distribución independiente de actualizaciones de código, modelo y
     configuración de tracking (canal `canary`/`stable`, Sección 8.4). **Construir
     el Flujo 7 (reemplazo de hardware / DR del Edge, Sección 5)** junto con el
     orquestador OTA — es la misma superficie operativa (gestión del ciclo de vida
     del Edge Gateway a escala de flota) —, incluyendo la revocación de
     access/refresh token del gateway dado de baja (`status='decommissioned'`,
     Sección 8.7.0) y la cadena `replaced_edge_gateway_id`. **Formalizar el Model
     Registry como servicio versionado**, dejando la arquitectura lista para
     admitir un segundo vertical sin cambios de código. **Poner en marcha los
     mecanismos de Operación Interna de la Sección 8.5** (break-glass auditado,
     retención/purga automatizada, cifrado de credenciales de cámara,
     observabilidad de accesos denegados y salud de flota) **junto con las alertas
     escalonadas de pérdida de datos offline (Sección 12.11: día 1 UI → día 3 correo
     → día 5 Slack/Telegram/WhatsApp según lo que el cliente tenga activo)**.
     Conectar la API de Anthropic para los módulos de chat (Copiloto en vivo,
     Messages API + Haiku 4.5) y auditorías visuales de stock (Batch API, Sección
     12.5), respetando el aislamiento de tres niveles — **sin Managed Agents, sin
     sandbox, sin el multiplicador 15x** (Sección 3.1 decisión 1); las auditorías
     escriben en `agent_findings` (Sección 12.7) igual que lo hará el Enjambre en
     Fase 4, mismo sumidero de datos. **Construir el Motor de Acciones** (Sección
     12.10: reglas umbral + **Slack/Telegram/Correo por defecto, WhatsApp opt-in
     con costo pass-through** + plantillas de SOP de compliance + `action_log`
     auditada) — es requisito de paridad competitiva del MLP, no un extra, y es el
     mismo motor que sirve las alertas de 12.11. **Implementar el endpoint de
     offboarding de Partner con derecho al olvido** (`DELETE /v1/tenants/
     {tenant_id}/partners/{partner_id}/data`, Sección 12.12) — depende del Módulo
     de Reventa ya construido en la Fase 2. **Levantar la suite de evaluación de
     calidad del Copiloto** (Sección 12.9: ~20 casos golden de retail + judge con
     rúbrica + firma humana) integrada como gate del pipeline antes del primer
     release comercial. **El Flujo 6 (referido de Reseller) no se construye en esta
     fase** — queda diferido a v2.0 junto con el resto del rol Reseller (Sección
     3.1 decisión 2).
   * *Entregable:* sistema End-to-End autónomo, gestionable a escala, produciendo
     insights cognitivos y acciones automáticas auditables (incluidas las alertas
     escalonadas de flota offline y la revocación de credenciales de gateways
     reemplazados), con la infraestructura de Model Registry validada para
     onboardear un segundo vertical, el endpoint de purga por derecho al olvido
     operando bajo auditoría, y con los controles de operación interna (Sección
     8.5) y el gate de calidad (12.9) verificados — no solo documentados — antes
     del primer cliente en producción. **MLP completo en este punto: 8-13 semanas
     acumuladas desde el inicio de Fase 1.**

4. **Fase 4: Enjambre Cognitivo del Plan Enterprise + Reseller v2.0 (post-MLP)**
   * *Objetivo:* implementar la arquitectura completa de la Sección 12 sobre
     Managed Agents: sesiones por contexto de aislamiento (12.1-12.2), scheduled
     deployments para la corrida diaria (12.4), subagentes según la matriz de
     paralelizabilidad (12.6), patrón de artefactos con `agent_findings` (12.7) —
     ya en uso desde Fase 3 con auditorías de una sola fila, ahora recibiendo el
     volumen del Enjambre —, observabilidad sin contenido con `agent_run_metrics`
     (12.8) y Outcomes como control de calidad continuo (12.9). Validar el COGS
     real por sede contra el modelo de la Sección 10.1 durante un piloto pagado
     antes de abrir la venta general del Plan Enterprise. **Activar mTLS (Sección
     8.7.1)** si algún vertical o cliente lo exige contractualmente — sin
     rediseño, sobre el mismo `edge_gateways`. **Activar el rol Reseller completo**
     (Flujo 6, Sección 5; RLS de `resellers`, ya construido en Fase 1) cuando se
     cierre el primer acuerdo de canal real — es habilitar UI/backend sobre un
     esquema que ya existe, no reconstruirlo.
   * *Entregable:* Plan Enterprise comercializable con COGS medido (no estimado),
     márgenes confirmados ≥ 84%, el Copiloto en vivo + Enjambre operando por los dos
     caminos de latencia definidos en 12.4, y — si el negocio lo requiere en este
     punto — el ciclo comercial de Reseller y/o mTLS activos sin haber tocado el
     esquema físico del MLP.

---

### Apéndice A — Changelog (v3.4 arriba; iteraciones previas debajo)

#### A.0 Changelog v3.3-FINAL → v3.4-FINAL

Esta iteración deriva de una especificación externa de "MLP Recortado" —
consolidada a partir de una serie de decisiones de negocio ya confirmadas — que
define **qué construir primero** sin renunciar a ningún feature de cliente ni a la
propuesta de valor frente a Agrex.ai. El documento base (v3.3) sigue siendo la
fuente de verdad de la arquitectura completa; v3.4 le agrega una capa explícita de
secuenciación de ejecución (Sección 3.1) y ajusta un puñado de mecanismos
concretos donde el recorte sí toca diseño (credenciales, hosting, Partners, Motor
de Acciones). Formato qué/por qué/trade-off, igual que las iteraciones anteriores.

1. **Nueva Sección 3.1 — MLP Recortado: doce decisiones de alcance con gancho de
   activación.**
   *Qué:* tabla consolidada de las doce decisiones de secuenciación (Managed
   Agents a Fase 4, Reseller fuera del MLP, ambientes Dev+Prod, credenciales por
   refresh token, banca fuera del MLP, canales del Motor de Acciones, SOP
   compliance, exclusión de personal sin demografía, MFA, máquina de estados de
   onboarding, hosting Supabase+R2+Render/Cloud Run+GitHub), cada una con su
   "gancho": dónde vive ya construido en el documento y qué la activa sin
   rediseño.
   *Por qué:* sin esta sección, el recorte de alcance vivía repartido en once
   respuestas de negocio sin un solo lugar del SDD que las consolidara — riesgo de
   que el equipo de desarrollo interpretara el alcance de forma distinta al
   negocio.
   *Trade-off:* ninguno; es documentación de una decisión ya tomada, no una
   decisión técnica nueva.

2. **Reseller — corrección de alcance: todo el flujo fuera del MLP, no solo su
   comisión (Secciones 3, 4, 5, 13).**
   *Qué:* v3.3 solo excluía la liquidación de comisión del Reseller del alcance;
   v3.4 corrige esto — el Flujo 6 completo y cualquier UI/backend sobre el rol
   Reseller quedan diferidos a v2.0. La tabla `resellers` y su RLS (ya construidos
   y validados) permanecen en el esquema, inertes.
   *Por qué:* confirmado explícitamente por el negocio — ningún caso de uso del
   MLP requirió un Reseller; todo lo necesario es la relación Asset Owner↔Partner.
   *Trade-off:* ninguno para el esquema (nada se elimina); el equipo de producto no
   construye una UI de gestión de cartera que nadie usaría en el año 1.

3. **Credenciales del Edge Gateway para el MLP: access + refresh token, mTLS
   diferido a Fase 4+ (Sección 8.7, reestructurada en 8.7.0/8.7.1).**
   *Qué:* el mecanismo por defecto pasa de certificado cliente mTLS (v3.3) a
   access token (24h, JWT stateless) + refresh token (90 días, hash persistido,
   rotado en cada uso). Revocación real: `edge_gateways.status='revoked'` bloquea
   el siguiente refresh — ventana máxima de exposición 24h (vs. revocación
   inmediata de mTLS). El mecanismo mTLS queda íntegro en el documento como 8.7.1,
   con el mismo enum de `status` y el mismo patrón de revocación contra estado en
   DB, listo para activarse sin rediseño.
   *Por qué:* mTLS es más PKI de la que el MLP necesita — revocación en ≤24h es
   suficiente para el perfil de riesgo del lanzamiento (retail/logística, no
   banca), y elimina la complejidad de operar una CA interna desde el día uno.
   *Trade-off:* ventana de exposición de hasta 24h tras revocar un gateway
   comprometido (vs. inmediata con mTLS) — aceptado explícitamente como parte del
   recorte de madurez operativa; se revierte activando 8.7.1 sin tocar el resto
   del esquema. Validado por ejecución: refresh legítimo funciona, refresh de
   gateway revocado/expirado/con token ya rotado (replay) es rechazado en los
   tres casos.

4. **Hosting del MLP: Supabase + Cloudflare R2 + Render/Cloud Run + GitHub,
   AWS/RDS como ruta de Fase 4+ (Secciones 1, 7, 7.3, 10.1).**
   *Qué:* se fija el stack de hosting del MLP y se retiran las menciones de AWS
   como default (Model Registry, Cloud Hosting) — quedan como ruta de
   escalamiento documentada, no como decisión del MLP.
   *Por qué:* verificado contra documentación oficial: una cuenta nueva de AWS se
   cierra a los 6 meses salvo upgrade a plan pagado (créditos de hasta $200); una
   cuenta nueva de GCP tiene $300 válidos solo 90 días. Ninguno de los dos sostiene
   una cuenta nueva sin reloj de expiración; Supabase/Cloudflare R2/Render/Cloud
   Run/GitHub sí, en sus respectivos free tiers.
   *Trade-off:* migrar a AWS/RDS en Fase 4+ es un cambio de endpoint sobre una API
   equivalente (R2 es compatible con S3), no un rediseño — costo de migración bajo
   si el volumen lo justifica.

5. **Tres refinamientos de Partners (Secciones 4.1, 5 Flujo 3, 8.0).**
   *Qué:* (a) alta/baja en un solo paso (formulario único → alta + asignación de
   zonas + invitación, transacción atómica — reemplaza el asistente de varios
   pasos descrito en versiones anteriores); (b) nueva columna
   `partners.access_expires_at` (NULL = indefinido) con job diario que revoca por
   el mismo camino del offboarding manual (12.12) cuando vence; (c) matriz
   explícita de qué pantallas ve un Partner Admin/Viewer en el frontend (nueva
   Sección 4.1), como capa de producto encima de la garantía de RLS ya existente.
   *Por qué:* la revisión de alcance reveló que estas tres piezas sí importan para
   la propuesta de valor del MLP, aunque no estuvieran en el recorte original —
   activaciones de marca por temporada necesitan acceso con fecha de vencimiento;
   un wizard de varios pasos es fricción de producto innecesaria; nadie había
   enumerado qué ve realmente un Partner.
   *Trade-off:* ninguno; son adiciones de bajo costo sobre infraestructura ya
   construida (el mecanismo de revocación de 12.12, el RLS de 8.3). Validado por
   ejecución: la consulta del job diario devuelve exactamente los Partners activos
   y vencidos, ninguno de los indefinidos/futuros/ya revocados.

6. **Ambientes del MLP: Dev + Prod, QA/Staging como ambiente adicional futuro
   (Sección 8.4).**
   *Qué:* se reduce de cuatro ambientes a dos para el MLP, con la suite pgTAP
   completa como gate obligatorio de toda promoción — el pipeline no se recorta,
   solo el número de ambientes intermedios.
   *Por qué:* mantener QA y Staging como instancias separadas antes de tener
   volumen de clientes que lo justifique es costo operativo sin beneficio de
   seguridad adicional, dado que Dev y Prod nunca comparten clúster de todos
   modos.
   *Trade-off:* menos superficie de prueba en un ambiente espejo de Prod antes del
   primer release; mitigado por el gate pgTAP obligatorio, que ya cubre el
   aislamiento multi-tenant sin necesitar un ambiente adicional. Se agrega QA/
   Staging como nodo más del mismo pipeline cuando el volumen lo justifique.

7. **Motor de Acciones: reordenamiento de canales y plantillas de SOP (Sección
   12.10, tabla Build-vs-Buy 7.3, economía 10.1).**
   *Qué:* Slack, Telegram y correo pasan a ser el default (costo marginal cero);
   WhatsApp Business API se mantiene disponible desde el día 1 pero como opt-in
   con su costo de Meta facturado como línea aparte al cliente, nunca absorbido en
   el COGS. Se agregan plantillas de reglas de compliance sobre el mismo motor:
   personal no presente en zona de caja, apertura/cierre fuera de horario, cliente
   sin atender.
   *Por qué:* WhatsApp seguía siendo tratado como "el canal" por defecto en v3.3,
   lo que habría absorbido su costo de Meta en el COGS de todos los clientes
   aunque no todos lo usaran; las plantillas de SOP son la misma infraestructura
   de reglas-por-umbral ya diseñada, aplicada a más casos de uso de valor.
   *Trade-off:* ninguno técnico; es una re-etiquetación de costos (quién paga qué)
   y una extensión de catálogo de reglas sobre un motor sin cambios.

8. **Zona de exclusión de personal; demografía confirmada fuera de alcance
   (Secciones 3, 6.1, 12.10).**
   *Qué:* convención `zone_type='staff_area'` (sin migración de esquema —
   `zones.zone_type` ya es texto libre) que el Motor Matemático excluye del
   conteo de clientes. Demografía (edad/género) se declara explícitamente fuera
   de alcance por defecto, reforzando Zero Biometrics como diferenciador de
   privacidad frente a Agrex.ai.
   *Por qué:* sin exclusión de personal, empleados que pasan horas frente a una
   cámara inflan artificialmente el tráfico/dwell time agregado y sesgan el
   Copiloto; demografía es una capa de sensibilidad de dato mayor que la sola
   detección de `person`, y no es necesaria para ningún caso de uso del MLP.
   *Trade-off:* ninguno; exclusión de personal es bajo costo y alto valor de
   precisión; demografía queda disponible caso por caso bajo consentimiento
   explícito del cliente, nunca por defecto.

9. **MFA y máquina de estados de onboarding/offboarding de Tenants (Secciones 4,
   5 Flujo 1).**
   *Qué:* MFA confirmado como configuración de Supabase Auth, sin desarrollo
   adicional. Variante MLP del Flujo 1: auto-registro del Tenant → aprobación de
   un clic del SuperAdmin → activo; baja dispara retención + revocación de
   tokens del Edge Gateway (mismo mecanismo de la decisión 3 arriba).
   *Por qué:* MFA de fábrica no requería trabajo de diseño, solo confirmarlo en
   el documento; la máquina de estados de onboarding estaba implícita en el
   `status` de `tenants` pero nunca se había descrito como flujo explícito con su
   variante self-service.
   *Trade-off:* ninguno; ambos son formalización de mecanismos ya disponibles o
   ya implícitos en el esquema.

10. **Roadmap (Sección 13) reescrito con el MLP recortado.**
    *Qué:* Fases 1-3 actualizadas para reflejar credenciales por refresh token, la
    salida completa de Reseller/Flujo 6 del plan de ejecución (se mueve a Fase 4
    junto con mTLS), ambientes Dev+Prod, y el reordenamiento de canales/plantillas
    del Motor de Acciones; estimado total actualizado a 8-13 semanas (antes
    10-19).
    *Por qué:* el roadmap es el documento operativo que el equipo de desarrollo
    sigue sprint a sprint — tenía que reflejar el recorte real, no solo las
    secciones de diseño.
    *Trade-off:* ninguno; es la propagación del recorte ya decidido al plan de
    ejecución.

**Verificaciones nuevas de esta iteración (se suman a la tabla A.4)**

| Afirmación | Método | Resultado |
| --- | --- | --- |
| AWS: cuenta nueva se cierra a los 6 meses salvo upgrade a plan pagado (créditos hasta $200); ~30 servicios "always-free" no expiran pero no evitan el cierre de cuenta | Documentación oficial de AWS (2026-07) | Confirmado |
| GCP: crédito de bienvenida $300 válido 90 días para cuentas nuevas | Documentación oficial de Google Cloud (2026-07) | Confirmado |
| Mecanismo de refresh token: refresh legítimo funciona; refresh de gateway revocado/expirado/con token ya rotado (replay) es rechazado en los tres casos | Ejecución real contra PostgreSQL 16 | Los cuatro escenarios se comportan exactamente como se diseñó |
| Job diario de expiración de acceso de Partner (`partners.access_expires_at`): devuelve exactamente los Partners activos y vencidos | Ejecución real contra PostgreSQL 16, incluye verificación de plan de consulta (usa el índice parcial) | Confirmado |
| Cadena de reemplazo de Edge Gateway (Flujo 7) compatible con el mecanismo de refresh token | Ejecución real contra PostgreSQL 16 | Confirmado — mismo patrón que mTLS, sin cambios al enum de `status` |

---

### Apéndice A (histórico) — Changelog de la iteración v3.2-FINAL → v3.3-FINAL

#### A.0 Changelog v3.2-FINAL → v3.3

Cada entrada: **qué se modificó**, **por qué**, **qué trade-off implica**. Mismo
formato que las secciones A.1-A.4 (que documentan la iteración v3.2, conservadas
abajo como registro histórico).

**Arquitectura de datos**

1. **Rediseño de la capa time-series: TimescaleDB → Postgres nativo + `pg_partman`
   (Secciones 7, 8.0, 8.6).**
   *Qué:* `tracking_coordinates` deja de ser una hypertable de TimescaleDB y pasa a
   particionamiento declarativo nativo `PARTITION BY RANGE ("time")` gestionado por
   `pg_partman`; se reescribe todo el DDL de creación, retención y compresión.
   *Por qué:* TimescaleDB está deprecado para proyectos nuevos de Supabase
   (verificado contra su documentación oficial), y Supabase free tier es el destino
   de hosting de bajo costo/fallback — el esquema anterior simplemente no corría
   ahí. Es una decisión de **portabilidad**: el mismo esquema debe correr en
   Supabase, RDS y Postgres local.
   *Trade-off:* se pierde la compresión columnar automática de Timescale (>90% de
   ratio); se mitiga con TOAST + tipos ajustados, `pg_squeeze` en particiones frías,
   y tiering del histórico >3 meses a S3 Glacier. El presupuesto de $15-27/sede se
   mantiene, a costa de un job de tiering operativo en vez de una política
   declarativa. Validado por ejecución contra PostgreSQL 16 (creación, enrutamiento,
   llegada tardía, propagación de índices).

2. **RLS completo y real de las ocho tablas restantes (Sección 8.3).**
   *Qué:* se escribe y valida por ejecución el `ENABLE/FORCE RLS` + políticas de
   `sites`, `cameras`, `zones`, `users`, `partners`, `tenants`, `resellers`,
   `user_site_assignments`, con helpers de pertenencia `SECURITY DEFINER` para
   evitar recursión mutua entre políticas.
   *Por qué:* v3.2 decía "la misma política aplica... se omite por brevedad" pero
   nunca lo escribió, y cinco tablas no tenían RLS del todo — cada una era una fuga:
   cualquier rol leía la tabla entera. "Sigue el mismo patrón" en prosa no es un
   control de seguridad.
   *Trade-off:* introduce funciones `SECURITY DEFINER` (dueño con `BYPASSRLS`), que
   son poder que hay que auditar; se acota devolviendo solo booleanos/escalares y
   documentando el patrón. Alternativa (subconsultas inline) causa
   `infinite recursion` — no era opción.

3. **Fix de `agent_findings_write`: subagente en contexto Partner no podía escribir
   (Sección 12.7).**
   *Qué:* se agrega la rama Partner que deriva `tenant_id` del padre del partner en
   vez de exigir `= app_current_tenant_id()` (que es NULL en sesión de Partner);
   test pgTAP 05 nuevo que ejecuta el INSERT.
   *Por qué:* bug real y silencioso — el patrón de artefactos (12.7) depende de que
   los subagentes escriban hallazgos, y en sesión de Partner **toda** escritura
   fallaba con violación de RLS. Descubierto y confirmado por ejecución.
   *Trade-off:* ninguno; es corrección pura. La rama nueva sigue impidiendo escribir
   a nombre de otro tenant (validado).

4. **Política de INSERT para `zone_dwell_sessions` (Sección 8.3).**
   *Qué:* se escribe la política `zone_dwell_sessions_ingest` scoped por
   `app.motor_site_id` que v3.2 solo mencionaba.
   *Por qué:* con `FORCE RLS`, una tabla sin política de INSERT rechaza toda
   escritura — el Motor Matemático no podía escribir ni una fila de dwell. Misma
   clase de defecto ya corregido para `tracking_coordinates` en v3.2.
   *Trade-off:* un subquery de cadena `zone→camera→site` por lote (amortizado);
   ninguno funcional. Validado por ejecución.

5. **Decisión explícita de RLS para `agent_run_metrics` (Sección 12.8).**
   *Qué:* se decide y documenta que es tabla exclusivamente interna
   (`FORCE RLS` + sin política de lectura, deny-by-default total), como
   `platform_admins`/`break_glass_audit_log`.
   *Por qué:* v3.2 la dejó sin RLS declarado; exponerla filtraría patrones de uso
   del cliente sin valor para él. El COGS agregado, si se decide exponer, irá por
   una vista de resumen separada.
   *Trade-off:* el Asset Owner no ve su consumo por esta tabla directamente
   (deliberado); ninguno en seguridad. Validado: cero filas para rol de aplicación.

6. **Residual "2 niveles" del diagrama de la Sección 6.**
   *Qué:* el diagrama ASCII decía "RLS de 2 niveles" y "PostgreSQL+Timescale" — se
   corrige a "3 niveles: tenant→site→partner" y "PostgreSQL nativo + pg_partman".
   *Por qué:* residual no capturado por la corrección de terminología de v3.2.
   *Trade-off:* ninguno; consistencia.

**Ciclo de vida y operación**

7. **Flujo 6 — Referido de Tenant por Reseller (Sección 5) + exclusión de comisión
   de Reseller (Sección 3).**
   *Qué:* se documenta el ciclo comercial del Reseller (referir → aprobación
   SuperAdmin → visibilidad de metadata acotada) y se declara fuera de alcance la
   liquidación de su comisión.
   *Por qué:* el rol Reseller Admin existía en la Sección 4 sin flujo ni límite de
   alcance — un gap de ciclo de vida.
   *Trade-off:* la plataforma provee atribución pero no cobro; mismo principio ya
   aplicado a Partners, coherente.

8. **Flujo 7 — Reemplazo de Hardware / DR del Edge (Sección 5) + columnas nuevas en
   `edge_gateways` (Sección 8.7).**
   *Qué:* código de activación marcado como "reemplazo de edge_id=X" que reutiliza
   `site`/`cameras`; `replaced_edge_gateway_id` (FK a sí misma), estados
   `revoked`/`decommissioned`.
   *Por qué:* el reemplazo de hardware es frecuente en BYOD/CENAM y no tenía flujo —
   riesgo de duplicar sedes/cámaras o perder trazabilidad.
   *Trade-off:* ninguno; la telemetría histórica vive por `site`/`camera`, no por
   `edge_id`, así que el reemplazo no pierde datos. Validado por ejecución
   (cadena de reemplazo + enum ampliado).

9. **Credenciales del Edge por mTLS (Sección 8.7; fila IAM de Sección 4
   actualizada).**
   *Qué:* se reemplaza el "JWT/API Key" genérico por certificado cliente mTLS con
   rotación proactiva y revocación server-side contra `edge_gateways.status` en cada
   handshake.
   *Por qué:* el Edge Gateway es el punto más expuesto (vive en la sede del cliente)
   y v3.2 no especificaba almacenamiento, rotación ni revocación de su credencial.
   *Trade-off:* operar una CA interna (build, Sección 7.3) a cambio de revocación
   inmediata y credenciales que sobreviven reinicios sin flujo de refresh — crítico
   con la conectividad intermitente de CENAM.

10. **Alertas escalonadas antes de pérdida de datos offline (Sección 12.11).**
    *Qué:* escalera día 1 (UI) → día 3 (correo) → día 5 (WhatsApp/Slack vía Motor de
    Acciones) con mensaje que indica los días restantes antes de evicción FIFO.
    *Por qué:* un aviso binario offline/online no comunica la urgencia creciente de
    pérdida irrecuperable de telemetría cuando la cola local se llena.
    *Trade-off:* reutiliza el Motor de Acciones (12.10) con una regla de catálogo,
    no infraestructura nueva; ninguno.

11. **Offboarding de Partner y derecho al olvido (Sección 12.12).**
    *Qué:* se separa la *visibilidad* del Asset Owner sobre hallazgos de un Partner
    revocado (ya resuelta por RLS, sin cambios) de la *purga por solicitud legal*
    (endpoint dedicado y auditado, distinto del timer pasivo de 13 meses).
    *Por qué:* v3.2 no distinguía retención por defecto de supresión bajo demanda —
    riesgo de borrar datos aún necesarios, o de retener datos que legalmente deben
    desaparecer.
    *Trade-off:* la purga es una operación explícita y auditada (más fricción) a
    cambio de un contrato de privacidad defendible.

12. **Descargas OTA resumibles y expiración de URL firmada (Sección 9.1).**
    *Qué:* reanudación por `Range`, TTL de URL firmada de 1h, y re-pedido del
    manifiesto (no reintento de la URL vencida) con el mismo backoff exponencial de
    la cola de telemetría.
    *Por qué:* las conexiones intermitentes de CENAM rompen descargas de checkpoints
    a mitad; sin reanudación se reinicia desde cero y puede no completar nunca.
    *Trade-off:* ninguno; S3 soporta `Range` nativamente, sin trabajo de servidor.

**Negocio**

13. **Tabla Build-vs-Buy (Sección 7.3).**
    *Qué:* registro explícito de construir vs. adoptar por componente, con motivo y
    trade-off, incluida la DB forzada a Postgres nativo por la Sección 8.6.
    *Por qué:* evitar re-litigar estas decisiones cada sprint y dejar claro que el
    foco de "build" es solo el diferenciador (aislamiento B2B2B + Motor Base).
    *Trade-off:* documentado por fila; el criterio transversal es no construir lo no
    diferenciador y elegir "buy" de costo ~cero hasta tener volumen.

14. **Enganche de los ítems nuevos de v3.3 al Roadmap (Sección 13).**
    *Qué:* las seis piezas nuevas de esta iteración (Flujo 6, Flujo 7, mTLS del
    Edge/8.7, descargas OTA resumibles/9.1, alertas escalonadas/12.11, offboarding
    con derecho al olvido/12.12) más la tabla Build-vs-Buy/7.3 quedaban escritas en
    su sección propia pero **sin mención en ninguna fase del roadmap** — vivían en
    el diseño sin estar ancladas al plan de ejecución. Se ubican así: mTLS (8.7),
    las descargas resumibles (9.1) y Build-vs-Buy (7.3) → **Fase 1**, junto al
    Model Manager y el esquema físico, porque son parte del mecanismo definitivo que
    se construye una sola vez (no tiene sentido levantar Model Manager sin
    reanudación de descarga, ni el Edge Gateway con una credencial provisional que
    luego se reemplaza); Flujo 6, Flujo 7 y las alertas escalonadas (12.11) →
    **Fase 3**, junto a Operación Interna (8.5) y el Motor de Acciones (12.10), por
    ser extensiones del mismo trabajo de observabilidad y ciclo de vida de flota que
    ya vive ahí; el offboarding con derecho al olvido (12.12) → también **Fase 3**,
    porque aunque opera *sobre* el Módulo de Reventa construido en la Fase 2, es una
    operación de purga auditada que pertenece al mismo bloque de cumplimiento y
    operación interna que el resto de la fase, no al bloque transaccional de la
    Fase 2.
    *Por qué:* un SDD que se declara la única fuente de verdad para desarrollo no
    puede dejar piezas de arquitectura sin un lugar en el plan de ejecución — el
    equipo de desarrollo necesita saber en qué sprint cae cada cosa, no solo que
    existe en algún lado del documento.
    *Trade-off:* ninguno; es una corrección de trazabilidad, no de contenido técnico
    — ninguna sección previa cambia, solo se referencian desde el roadmap.

**Verificaciones nuevas de esta iteración (se suman a la tabla A.4)**

| Afirmación | Método | Resultado |
| --- | --- | --- |
| TimescaleDB deprecado en proyectos nuevos de Supabase (PG17) | Documentación oficial de Supabase (2026-07) | Confirmado; motiva el rediseño de 8.6 |
| Particionamiento nativo: creación, enrutamiento por `"time"`, llegada tardía, índices propagados | Ejecución real contra PostgreSQL 16 | Corre sin errores |
| RLS de las 8 tablas de gestión + helpers `SECURITY DEFINER` sin recursión | Ejecución real contra PostgreSQL 16, rol no-superusuario | 23 políticas; aislamiento cruzado verificado (admin/partner/operator/reseller) |
| Fix `agent_findings_write` en contexto Partner | Ejecución real (INSERT en sesión de Partner + rechazo de tenant ajeno) | Antes fallaba; ahora inserta y bloquea lo ajeno |
| Política INSERT de `zone_dwell_sessions` | Ejecución real (site correcto inserta, ajeno rechazado) | Correcto |
| `agent_run_metrics` deny-by-default | Ejecución real (rol de aplicación → 0 filas) | Correcto |
| `edge_gateways` mTLS + cadena de reemplazo | Ejecución real (ALTER + FK a sí misma + enum ampliado) | Correcto |
| `pg_partman` `create_parent`/retención | Documentación oficial de pg_partman 5.x | Verificado documentalmente (extensión no presente en el entorno de auditoría) |

---

### Apéndice A (histórico) — Changelog de la iteración v3.1 → v3.2-FINAL

Cada entrada indica: **qué se modificó**, **por qué**, y **qué trade-off implica**.

#### A.1 Modelo de negocio

1. **Economía unitaria dividida en dos planes (Sección 10.1, reescrita).**
   *Qué:* el COGS único de $22-41/sede se reemplaza por Plan Base ($20-35) y Plan
   Enterprise ($30-65), y el Plan Enterprise se re-precia de ~$175-235 a $400-500
   por sede/mes.
   *Por qué:* el consumo de tokens del Enjambre se recalculó con el multiplicador
   real documentado por Anthropic (~15x el chat simple para sistemas multiagente,
   ~4x para agentes individuales) en lugar de la estimación optimista anterior; con
   ejecución diaria del enjambre, el costo de IA por sí solo ($11-32/mes) más
   infraestructura excede el COGS objetivo original — mantener el precio anterior
   habría significado vender el plan insignia con margen decreciente e
   impredecible.
   *Trade-off:* un precio Enterprise de $400-500 sube la barrera comercial en un
   mercado sensible a precio; se mitiga anclando el precio al valor documentado por
   el mercado de referencia (Agrex.ai: 20-30% de reducción en colas) y manteniendo
   el Plan Base en $150-200 como puerta de entrada. La alternativa (enjambre
   semanal para abaratar) queda disponible como configuración, no como default.

2. **Estrategia de cargas nocturnas condicionada por el pricing verificado
   (Secciones 10.1 y 12.5).**
   *Qué:* las auditorías batch del Plan Base se mueven explícitamente a la
   Messages API/Batch API (50% de descuento); Managed Agents queda reservado para
   el Enjambre Enterprise.
   *Por qué:* verificación contra la página oficial de pricing: el descuento de
   Batch API **no aplica** dentro de sesiones de Managed Agents — usar CMA para
   todo habría duplicado el costo de las cargas que no necesitan sandbox.
   *Trade-off:* dos rutas de ejecución que mantener (batch pipeline + CMA) a cambio
   de ~50% de ahorro en la mitad no interactiva de la carga; la complejidad se
   acota compartiendo el mismo MCP interno y el mismo contexto RLS en ambas rutas.

3. **Métricas de valor calibradas contra el competidor (Secciones 1 y 12.10).**
   *Qué:* se adopta el rango publicado por Agrex.ai (20-30% de reducción de colas)
   como benchmark citable, y se define que nuestras promesas usan la medición del
   propio cliente como evidencia.
   *Por qué:* proyecciones de valor sin referencia externa no son creíbles en un
   head-to-head; inventar porcentajes propios sin producción es un riesgo
   reputacional.
   *Trade-off:* citamos el benchmark de un competidor (implícitamente validándolo);
   aceptable porque el tablero de correlación alerta→métrica (12.10) convierte esa
   referencia en medición propia por cliente.

#### A.2 Arquitectura de datos y seguridad

4. **Corrección de la política RLS de `zone_dwell_sessions` (Sección 8.3).**
   *Qué:* se agrega la rama "el tenant ve las zonas cedidas a sus propios
   Partners", más el test pgTAP 04 que la protege.
   *Por qué:* defecto real — al reasignar una zona a un Partner (`owner_type =
   'PARTNER'`), la política anterior se la ocultaba al Asset Owner, contradiciendo
   la garantía explícita del Flujo 3 ("sin afectar la visibilidad que el propio
   Asset Owner tiene... que conserva siempre").
   *Trade-off:* la política gana un EXISTS adicional (costo de plan de consulta
   marginal, cubierto por `idx_partners_tenant_id`); ninguno en seguridad — la
   visibilidad agregada es del dueño legítimo de la infraestructura.

5. **Corrección de la política break-glass (Sección 8.5).**
   *Qué:* el acceso de soporte se acota al `tenant_id_accessed` declarado en la
   auditoría (columna ahora NOT NULL), se verifica el estado activo del admin y el
   timeout de 4 horas dentro de la propia política, y las tablas de auditoría
   quedan bajo FORCE RLS sin política de lectura para roles de aplicación.
   *Por qué:* defecto de seguridad real — la versión anterior otorgaba SELECT
   sobre datos de **todos** los tenants mientras existiera cualquier sesión
   break-glass abierta, y el timeout dependía de un proceso externo que podía
   fallar.
   *Trade-off:* un incidente que abarque varios tenants exige varias filas de
   auditoría (una por tenant) — fricción deliberada: es exactamente el registro
   que un auditor esperaría.

6. **Funciones helper `STABLE LEAKPROOF PARALLEL SAFE` (Sección 8.2).**
   *Qué:* las cuatro funciones de contexto RLS se marcan LEAKPROOF y PARALLEL
   SAFE, con nota operativa sobre el requisito de superusuario.
   *Por qué:* restricción no negociable del diseño; sin LEAKPROOF el planner no
   empuja predicados bajo la barrera RLS y las consultas sobre la hypertable
   degradan a seq-scan; las funciones califican legítimamente (solo leen GUCs).
   *Trade-off:* dependencia de un privilegio de superusuario que los Postgres
   gestionados no siempre exponen — se documenta la validación como criterio de
   selección de proveedor y la alternativa (inline de `current_setting`) si un
   proveedor lo bloquea.

7. **Política de INSERT para ingesta scoped por Edge Gateway (Sección 8.3).**
   *Qué:* nueva política `tracking_coordinates_ingest` con
   `app_current_ingest_site_id()` fijado desde el JWT del gateway.
   *Por qué:* las políticas existentes eran solo FOR SELECT (con FORCE RLS, la
   ingesta habría fallado en el primer INSERT), y de paso cierra el vector de un
   gateway comprometido inyectando telemetría de otra sede.
   *Trade-off:* un subquery por lote insertado (amortizado en batch); ninguno
   funcional.

8. **Datos semilla y tests pgTAP ejecutables; GUC de rol renombrada (Secciones
   8.2 y 8.4).**
   *Qué:* (a) los literales 'r1'/'t1'/'s1'/'u_admin' se reemplazan por UUIDs
   válidos fijos y legibles; (b) el test 03 gana el caso partner-vs-partner y se
   agrega el test 04; (c) la GUC `app.current_role` se renombra a
   `app.current_actor_role` en todo el documento.
   *Por qué:* los bloques anteriores fallaban en ejecución real por dos causas:
   "invalid input syntax for type uuid" en las semillas, y — descubierto al
   validar — `SET app.current_role = ...` es un **error de sintaxis** en
   PostgreSQL porque `current_role` es palabra reservada del estándar SQL. Un
   documento que se declara "ejecutable, no solo conceptual" no puede contener
   SQL que no corre. Todo el DDL de la Sección 8 (tablas, funciones LEAKPROOF,
   políticas, semillas) fue validado por ejecución contra PostgreSQL 16 en esta
   iteración, incluida una prueba funcional del aislamiento con un rol de
   aplicación no-superusuario: tenant admin ve zona propia + zona cedida (2
   filas), Partner ve exactamente la suya (1), otro tenant ve 0, la ingesta con
   `site` correcto inserta y con `site` ajeno es rechazada por la política. Las
   llamadas TimescaleDB (`create_hypertable`, retención, compresión) se validaron
   contra su documentación por no estar la extensión disponible en el entorno de
   auditoría.
   *Trade-off:* UUIDs fijos legibles en vez de aleatorios — deliberado para que
   los tests sean deterministas; el rename de la GUC obliga a tocar cualquier
   código ya escrito contra el nombre anterior (no hay ninguno: el esquema aún no
   está en producción — esta es exactamente la razón para corregirlo ahora).

9. **Compresión columnar de TimescaleDB (Sección 8.5).**
   *Qué:* política de compresión a 7 días sobre `tracking_coordinates`.
   *Por qué:* 13 meses de telemetría sin comprimir rompe el presupuesto de
   $15-27/sede de infraestructura; la compresión (>90% típico en este perfil) es
   la palanca que lo sostiene.
   *Trade-off:* los chunks comprimidos penalizan UPDATEs/DELETEs (irrelevante:
   la telemetría es append-only) y la suite de aislamiento debe correr también
   contra datos comprimidos (agregado al ambiente de pruebas de carga).

10. **Terminología unificada: "aislamiento de tres niveles" (Secciones 2, 8.3,
    10.2).**
    *Qué:* los encabezados y objetivos que decían "dos niveles" pasan a "tres
    niveles: tenant → site → partner".
    *Por qué:* la jerarquía de tres niveles ya estaba construida (v3.0); el texto
    heredado de v2.0 la subvendía y generaba ambigüedad sobre cuál era la
    restricción real.
    *Trade-off:* ninguno; es corrección de consistencia.

#### A.3 Infraestructura e IA

11. **Retiro de Claude 3.5 Sonnet y estrategia de modelos vigente (Secciones 3,
    7, 12.5).**
    *Qué:* toda referencia al modelo retirado (oct-2025) se reemplaza por la
    matriz de modelos por carga de trabajo: Haiku 4.5 (copiloto y subagentes),
    Sonnet 4.6/5 (orquestador, visión, batch), Opus 4.8 (escalación puntual);
    IDs de modelo por configuración, nunca hardcodeados.
    *Por qué:* el modelo citado devuelve 404 — cualquier código construido sobre
    el documento anterior habría fallado en el primer request.
    *Trade-off:* Sonnet 4.6/5 es más caro por token que el modelo retirado, pero
    el mix Haiku/Sonnet por carga de trabajo deja el costo neto por debajo del
    supuesto original (detalle en 10.1/12.5).

12. **Estatus de multiagent orchestration actualizado (Sección 12.1).**
    *Qué:* deja de describirse como research preview; se documentan los límites
    verificados de la beta pública (roster máx. 20, 25 threads, un nivel de
    delegación, threads comparten contenedor/filesystem, vaults por sesión).
    *Por qué:* verificación contra documentación oficial vigente; el estatus
    anterior era correcto cuando se escribió pero ya no.
    *Trade-off:* ninguno para el aislamiento — la corrección central de 12.1
    (sesiones separadas por contexto) se reafirma con la documentación actual.

13. **Resolución explícita Copiloto-en-vivo vs. enjambre síncrono (Sección 12.4).**
    *Qué:* dos caminos de latencia formalizados — Messages API + streaming para el
    chat (promesa: primera palabra ~1-3 s), enjambre asíncrono programado
    (scheduled deployments) cuyos resultados llegan como hallazgos/alertas; el
    puente es "responder con lo que existe + encolar corrida profunda".
    *Por qué:* el patrón orquestador-subagentes espera a todos los subagentes; era
    incompatible, sin decisión explícita, con la promesa de un copiloto "en vivo".
    *Trade-off:* la promesa comercial se ajusta a la baja ("análisis profundo en
    minutos, no en el chat") a cambio de una promesa cumplible el 100% de las
    veces; se renuncia deliberadamente al enjambre-como-chat.

14. **Matriz de paralelizabilidad por subagente (Sección 12.6, nueva).**
    *Qué:* Visión y Planogramas → multiagente (unidades independientes por zona);
    Trade Marketing y reportes → agente individual con pasos; regla de decisión
    formal para subagentes futuros.
    *Por qué:* el multiplicador 15x solo se justifica en tareas genuinamente
    paralelizables (hallazgo central del paper de Anthropic); tratar tareas
    secuenciales como enjambre quema tokens sin ganancia de calidad.
    *Trade-off:* el insight de Trade Marketing pierde el paralelismo (latencia
    algo mayor en esa tarea) a cambio de ~4x en vez de 15x de costo y mejor
    coherencia narrativa por contexto único.

15. **Patrón de artefactos con `agent_findings` (Sección 12.7, nueva).**
    *Qué:* los subagentes escriben hallazgos completos a Postgres (bajo RLS) y
    devuelven solo `finding_id` + resumen de una línea; DDL y políticas incluidos.
    *Por qué:* reduce el input del orquestador en un orden de magnitud (palanca
    directa del COGS) y evita que datos completos transiten por contextos
    conversacionales que no los necesitan (menor superficie de exposición entre
    Partners).
    *Trade-off:* el orquestador razona sobre resúmenes — si un resumen es pobre,
    puede perder matices; mitigado con lectura puntual bajo demanda
    (`get_finding`) y con el grader de Outcomes verificando que los hallazgos
    referenciados existan.

16. **Observabilidad sin contenido conversacional (Sección 12.8, nueva).**
    *Qué:* tabla `agent_run_metrics` alimentada por eventos de la API de CMA
    (tokens por request, threads, duración, errores de herramienta, outcomes) —
    sin ninguna columna de contenido, con esa ausencia protegida como contrato.
    *Por qué:* trazabilidad operativa y control de COGS eran necesarios, pero
    espejear conversaciones habría creado un canal de datos entre contextos que el
    RLS no gobierna y un pasivo de confidencialidad frente a Asset Owners y
    Partners.
    *Trade-off:* el debugging profundo de un incidente requiere break-glass +
    correlación con la traza retenida por Anthropic, en vez de leer logs propios —
    más fricción a cambio de una historia de confidencialidad defendible.

17. **Metodología de evaluación de calidad del Copiloto/Enjambre (Sección 12.9,
    nueva; gate en 8.4).**
    *Qué:* ~20 casos golden por vertical, LLM-as-judge con rúbrica de criterios
    binarios (exactitud / uso de fuentes y alcance / completitud; umbral 100% en
    alcance), firma humana por release, Outcomes de CMA como control continuo en
    producción, y todo bug de calidad convertido en caso de regresión.
    *Por qué:* el pipeline solo probaba aislamiento (pgTAP); la calidad de
    respuestas — el producto que se vende — no tenía ningún gate.
    *Trade-off:* cada release que toque prompts/modelos/herramientas paga el costo
    de la corrida de evaluación y una revisión humana; asumido como costo fijo de
    QA (es pequeño frente al costo reputacional de una respuesta que cite datos
    fuera de alcance).

18. **Motor de Acciones (Sección 12.10, nueva; Fase 3 del roadmap).**
    *Qué:* reglas umbral por tenant/partner sobre agregados y hallazgos, canales
    WhatsApp Business API / Slack / correo, herramienta MCP `trigger_action` con
    catálogo scoped por RLS, y `action_log` auditada.
    *Por qué:* brecha competitiva directa — Agrex.ai ya vende alertas automáticas
    sin humano en el loop (WhatsApp/Slack/SMS, ERP); sin esto, la paridad
    funcional declarada en la Sección 1 era falsa.
    *Trade-off:* "sin humano en el loop" se acota a ejecución dentro de un
    catálogo definido por humanos (no acciones libres inventadas por el agente) —
    se cede una fracción del titular de marketing a cambio de una superficie de
    riesgo auditable; la integración de escritura directa a ERPs se difiere a
    webhook firmado (evita asumir responsabilidad sobre sistemas de terceros en el
    MLP).

19. **Fase 4 agregada al roadmap (Sección 13).**
    *Qué:* el Enjambre Enterprise se separa como fase post-MLP con piloto pagado y
    validación de COGS medido antes de venta general.
    *Por qué:* el recálculo de 10.1 demuestra que el riesgo financiero del plan
    insignia se concentra en supuestos de consumo de tokens que solo la operación
    real confirma.
    *Trade-off:* el Plan Enterprise llega al mercado una fase más tarde; a cambio,
    llega con margen confirmado en vez de estimado.

#### A.4 Verificaciones realizadas en esta iteración

| Afirmación | Método | Resultado |
| --- | --- | --- |
| Pricing por modelo (Haiku 4.5, Sonnet 4.6/5, Opus 4.8), caching 0.1x/1.25x/2x, Batch 50% | Documentación oficial de pricing de Anthropic (2026-07-18) | Confirmado; Sonnet 5 intro $2/$10 hasta 2026-08-31 |
| Runtime Managed Agents $0.08/hora-sesión, solo estado `running`; tokens ≈ 85-90% del costo | Documentación oficial de pricing | Confirmado (incl. ejemplo oficial trabajado) |
| Batch API no aplicable a sesiones de Managed Agents | Documentación oficial de pricing | Confirmado explícitamente |
| Claude 3.5 Sonnet retirado | Catálogo oficial de modelos | Confirmado (retirado 2025-10-28) |
| Multiagent: beta pública `managed-agents-2026-04-01`; threads comparten contenedor/filesystem; vaults por sesión; máx. 20 roster / 25 threads / 1 nivel | Documentación oficial de Managed Agents | Confirmado |
| Vaults: credenciales nunca entran al sandbox; inyección en egreso; `environment_variable` no soportado en self-hosted | Documentación oficial de Managed Agents | Confirmado |
| Multiplicadores ~15x (multiagente) y ~4x (agente) vs chat | Anthropic, "How we built our multi-agent research system" (blog de ingeniería) | Adoptado como base del modelo de costos |
| Capa agéntica de Agrex.ai: NL queries, monitoreo autónomo, acciones WhatsApp/Slack/SMS y ERP; 20-30% reducción de colas | Material público de Agrex.ai (2026-07-18) | Confirmado; incorporado a 12.10 |
| DDL Sección 8 (tablas, funciones LEAKPROOF, políticas RLS, semillas, consultas de tests) | Ejecución real contra PostgreSQL 16 | Corre sin errores (TimescaleDB validado documentalmente) |
| Elegibilidad ZDR/HIPAA BAA de Managed Agents | No re-verificable con las fuentes de esta iteración | Se mantiene la afirmación de v3.1 con marca de "re-confirmar con Anthropic antes del vertical banca" (Sección 12.3) |
