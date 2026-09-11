# Plan: roles jerárquicos para el panel

Estado: **diseño aprobado, sin implementar**. Fases en §7.

Decisiones del usuario, cerradas: una sola iglesia (Life), 2 congregaciones, árbol
Congregación → Red → Subred → Grupo de conexión, cada red bajo una sola congregación.
Roles: Apóstol (todo), Pastor (su congregación), Líder de Red (su red), Líder (el nodo
asignado y lo que cuelgue), Estaca (su grupo, permisos fijos y reducidos).
El sitio público **no cambia**: la jerarquía gobierna quién administra, no qué ve el visitante.

## 1. Modelo

Un solo `OrgNode` autorreferenciado con `kind` y **camino materializado** (`path`), en vez de
una tabla por nivel. Con tabla por nivel, «todo lo que cuelga de X» es un UNION de cuatro
consultas y `Membership`/`Event` necesitan cuatro FK nullable; con camino materializado es un
`path__startswith` sobre un índice, y el mismo SQL sirve en SQLite y PostgreSQL. Se descartan
el CTE recursivo (Django 5.2 no lo expone sin SQL crudo) y `ltree` (solo PostgreSQL, rompería
los tests).

```python
class OrgNode(models.Model):
    KINDS = ['organization', 'congregation', 'network', 'subnetwork', 'group']
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    parent = models.ForeignKey('self', null=True, blank=True, related_name='children', on_delete=models.PROTECT)
    kind = models.CharField(max_length=20)
    name = models.CharField(max_length=120)
    # Camino "/uuid/uuid/": resuelve el subárbol con un prefijo indexado. 255 y no 200:
    # cinco niveles ya ocupan 186 caracteres y un sexto no cabría.
    path = models.CharField(max_length=255, unique=True, editable=False)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ['path']
        constraints = [
            models.UniqueConstraint(fields=['kind'], condition=Q(kind='organization'), name='una_sola_organizacion'),
            models.UniqueConstraint(Lower('name'), 'parent', name='nombre_unico_entre_hermanos'),
        ]
        indexes = [models.Index(fields=['path'])]
```

`path` se calcula en `save()` y no es editable por la API. La relación `kind`↔`parent.kind` es
cross-row y no cabe en un `CheckConstraint`: se valida en `validation.py` con una tabla
`PADRE_VALIDO`. Existe un nodo raíz sintético `kind='organization'` (Life): elimina el caso
especial «ámbito nulo = toda la organización» y da destino inmediato a los eventos huérfanos.

```python
class Membership(models.Model):
    ROLES = ['apostol', 'pastor', 'lider_red', 'lider', 'estaca']
    user = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='memberships', on_delete=models.CASCADE)
    node = models.ForeignKey(OrgNode, related_name='memberships', on_delete=models.PROTECT)
    role = models.CharField(max_length=20)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['user', 'node'], name='una_membresia_por_nodo')]
```

El ámbito es **polimórfico**: la membresía apunta a cualquier nodo, el rol decide qué se puede
hacer y el nodo hasta dónde llega. Varias membresías: unión de ámbitos y de permisos.

**Evento conjunto: un dueño más invitados**, no varios ámbitos simétricos. Con N ámbitos iguales
no hay respuesta única a «quién manda» y perder uno puede dejar el evento sin nadie.

```python
# en Event
owner = models.ForeignKey(OrgNode, related_name='events', on_delete=models.PROTECT, null=True)  # null solo durante la migración
guests = models.ManyToManyField(OrgNode, through='EventGuest', related_name='guest_events')
```

`Registration` no cambia: hereda el ámbito de su evento. Por eso `Event` no tiene FK a `User`
y quitarle la membresía a quien creó un evento no rompe nada.

Se descartan `django.contrib.admin` (abriría una segunda superficie sin ámbito sobre los mismos
datos personales) y `auth.Permission`/`Group` (permisos globales por modelo, sin dimensión de
fila: haría falta igualmente toda la capa de ámbito y quedarían dos fuentes de verdad).

## 2. Migración de lo existente

`migrate` corre solo al arrancar el contenedor y el contenedor viejo puede seguir sirviendo
durante ese rato. Expand → backfill → contract, con relleno repetido antes de apretar:

1. `0003_org_expand` — crea OrgNode, Membership, EventGuest; añade `Event.owner` **null=True**.
2. `0004_org_seed` — crea la raíz con `SiteSettings.organization`; asigna `owner=raíz` a todo
   evento sin dueño; da `apostol` en la raíz a cada usuario `is_staff` sin membresía.
3. `0005_org_contract` — repite el relleno (cubre lo insertado entre 0003 y 0005) y después
   `AlterField(owner, null=False)`.

Los 6 eventos de producción quedan en la raíz: solo el Apóstol los ve, y desde ahí los reasigna.
Un Pastor no hereda eventos que quizá no son suyos. `ensure_admin` pasa a garantizar de forma
idempotente raíz + membresía de Apóstol.

## 3. Dónde se aplica la autorización

`server/events/scope.py`, con un `Scope` construido una vez por request:

```python
class Scope:
    permissions: frozenset   # unión de PERMISOS_POR_ROL de todas las membresías
    prefixes: tuple          # paths de los nodos de las membresías
    def nodes(self)          # OrgNode filtrado por Q(path__startswith=p) OR-eados
    def events(self)         # propios e invitados
    def owned_events(self)   # solo propios
```

`endpoint(methods, staff=True, permission=None)` decide **la acción** en un único sitio.
**Las filas las decide el queryset**, no la vista: `get_event()` parte de `scope.events()` o de
`scope.owned_events()`, así que un id de otro ámbito da **404, no 403** — no se filtra ni la
existencia del recurso.

Puntos a cambiar en `views.py`: `admin_events` (lista y creación), `admin_event` (PUT sobre
eventos propios; el invitado es solo lectura), `registrations_query` (base común de
`admin_registrations` y `export_registrations`) y **`private_file`**, que hoy deja a cualquier
staff descargar cualquier adjunto.

## 4. Matriz de permisos

| Acción | Permiso | Apóstol | Pastor | Líder de Red | Líder | Estaca |
|---|---|:--:|:--:|:--:|:--:|:--:|
| `admin_settings` PUT | `settings.edit` | ✓ | – | – | – | – |
| `admin_events` GET | `event.view` | ✓ | ✓ | ✓ | ✓ | ✓ |
| `admin_events` POST | `event.create` | ✓ | ✓ | ✓ | ✓ | – |
| `admin_event` PUT | `event.edit` | ✓ | ✓ | ✓ | ✓ | ✓ |
| pasar a `published` / `featured` | `event.publish` | ✓ | ✓ | ✓ | ✓ | – |
| fijar `owner` / `guests` | `event.assign` | ✓ | ✓ | ✓ | – | – |
| `admin_images` POST | `event.edit` | ✓ | ✓ | ✓ | ✓ | ✓ |
| `admin_registrations` GET | `registration.view` | ✓ | ✓ | ✓ | ✓ | ✓ |
| `private_file` GET | `registration.view` | ✓ | ✓ | ✓ | ✓ | ✓ |
| `export_registrations` GET | `registration.export` | ✓ | ✓ | ✓ | ✓ | – |
| nodos (CRUD) | `node.manage` | ✓ | ✓ | ✓ | ✓ | – |
| usuarios y membresías | `user.manage` | ✓ | ✓ | ✓ | ✓ | – |

Todo ✓ está acotado al subárbol de la membresía. Que solo el Apóstol cree congregaciones cae del
ámbito, no es una regla aparte. `PERMISOS_POR_ROL` es un `dict` constante: no hay concesiones
caso por caso ni tabla de permisos en base.

**`owner` y `guests` son inmutables sin `event.assign`, también en PUT.** Sin esto, una Estaca
con `event.edit` podría reasignar su evento a otro nodo y sacárselo de encima, o un Líder
moverlo fuera de su red. Es la vía de escalada más obvia del diseño.

## 5. Frontend

`Session` gana `permissions` y `memberships`; `event_data()` gana un parámetro `admin` para que
las vistas públicas sigan devolviendo **exactamente el mismo JSON de hoy** y no se filtre
estructura interna. Nuevo `GET /api/admin/nodes` para los selectores. En `Admin.tsx`, un helper
`can(session, permission)` filtra pestañas y controles. **El gateado del cliente es cosmético**:
la autoridad es el servidor, y §9 lo prueba.

## 6. Usuarios

Hace falta pantalla: hoy solo `ensure_admin` crea cuentas. Regla única de quién invita a quién:
**puedes conceder una membresía en un nodo de tu ámbito y con un rol estrictamente inferior al
tuyo**, y solo editar usuarios cuyas membresías estén todas dentro de tu ámbito. `is_staff` lo
pone siempre el servidor; nadie edita su propio rol. No hay correo saliente en el proyecto, así
que la contraseña inicial se entrega fuera de banda y cada quien la cambia después.

## 7. Fases

1. **Modelo y migraciones.** Sin cambio de comportamiento observable. Verificar con
   `makemigrations --check --dry-run`, `migrate` sobre un dump restaurado de Supabase, y las 60
   pruebas en verde tras dar Apóstol al staff de los tests y `owner` a `seed_demo`.
2. **Motor de autorización** (`scope.py`, `security.py`, filtrado en `views.py` incluido
   `private_file`). Las 60 anteriores siguen verdes porque el Apóstol en la raíz reproduce el
   comportamiento actual.
3. **Nodos**: API y pestaña Organización. Crear las 2 congregaciones y una red desde el panel.
4. **Ámbito del evento**: `owner`/`guests` en la API de administración y en el editor.
5. **Sesión y gateado de UI.**
6. **Equipo**: usuarios y membresías.

Las fases 1 y 2 se despliegan por separado: si el `migrate` de arranque falla, el rollback es la
imagen anterior sin pérdida de datos.

## 8. Casos borde

- Quitar la membresía a quien creó eventos: no pasa nada, el evento pertenece al nodo.
- Borrar un nodo con hijos o eventos: imposible por `PROTECT`; la API responde 409 y ofrece
  archivar (`active=False`), que conserva historial y eventos.
- Dos membresías: unión de permisos y subárboles; para `user.manage` manda el rango más alto.
- Evento conjunto que pierde un invitado: `EventGuest` es `CASCADE` y no toca al dueño.
- Ventana de despliegue entre 0003 y 0005: mitigada por el relleno repetido dentro de 0005.
- La Estaca puede editar fecha o aforo de un evento ya publicado sin tener `event.publish`. Es
  coherente con el encargo; si molesta, se refina el permiso, no el modelo.
- Mover un nodo de padre exige reescribir el prefijo de sus descendientes: fuera de alcance.

## 9. Pruebas

- Matriz dirigida por datos en `test_scope.py`: tabla `(rol, endpoint, método, esperado)`
  recorrida con `subTest`. Añadir un permiso a un rol rompe la tabla.
- **Acceso lateral por id directo**, un test por vector: PUT de un evento ajeno → 404; adjunto
  ajeno → 404; `?event_id` ajeno en listado y en exportación → 404; POST con `owner` fuera de
  ámbito → 403; membresía con rol igual o superior al propio → 403; **PUT que intenta cambiar
  `owner` sin `event.assign` → 403**.
- No fuga por listado: con dos congregaciones pobladas, el Pastor de A recibe exactamente sus
  eventos e inscripciones, y su CSV no contiene un solo correo de B.
- Herencia del subárbol: el Líder de Red ve el evento de un grupo tres niveles por debajo; el
  Líder de ese grupo no ve el de la congregación.
- Regresión: las tres suites más `makemigrations --check` en el mismo paso.

## Fuera de alcance

Mover nodos de padre; invitación por correo; bitácora de auditoría; ámbito por inscrito (el
formulario público no pregunta el grupo); cualquier cambio en el sitio público.
