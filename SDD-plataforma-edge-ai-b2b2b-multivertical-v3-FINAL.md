# System Design Document (SDD) v3.2 — FINAL

## Plataforma de Analítica "Hardware-Free" vía Edge AI — Motor Base Multi-Vertical (B2B2B)

> **Estatus del documento:** VERSIÓN FINAL. Fuente única de verdad para desarrollo
> técnico y salida al mercado. Toda afirmación sobre productos de Anthropic fue
> verificada contra documentación oficial vigente al 2026-07-18 (pricing, estado de
> betas, modelos activos/retirados). Toda afirmación competitiva fue calibrada contra
> el material público de Agrex.ai vigente a la misma fecha. Los cambios de esta
> iteración están detallados en el **Apéndice A — Changelog** al final del documento.

---

### Nota de versión

**v3.2-FINAL (esta iteración):** auditoría integral en tres frentes y cierre del
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

---

### 4. Usuarios y Roles (IAM - Identity and Access Management)

El modelo de identidad ahora tiene **dos niveles de tenancy**: el Asset Owner
(tenant maestro, cliente contractual directo) y, opcionalmente, uno o más Partners
(sub-tenants) que el propio Asset Owner da de alta dentro de su cuenta.

| Rol | Nivel | Descripción | Permisos Clave |
| --- | --- | --- | --- |
| **SuperAdmin (Plataforma)** | Plataforma | Administrador central del sistema SaaS. No es un registro de la tabla `users` (ver Sección 8.5) — es acceso interno de la plataforma. | Crear Asset Owners (tenants maestros) y Resellers. Asignar el `vertical_type` de cada cliente. Registrar IDs de Edge Gateways. Mapear polígonos (zonas/ROIs) sobre fotogramas de cámaras. Gestionar flota (actualizaciones OTA de código y de modelos). Publicar nuevos checkpoints en el Model Registry. Único rol con acceso *break-glass* auditado cross-tenant. |
| **Reseller Admin (Distribuidor/Canal)** *(nuevo, inferido — validar)* | Reseller | Socio de canal que onboardea y da soporte comercial a una cartera de Asset Owners. | Ve metadata de gestión (nombre, estado, sedes) de los Tenants bajo su `reseller_id`. **No ve telemetría ni tableros operativos de esos Tenants por defecto** — mismo principio de mínimo privilegio que un Partner; el Asset Owner tendría que habilitárselo explícitamente si en el futuro se decide lo contrario. Puede iniciar el alta de un nuevo Tenant en su cartera, sujeto a aprobación del SuperAdmin. |
| **Tenant Admin (Asset Owner / Cliente Maestro)** | Tenant | Gerente de Operaciones, TI o Seguridad del dueño de la infraestructura (supermercado, banco, bodega, centro comercial). | Visualizar tráfico, colas, ocupación y mapas de calor de **toda** su infraestructura (todas sus sucursales). Acceso completo al Copiloto sobre sus propios datos. **Backoffice de Usuarios:** crear usuarios `operator`/`viewer` y asignarles una o varias sucursales específicas (ver Sección 8.2). **Módulo de Reventa:** crear, editar, desactivar Partners; asignar o revocar el acceso de cada Partner a zonas (ROIs) específicas, a nivel de sucursal completa o de zona individual. |
| **Tenant Operator/Viewer Regional** *(nuevo)* | Tenant, acotado | Gerente o analista de una o varias sucursales específicas, sin visibilidad del resto de la cadena. | Visualiza tráfico, colas y mapas de calor **únicamente de las sucursales que el Tenant Admin le asignó** vía `user_site_assignments` (Sección 8.2). `operator` puede además ajustar configuración operativa de sus sucursales asignadas; `viewer` es de solo lectura. |
| **Partner Admin (Sub-Tenant / Socio Comercial)** | Sub-Tenant | Gerente de Trade Marketing, Category Manager, o equivalente del socio comercial que opera dentro del espacio del Asset Owner (ej. Nestlé dentro de La Torre; una aseguradora dentro de una sucursal bancaria). Es dado de alta **por el Asset Owner**, nunca directamente por el SuperAdmin. | Visualizar **únicamente** los datos de las zonas (ROIs) que el Asset Owner le asignó explícitamente — puede ser una sucursal completa o zonas puntuales dentro de ella (Sección 8.3). Acceso al Copiloto acotado a ese mismo alcance. No puede ver datos operativos internos del Asset Owner ni de otros Partners. |
| **Viewer (Analista)** | Tenant, Sub-Tenant o Reseller | Usuario de solo lectura, existe en cualquiera de los tres niveles. | Consultar y exportar reportes en PDF/CSV dentro del alcance de su nivel. Sin permisos de configuración ni de gestión de Partners/usuarios. |
| **Service Account (Edge Gateway)** | Sistema | Sistema físico en sucursal/bodega. | Autenticación máquina a máquina (JWT/API Key) para publicar telemetría y para solicitar al Model Manager la descarga del modelo del vertical asignado. |

**Regla de aislamiento explícita (ampliada en v3.0):** ningún rol por debajo del
SuperAdmin tiene visibilidad fuera de su alcance asignado — ni siquiera por omisión.
Concretamente: (a) un Partner Admin nunca ve datos operativos internos del Asset
Owner que no correspondan a una zona compartida, ni datos de otro Partner del mismo
Asset Owner; (b) un Tenant Operator/Viewer Regional nunca ve sucursales fuera de su
asignación, aunque pertenezcan al mismo tenant; (c) un Reseller Admin nunca ve
telemetría de sus Tenants por defecto; (d) nadie ve la existencia de Asset Owners,
Partners o Resellers ajenos a su propia jerarquía. La implementación completa de
esta regla vía Row-Level Security está en la Sección 8.

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
   las URL RTSP y el `vertical_type` asignado.
5. **Descarga del Modelo (nuevo):** el Edge Gateway, al validar sus credenciales,
   consulta al Model Manager en la nube qué checkpoint corresponde a su vertical,
   descarga el archivo `.pt` correspondiente (ej. `yolo_retail.pt`), verifica su
   checksum, y lo carga en memoria. Solo este modelo permanece cargado.
6. **Validación:** el Edge Gateway verifica la conexión RTSP, inicia los hilos de
   inferencia con el modelo correcto ya cargado, y envía un latido (Heartbeat) de
   estado "Online" a la nube.

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

#### Flujo 3: Módulo de Reventa — El Asset Owner Provisiona a un Partner (nuevo)

1. **Ingreso:** el Asset Owner Admin inicia sesión y entra a la sección "Partners" de
   su portal.
2. **Alta de Partner:** crea un nuevo Partner (ej. "Nestlé Guatemala"), define un
   nombre de contacto y un correo de invitación.
3. **Asignación de Alcance:** selecciona, de la lista de ROIs de sus propias sedes,
   cuáles quedan visibles para ese Partner (ej. únicamente los ROIs etiquetados como
   góndolas de lácteos en las 12 tiendas donde Nestlé tiene presencia). Esta acción
   cambia el `owner_type` de esos ROIs a `PARTNER` y su `owner_id` al Partner recién
   creado — sin afectar la visibilidad que el propio Asset Owner tiene sobre esos
   mismos ROIs, que conserva siempre.
4. **Invitación:** el sistema envía una invitación al Partner con credenciales
   propias y el rol `Partner Admin`, acotado exactamente a lo asignado en el paso 3.
5. **Gestión continua:** el Asset Owner puede revocar o ampliar el acceso de un
   Partner en cualquier momento; el cambio se refleja de inmediato en lo que ese
   Partner puede consultar.

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
  │       PARTNER; asignación de      │  de 2 niveles)           │
  │       sedes a usuarios operator/  └─ Time-Series DB           │
  │       viewer regionales              (tracking_coordinates,   │
  │                                       PostgreSQL+Timescale)   │
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
* **Base de Datos Principal:** `PostgreSQL` con la extensión `TimescaleDB`
  (optimizada para series de tiempo).
* **Model Registry (nuevo):** bucket `S3` versionado, con una API ligera de
  manifiesto (`GET /v1/models/{vertical_type}/manifest`) que devuelve la versión más
  reciente del checkpoint, su URL de descarga firmada y su checksum SHA256.
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
* **Cloud Hosting:** `AWS (EC2/ECS, RDS, S3)` — el mismo `S3` que almacena snapshots
  de auditoría ahora también aloja el Model Registry, en un bucket/prefijo separado
  con políticas de acceso propias.

#### 7.1 Gestión de Flota (Fleet Management) y Actualizaciones

Administrar cientos de Edge Gateways de forma manual es inviable. Con el Motor
Multi-Vertical, **hay dos tipos de actualización independientes** que la flota debe
soportar: actualización de **código** (la imagen Docker del Edge Gateway) y
actualización de **modelo** (un nuevo checkpoint `.pt` para un vertical dado).

* **Mecanismo OTA (Over-The-Air):** se utilizará un orquestador de Edge Computing
  (como Portainer Edge, BalenaOS, o un cliente ligero de AWS IoT Greengrass) para las
  actualizaciones de código.
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

---

### 8. Modelo de Datos y Arquitectura Multi-Tenant (Esquema Físico Ejecutable)

Esta sección reemplaza el esquema conceptual de v2.0 con el **esquema físico
completo**, en DDL ejecutable de PostgreSQL/TimescaleDB. Es la referencia autoritativa
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
zone_dwell_sessions            tracking_coordinates (hypertable, vía camera_id)

users (tenant_id | reseller_id, + partner_id opcional; role: admin/operator/viewer)
    │ N
    │ N  (tabla puente)
    ▼
user_site_assignments (user_id, site_id)

model_registry_entries (catálogo de checkpoints .pt por vertical_type)
edge_gateways (site_id, vertical_type, current_model_version, status, channel)
platform_admins + break_glass_audit_log (acceso interno auditado, Sección 8.5)
```

Extensiones de PostgreSQL requeridas antes de correr el DDL siguiente:

```sql
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS citext;
CREATE EXTENSION IF NOT EXISTS timescaledb;
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
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id   UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    name        TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','revoked')),
    invited_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_partners_tenant_id ON partners(tenant_id);

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
-- Time-Series: tracking_coordinates (hypertable) y agregados batch
-- ============================================================
CREATE TABLE tracking_coordinates (
    "time"     TIMESTAMPTZ NOT NULL,
    camera_id  UUID NOT NULL REFERENCES cameras(id) ON DELETE CASCADE,
    person_id  TEXT NOT NULL,
    x          INTEGER NOT NULL,
    y          INTEGER NOT NULL,
    PRIMARY KEY (camera_id, "time", person_id)
);
SELECT create_hypertable('tracking_coordinates', 'time');
CREATE INDEX idx_tracking_camera_time ON tracking_coordinates(camera_id, "time" DESC);

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

La misma política aplica (con el mismo patrón) a `sites`, `cameras` y `zones` como
tablas — se omiten aquí por brevedad, pero siguen exactamente esta lógica de ramas
OR, incluida la rama de "zonas cedidas siguen visibles para el tenant dueño".

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
de base de datos. El Motor Matemático (batch) escribe `zone_dwell_sessions` bajo un
rol de servicio con su propia política `FOR INSERT` equivalente (scoped por la
cadena `zone → camera → site` del lote en proceso).

**Alcance de Partner a nivel de sucursal completa:** como `zones.owner_partner_id`
se asigna por zona individual, para "asignarle una sucursal completa a una marca" el
Módulo de Reventa simplemente crea/reasigna **todas** las zonas de esa sucursal al
mismo `partner_id` en una sola operación — no requiere una tabla `partner_site_
assignments` separada, evitando dos fuentes de verdad para el mismo concepto de
scope.

---

#### 8.4 Gestión de Ambientes (Dev/QA/Staging/Prod)

**Separación por ambiente — instancias, no solo esquemas:**

| Ambiente | Aislamiento recomendado | Justificación |
| --- | --- | --- |
| **Dev (local)** | Contenedor Docker efímero, un solo esquema | Ciclo de vida de minutos; no vale la pena una instancia completa. |
| **QA** | Instancia/proyecto Postgres separado | Corre la suite de aislamiento (pgTAP) contra un clon real de la topología de extensiones (Timescale, RLS) sin compartir recursos con Staging. |
| **Staging** | Instancia/proyecto Postgres separado, con IaC idéntico a Prod | Debe ser un espejo fiel de Prod (misma versión de Postgres/Timescale, mismas políticas RLS) — es el último gate antes de producción. |
| **Prod** | Instancia dedicada, backups PITR | — |

Se descarta la separación por esquema-único-compartido entre QA/Staging/Prod: el
riesgo de una política RLS mal aplicada en un ambiente "de prueba" que en realidad
comparte el mismo clúster que producción no vale el ahorro de costo, dado que la
sensibilidad del dato (rastreo de personas) es alta.

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

**Pipeline de migraciones con rollback:** cada cambio de esquema/política vive como
un par de archivos versionados `NNN_descripcion.up.sql` / `NNN_descripcion.down.sql`
(herramienta agnóstica — Sqitch, Flyway o `node-pg-migrate` funcionan igual de bien
sobre este patrón). El pipeline de CI, en orden:

1. Levanta una instancia Postgres+Timescale efímera.
2. Corre todas las migraciones `up` en orden.
3. Corre la suite pgTAP completa (los cuatro tests de arriba y sus variantes) — si
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
validando que la política de `retention`/`compression` de TimescaleDB (Sección 8.5)
no degrade la latencia de las vistas agregadas de 8.1 a medida que crece el
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

**Retención y purga de `tracking_coordinates`:** implementa técnicamente la política
de negocio ya definida en la Sección 10.2 (13 meses para telemetría analítica,
30 días para snapshots en S3):

```sql
SELECT add_retention_policy('tracking_coordinates', INTERVAL '13 months');
-- La purga de snapshots en S3 se gestiona vía lifecycle policy del bucket, no en SQL.

-- Compresión columnar (nuevo, v3.2): la telemetría con más de 7 días se comprime.
-- TimescaleDB reporta ratios típicos de >90% en series de tiempo de este perfil
-- (columnas repetitivas: camera_id, person_id incremental, coordenadas acotadas).
-- Esta es la palanca principal que mantiene el costo de almacenamiento dentro del
-- rango de $15-27/sede/mes de la Sección 10.1 con 13 meses de retención.
-- Nota de compatibilidad: segmentar por la columna de mayor cardinalidad de acceso.
ALTER TABLE tracking_coordinates SET (
  timescaledb.compress,
  timescaledb.compress_segmentby = 'camera_id',
  timescaledb.compress_orderby   = '"time" DESC'
);
SELECT add_compression_policy('tracking_coordinates', INTERVAL '7 days');
```

La compresión no altera el RLS: las políticas se evalúan igual sobre chunks
comprimidos, y la suite pgTAP de la Sección 8.4 corre también contra datos ya
comprimidos en el ambiente de pruebas de carga (donde la política de compresión
está activa) para verificar que no exista divergencia de comportamiento.

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
  momento exacto de la inferencia local, TimescaleDB insertará la data antigua sin
  afectar la integridad de los gráficos históricos en el dashboard.

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

* **Infraestructura Cloud (AWS):** balanceo, backend, PostgreSQL/TimescaleDB
  gestionado (con compresión columnar activa, Sección 8.5, que es lo que hace
  sostenible la retención de 13 meses), Model Registry (S3 + tráfico de descarga de
  checkpoints, infrecuente y de pocos MB): **~$15 - $27 USD / mes por sede**.
* **Ancho de Banda de Subida:** JSON en kilobytes + snapshots bajo demanda:
  **~$2 USD / mes por sede**.

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
* **Encriptación en Reposo:** las bases de datos cloud (PostgreSQL/TimescaleDB)
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

1. Cada subagente escribe su resultado completo en Postgres/TimescaleDB mediante
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
CREATE POLICY agent_findings_write ON agent_findings
FOR INSERT WITH CHECK (
  agent_findings.tenant_id = app_current_tenant_id()
  AND ( app_current_partner_id() IS NULL
        OR agent_findings.partner_id = app_current_partner_id() )
);
```

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
```

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
  `agent_findings`: "si la cola de cajas supera N personas por M minutos →
  WhatsApp al gerente de turno"; "si el enjambre escribe un hallazgo
  `action_required` de quiebre de stock en una zona de Nestlé → notificar al
  contacto del Partner". Evaluadas por el Motor Matemático en su mismo ciclo batch
  (1-5 min) — sin infraestructura nueva de streaming, coherente con la Sección 6.
* **Canales del MLP:** WhatsApp Business API (canal dominante en CENAM — es el
  canal, no el email), Slack (incoming webhooks) y correo. Roadmap: SMS y webhooks
  salientes genéricos para integración ERP (la actualización directa de ERP de
  terceros queda fuera del MLP; se expone el webhook firmado para que el cliente
  integre).
* **Acciones originadas por el Enjambre (paridad "agéntica" real):** los agentes
  no improvisan acciones — disponen de una herramienta MCP `trigger_action(rule_
  template, target, payload)` cuyo catálogo está acotado por tenant/partner vía el
  mismo scoping RLS de 12.2: un agente solo puede disparar acciones del catálogo
  de su propio contexto, hacia destinatarios registrados por ese contexto. "Sin
  humano en el loop" aplica a la *ejecución* (nadie aprueba cada alerta), no a la
  *definición* (todo tipo de acción y destinatario fue configurado explícitamente
  por un humano del tenant). Esto nos da el titular competitivo de Agrex — alertas
  automáticas accionadas por IA — con una superficie de riesgo acotada y auditable.
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

---

### 13. Roadmap de Implementación por Fases

1. **Fase 1: Tubería de Datos Básica, Model Manager, Esquema Físico y Pruebas
   Off-Spec (MLP Interno)**
   * *Objetivo:* instalar el Edge Gateway (Docker) en una computadora de oficina
     genérica vieja para testear el "Lowest Common Denominator". Integrar YOLO Nano +
     ByteTrack, **construir el Model Manager con soporte para un único vertical
     piloto (`yolo_retail.pt`)**, y probar el mecanismo de cola local offline
     (SQLite). En paralelo, **levantar el esquema físico completo de la Sección 8**
     (`resellers` → `tenants` → `sites` → `cameras` → `zones` →
     `tracking_coordinates`, más `users`/`user_site_assignments`), con RLS activo
     desde el primer commit y la suite pgTAP de aislamiento corriendo en CI — no se
     pospone la seguridad multi-tenant a una fase posterior.
   * *Entregable:* Base de Datos Time-Series recibiendo batches de telemetría de
     forma estable sin colapsar la PC del cliente, con el Edge Gateway resolviendo y
     cargando su modelo de vertical correctamente al arrancar, y los tres niveles de
     aislamiento (tenant/site/partner) validados por pruebas automatizadas antes de
     escribir una sola pantalla de UI.

2. **Fase 2: El Producto Transaccional B2B2B (Mapeo, Backoffice, Módulo de Reventa
   y Tableros)**
   * *Objetivo:* crear la herramienta de administración para dibujar los polígonos
     (zonas) sobre el video. Desarrollar el cálculo lógico (batch) de intersecciones
     en la nube, alimentando `zone_dwell_sessions`. **Construir el Backoffice de
     Usuarios** (alta de usuarios `operator`/`viewer`, asignación granular a
     sucursales vía `user_site_assignments`) **y el Módulo de Reventa** (alta/gestión
     de Partners y asignación de zonas o sucursales completas) dentro del portal del
     Asset Owner. Desplegar los tableros frontend (React), incluyendo las vistas
     agregadas de comparación inter-sucursal (Sección 8.1).
   * *Entregable:* Dashboard visual mostrando Mapas de Calor, Dwell Time real por
     zona y comparativos entre sucursales, funcionando correctamente para los tres
     perfiles de prueba (Tenant Admin, Operator regional, Partner), listo para venta
     comercial bajo el esquema B2B2B.

3. **Fase 3: Gestión de Flota, Registry Multi-Vertical, Operación Interna y Valor
   Premium Cognitivo**
   * *Objetivo:* implementar el orquestador OTA para gestionar los Edge Nodes
     remotamente, incluyendo la distribución independiente de actualizaciones de
     código, modelo y configuración de tracking (canal `canary`/`stable`, Sección
     8.4). **Formalizar el Model Registry como servicio versionado**, dejando la
     arquitectura lista para admitir un segundo vertical sin cambios de código.
     **Poner en marcha los mecanismos de Operación Interna de la Sección 8.5**
     (break-glass auditado, retención/purga automatizada, cifrado de credenciales de
     cámara, observabilidad de accesos denegados y salud de flota) antes de aceptar
     el primer cliente real en producción. Conectar la API de Anthropic para los
     módulos de chat (Copiloto en vivo, Messages API + Haiku 4.5) y auditorías
     visuales de stock (Batch API, Sección 12.5), respetando el aislamiento de tres
     niveles. **Construir el Motor de Acciones** (Sección 12.10: reglas umbral +
     canales WhatsApp/Slack/correo + `action_log` auditada) — es requisito de
     paridad competitiva del MLP, no un extra. **Levantar la suite de evaluación de
     calidad del Copiloto** (Sección 12.9: ~20 casos golden de retail + judge con
     rúbrica + firma humana) integrada como gate del pipeline antes del primer
     release comercial.
   * *Entregable:* sistema End-to-End autónomo, gestionable a escala, produciendo
     insights cognitivos y acciones automáticas auditables, con la infraestructura
     de Model Registry validada para onboardear un segundo vertical, y con los
     controles de operación interna (Sección 8.5) y el gate de calidad (12.9)
     verificados — no solo documentados — antes del primer cliente en producción.

4. **Fase 4: Enjambre Cognitivo del Plan Enterprise (post-MLP)**
   * *Objetivo:* implementar la arquitectura completa de la Sección 12 sobre
     Managed Agents: sesiones por contexto de aislamiento (12.1-12.2), scheduled
     deployments para la corrida diaria (12.4), subagentes según la matriz de
     paralelizabilidad (12.6), patrón de artefactos con `agent_findings` (12.7),
     observabilidad sin contenido con `agent_run_metrics` (12.8) y Outcomes como
     control de calidad continuo (12.9). Validar el COGS real por sede contra el
     modelo de la Sección 10.1 durante un piloto pagado antes de abrir la venta
     general del Plan Enterprise.
   * *Entregable:* Plan Enterprise comercializable con COGS medido (no estimado),
     márgenes confirmados ≥ 84%, y el Copiloto en vivo + Enjambre operando por los
     dos caminos de latencia definidos en 12.4.

---

### Apéndice A — Changelog de esta iteración (v3.1 → v3.2-FINAL)

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
