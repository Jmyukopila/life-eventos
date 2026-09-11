# Despliegue

**Un solo servicio.** Django sirve el frontend construido y la API desde el mismo origen, con
whitenoise. Sin proxy inverso, sin CORS, sin segunda plataforma: es la forma con menos piezas
que mantener, y la aplicación está escrita para eso.

Todo el camino es gratuito. Eso tiene tres consecuencias que conviene tener presentes desde el
principio, porque ninguna se arregla con código.

## Las tres verdades del plan gratuito

**Render duerme el servicio** tras 15 minutos sin tráfico y tarda cerca de un minuto en
despertar. El primero que abra el enlace espera; el resto entran rápido mientras haya tráfico.
La interfaz lo dice: si la carga pasa de cuatro segundos, aparece un aviso explicando que el
servidor está despertando, para que no parezca una página rota.

**Supabase pausa los proyectos gratuitos** tras 7 días de poca actividad en la base. No van
lentos: quedan apagados hasta que alguien entre al panel y los restaure, y solo son
recuperables durante 90 días. Un latido periódico lo evita.

**No hay cron.** Los trabajos programados de Render son de pago, así que la purga por retención
—que es una obligación legal, no una comodidad— la dispara un cron externo por HTTP.

## El latido resuelve dos cosas a la vez

`/healthz` hace un `SELECT 1` contra la base. Una llamada periódica a esa URL mantiene vivo el
proyecto de Supabase y de paso despierta Render, gastando minutos de las 750 horas mensuales,
no horas.

Configura en un cron externo gratuito (cron-job.org, UptimeRobot o similar):

```
cada 6 horas   GET  https://TU-APP.onrender.com/healthz
una vez al día POST https://TU-APP.onrender.com/tareas/purga
               cabecera: Authorization: Bearer <TAREAS_TOKEN>
```

**No uses GitHub Actions para esto.** Sus workflows programados se desactivan solos tras 60
días sin actividad en el repositorio, que es exactamente el escenario que quieres cubrir.

## El endpoint de purga

`POST /tareas/purga` con `Authorization: Bearer <TAREAS_TOKEN>`. Se autentica con token, no con
cookie, así que queda fuera de CSRF. Sin `TAREAS_TOKEN` configurado responde 404: no tiene
sentido anunciar una superficie destructiva que nadie puede usar. Con un token de menos de 32
caracteres responde 503, porque no protegería nada.

Devuelve `{"purgados": N, "fallidos": []}`. **Si algún borrado falla responde 500** y deja esas
inscripciones en la base, para que el intento siguiente lo reintente y para que tu cron te
avise: un fallo silencioso ahí son datos personales acumulándose fuera de plazo. Configura el
cron para que te notifique los fallos.

## Variables de entorno

```bash
cp entorno.example .env
```

Los valores que solo puedes poner tú son `DJANGO_SECRET_KEY`, `SUPABASE_SERVICE_ROLE_KEY`,
`DJANGO_ADMIN_PASSWORD` y `TAREAS_TOKEN`. En Render, `render.yaml` genera la clave y el token
solo, y deriva `DJANGO_ALLOWED_HOSTS` del propio servicio; los secretos van marcados
`sync: false` y se pegan en el panel.

## Construir y arrancar

```bash
docker build -t life-eventos .
docker run -d --name life --env-file .env -p 8000:8000 life-eventos
```

El arranque migra, crea `STATIC_ROOT`, recoge estáticos, garantiza el usuario del panel y
levanta gunicorn. Si `DJANGO_ADMIN_PASSWORD` está vacío no toca ningún usuario; si no cumple
los validadores (15 caracteres mínimo), el contenedor aborta en vez de arrancar a medias.

El punto de entrada **acepta un comando**, así que la misma imagen sirve para tareas sueltas:

```bash
docker run --rm --env-file .env life-eventos python /app/server/manage.py purge_expired --execute
```

## Los dos puertos de Supabase

El pooler escucha en dos y no son intercambiables:

- **6543**, modo transacción. Es el de `DATABASE_URL`. Cada sentencia puede caer en una conexión
  distinta, así que Django corre ahí sin cursores de servidor, sin sentencias preparadas y sin
  conexiones persistentes. `settings.py` lo detecta por el número de puerto.
- **5432**, sesión completa. Es el que necesita el DDL. Va en `DATABASE_URL_MIGRATIONS`.

## Storage

Los archivos que sube la gente van a dos buckets de Supabase, que tienen que existir antes del
primer arranque:

| Bucket | Acceso | Tipos | Qué guarda |
|---|---|---|---|
| `event-images` | público | `image/jpeg` | Portadas y galerías |
| `registration-files` | privado | `image/jpeg`, `application/pdf` | Adjuntos de las inscripciones |

`registration-files` es privado porque contiene datos personales. La aplicación nunca expone su
contenido: entrega URLs firmadas con caducidad (`SUPABASE_SIGNED_URL_TTL`, 300 s) y solo a una
sesión de staff.

Sin `SUPABASE_URL` y `SUPABASE_SERVICE_ROLE_KEY` la aplicación escribe en el disco del
contenedor. Arranca igual y no avisa, pero cada redespliegue se lleva todo lo subido.

## Purga por retención

`SiteSettings.retention_days` promete que los datos de una inscripción se borran pasado ese
plazo. La ejecuta el cron externo descrito arriba, o a mano:

```bash
python /app/server/manage.py purge_expired            # simulacro
python /app/server/manage.py purge_expired --execute  # aplica
```

Borra primero el archivo y solo después la fila. Si el borrado en Storage falla, deja la
inscripción en la base y termina con código distinto de cero: quitarla dejaría el adjunto
huérfano en el bucket, fuera de plazo y sin nada que lo referencie.

Para comprobar que un borrado ocurrió de verdad no consultes el objeto por HTTP: Supabase lo
sirve por CDN y puede devolver 200 sobre algo ya borrado. Pregunta a la base:

```sql
select bucket_id, name from storage.objects where bucket_id = 'registration-files';
```

Los cupos ya consumidos no se recalculan al purgar, a propósito: el histórico de asistencia no
es un dato personal.

## Seguridad

`DJANGO_DEBUG=0` activa HSTS, cookies seguras y redirección a HTTPS. Compruébalo:

```bash
python /app/server/manage.py check --deploy
```

La `service_role` key de Supabase se salta las políticas RLS: vive solo en el servidor, nunca
en el frontend ni en el repositorio. Si una credencial ha pasado por un chat, un log o una captura,
rótala — y al cambiar la de la base, regenera `DATABASE_URL` con la contraseña codificada.

## Desarrollo local

Sin cambios: `npm run dev` levanta Vite en 5173 con su proxy al 8000, y
`.venv/bin/python server/manage.py runserver` el backend. En producción es un solo proceso: el
contenedor sirve el `dist` ya construido.
