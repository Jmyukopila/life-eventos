import re
from unittest.mock import patch

from django.test import TestCase, override_settings

from events import storage
from events.security import ApiProblem

SUPABASE_SETTINGS = dict(
    USE_SUPABASE_STORAGE=True,
    SUPABASE_URL='https://proyecto-sintetico.supabase.co',
    SUPABASE_SERVICE_ROLE_KEY='clave-sintetica-de-prueba',
    SUPABASE_BUCKET_PUBLIC='event-images',
    SUPABASE_BUCKET_PRIVATE='registration-files',
    SUPABASE_SIGNED_URL_TTL=300,
)


@override_settings(**SUPABASE_SETTINGS)
class SupabaseStorageTests(TestCase):
    def test_save_public_uploads_with_expected_url_method_headers_and_body(self):
        with patch('events.storage._request', return_value=(200, b'{"Key":"ok"}')) as mocked:
            name = storage.save(b'contenido-jpeg', 'image/jpeg', '.jpg', False)
        self.assertRegex(name, r'^[a-f0-9]{32}\.jpg$')
        (method, url, headers, body), _ = mocked.call_args
        self.assertEqual(method, 'POST')
        self.assertEqual(url, f'https://proyecto-sintetico.supabase.co/storage/v1/object/event-images/{name}')
        self.assertEqual(headers['apikey'], 'clave-sintetica-de-prueba')
        self.assertEqual(headers['Authorization'], 'Bearer clave-sintetica-de-prueba')
        self.assertEqual(headers['Content-Type'], 'image/jpeg')
        self.assertEqual(headers['x-upsert'], 'true')
        self.assertEqual(body, b'contenido-jpeg')

    def test_save_private_uploads_to_the_private_bucket(self):
        with patch('events.storage._request', return_value=(200, b'{"Key":"ok"}')) as mocked:
            name = storage.save(b'%PDF-1.4 contenido', 'application/pdf', '.pdf', True)
        self.assertRegex(name, r'^[a-f0-9]{32}\.pdf$')
        (method, url, headers, body), _ = mocked.call_args
        self.assertEqual(method, 'POST')
        self.assertEqual(url, f'https://proyecto-sintetico.supabase.co/storage/v1/object/registration-files/{name}')
        self.assertEqual(headers['Content-Type'], 'application/pdf')
        self.assertEqual(body, b'%PDF-1.4 contenido')

    def test_save_failure_becomes_api_problem_not_a_raw_traceback(self):
        with patch('events.storage._request', return_value=(500, b'{"error":"boom"}')):
            with self.assertRaises(ApiProblem) as ctx:
                storage.save(b'x', 'image/jpeg', '.jpg', False)
        self.assertNotIn('Traceback', ctx.exception.message)
        self.assertEqual(ctx.exception.status, 502)

    def test_public_url_points_to_the_public_bucket(self):
        url = storage.public_url('abc123abc123abc123abc123abc123ab.jpg')
        self.assertEqual(
            url,
            'https://proyecto-sintetico.supabase.co/storage/v1/object/public/event-images/'
            'abc123abc123abc123abc123abc123ab.jpg',
        )

    def test_signed_url_prefixes_the_relative_path_from_supabase(self):
        with patch('events.storage._request', return_value=(200, b'{"signedURL":"/object/sign/registration-files/f.pdf?token=abc"}')) as mocked:
            url = storage.signed_url('f.pdf')
        self.assertEqual(
            url,
            'https://proyecto-sintetico.supabase.co/storage/v1/object/sign/registration-files/f.pdf?token=abc',
        )
        (method, request_url, headers, body), _ = mocked.call_args
        self.assertEqual(method, 'POST')
        self.assertEqual(request_url, 'https://proyecto-sintetico.supabase.co/storage/v1/object/sign/registration-files/f.pdf')
        self.assertEqual(headers['Content-Type'], 'application/json')
        self.assertEqual(body, b'{"expiresIn": 300}')

    def test_signed_url_failure_becomes_api_problem(self):
        with patch('events.storage._request', return_value=(404, b'{"error":"not_found"}')):
            with self.assertRaises(ApiProblem):
                storage.signed_url('inexistente.pdf')

    def test_delete_of_missing_object_does_not_raise(self):
        with patch('events.storage._request', return_value=(404, b'{"error":"not_found"}')) as mocked:
            storage.delete('inexistente.pdf', True)
        mocked.assert_called_once()
        method, url, headers = mocked.call_args.args[:3]
        self.assertEqual(method, 'DELETE')
        self.assertEqual(url, 'https://proyecto-sintetico.supabase.co/storage/v1/object/registration-files/inexistente.pdf')

    def test_delete_propaga_el_fallo_de_transporte(self):
        # Un borrado que no ocurre deja datos personales fuera de su plazo de retención:
        # quien llama tiene que enterarse, no recibir un silencio.
        with patch('events.storage._request', side_effect=ApiProblem('sin conexión', 'storage_unavailable', 502)):
            with self.assertRaises(ApiProblem):
                storage.delete('f.pdf', True)

    def test_delete_propaga_el_error_del_servidor(self):
        with patch('events.storage._request', return_value=(500, b'{"error":"interno"}')):
            with self.assertRaises(ApiProblem) as capturado:
                storage.delete('f.pdf', True)
        self.assertEqual(capturado.exception.code, 'storage_error')


class DiskStorageFallbackTests(TestCase):
    # Sin credenciales de Supabase (el estado por defecto en tests, ver USE_SUPABASE_STORAGE en
    # settings), todo debe seguir yendo a disco exactamente como antes.
    def setUp(self):
        import tempfile
        from pathlib import Path
        root = Path(self.enterContext(tempfile.TemporaryDirectory(prefix='storage-test-')))
        self.private_root = root / 'private'
        self.media_root = root / 'media'
        self.enterContext(override_settings(PRIVATE_ROOT=self.private_root, MEDIA_ROOT=self.media_root))

    def test_save_and_open_private_round_trip_on_disk(self):
        name = storage.save(b'contenido-privado', 'application/pdf', '.pdf', True)
        self.assertRegex(name, r'^[a-f0-9]{32}\.pdf$')
        path = self.private_root / name
        self.assertEqual(path.read_bytes(), b'contenido-privado')
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        handle = storage.open_private(name)
        self.assertIsNotNone(handle)
        self.assertEqual(handle.read(), b'contenido-privado')
        handle.close()

    def test_save_public_writes_to_media_root(self):
        name = storage.save(b'jpeg-falso', 'image/jpeg', '.jpg', False)
        self.assertEqual((self.media_root / name).read_bytes(), b'jpeg-falso')

    def test_open_private_returns_none_when_missing(self):
        self.assertIsNone(storage.open_private('no-existe.pdf'))

    def test_public_and_signed_url_are_none_on_disk(self):
        self.assertIsNone(storage.public_url('cualquiera.jpg'))
        self.assertIsNone(storage.signed_url('cualquiera.pdf'))

    def test_delete_of_missing_file_does_not_raise(self):
        storage.delete('no-existe.pdf', True)  # no debe lanzar


class MontajeSupabase:
    # Montaje compartido, sin heredar de TestCase para que el descubridor no lo ejecute solo.
    password = 'Synthetic-test-password-7391!'

    def setUp(self):
        import json, time, uuid
        from datetime import timedelta
        from django.contrib.auth import get_user_model
        from django.test import Client
        from django.utils import timezone
        from events.models import Event, Membership, OrgNode, SiteSettings
        self.json, self.uuid = json, uuid
        self.site = SiteSettings.objects.create(
            pk=1, organization='Organización sintética de pruebas',
            contact_email='privacy@example.test', address='Dirección ficticia para pruebas',
            privacy_policy='Política sintética exclusiva de pruebas sobre finalidad y retención. ' * 6,
            privacy_version='test-v1', retention_days=30, registration_enabled=True,
        )
        self.root, _ = OrgNode.objects.get_or_create(kind='organization', defaults={'name': 'Organización de prueba'})
        pregunta = lambda qid, kind='text', **extra: {
            'id': qid, 'label': f'Pregunta {qid}', 'type': kind, 'required': True,
            'help': '', 'options': [], 'rules': [], 'accept': 'both', **extra}
        self.event = Event.objects.create(
            title='Evento sintético', category='Iglesia', summary='Resumen', description='Descripción',
            date=timezone.now() + timedelta(days=10), location='Lugar ficticio', capacity=10,
            cover='/posters/encuentro.svg', gallery=[], status='published', featured=False,
            questions=[pregunta('acta', 'file', accept='documents'), pregunta('anexo', 'file', accept='documents')],
            owner=self.root)
        self.staff = get_user_model().objects.create_user(
            username='staff-supabase', password=self.password, is_staff=True)
        Membership.objects.create(user=self.staff, node=self.root, role='apostol')
        self.admin = Client()
        self.admin.force_login(self.staff, backend='django.contrib.auth.backends.ModelBackend')
        sesion = self.admin.session
        sesion['authenticated_at'] = time.time()
        sesion.save()

    def pdf(self, nombre='acta.pdf'):
        from django.core.files.uploadedfile import SimpleUploadedFile
        cuerpo = (b'%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\n'
                  b'trailer\n<< /Size 2 /Root 1 0 R >>\nstartxref\n9\n%%EOF\n')
        return SimpleUploadedFile(nombre, cuerpo, content_type='application/pdf')

    def imagen(self):
        from io import BytesIO
        from PIL import Image
        from django.core.files.uploadedfile import SimpleUploadedFile
        salida = BytesIO()
        Image.new('RGB', (24, 18), 'teal').save(salida, format='PNG')
        return SimpleUploadedFile('portada.png', salida.getvalue(), content_type='image/png')

    def inscribir(self, archivos):
        datos = {'name': 'Persona adulta sintética', 'email': 'adult@example.test', 'phone': '',
                 'is_minor': False, 'guardian_name': '', 'guardian_email': '', 'guardian_consent': False,
                 'adult_confirmed': True, 'consent': True, 'sensitive_consent': True,
                 'privacy_version': self.site.privacy_version, 'form_version': self.event.form_version,
                 'request_id': str(self.uuid.uuid4()), 'answers': {}}
        return self.client.post(f'/api/events/{self.event.pk}/registrations',
                                {'data': self.json.dumps(datos), **archivos})


@override_settings(**SUPABASE_SETTINGS)
class VistasSobreSupabaseTests(MontajeSupabase, TestCase):
    # Las vistas con el almacenamiento remoto ACTIVO. El resto de la suite corre siempre con
    # USE_SUPABASE_STORAGE en falso, así que este camino no lo cubre nadie más.

    def test_portada_sube_al_bucket_publico_y_no_toca_el_disco(self):
        with patch('events.storage._request', return_value=(200, b'{"Key":"ok"}')) as llamada:
            respuesta = self.admin.post('/api/admin/images', {'file': self.imagen()})
        self.assertEqual(respuesta.status_code, 201, respuesta.content)
        nombre = respuesta.json()['url'].removeprefix('/media/')
        self.assertRegex(nombre, r'^[a-f0-9]{32}\.jpg$')
        metodo, url = llamada.call_args.args[:2]
        self.assertEqual(metodo, 'POST')
        self.assertEqual(url, f'https://proyecto-sintetico.supabase.co/storage/v1/object/event-images/{nombre}')
        self.assertFalse((__import__('django.conf', fromlist=['settings']).settings.MEDIA_ROOT / nombre).exists())

    def test_imagen_publica_redirige_a_la_url_del_bucket(self):
        nombre = 'a' * 32 + '.jpg'
        respuesta = self.client.get(f'/media/{nombre}')
        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(respuesta['Location'],
                         f'https://proyecto-sintetico.supabase.co/storage/v1/object/public/event-images/{nombre}')

    def test_imagen_publica_sigue_rechazando_un_nombre_con_traversal(self):
        self.assertEqual(self.client.get('/media/..%2Fsecreto.jpg').status_code, 404)

    def test_adjunto_de_inscripcion_sube_al_bucket_privado(self):
        with patch('events.storage._request', return_value=(200, b'{"Key":"ok"}')) as llamada:
            respuesta = self.inscribir({'file_acta': self.pdf(), 'file_anexo': self.pdf('anexo.pdf')})
        self.assertEqual(respuesta.status_code, 201, respuesta.content)
        from events.models import Attachment
        nombres = sorted(Attachment.objects.values_list('storage_name', flat=True))
        self.assertEqual(len(nombres), 2)
        subidas = [c.args[1] for c in llamada.call_args_list if c.args[0] == 'POST']
        for nombre in nombres:
            self.assertIn(f'https://proyecto-sintetico.supabase.co/storage/v1/object/registration-files/{nombre}',
                          subidas)

    def test_descarga_privada_redirige_a_una_url_firmada(self):
        with patch('events.storage._request', return_value=(200, b'{"Key":"ok"}')):
            self.inscribir({'file_acta': self.pdf(), 'file_anexo': self.pdf('anexo.pdf')})
        from events.models import Attachment
        adjunto = Attachment.objects.first()
        firma = (200, b'{"signedURL":"/object/sign/registration-files/x.pdf?token=abc"}')
        with patch('events.storage._request', return_value=firma):
            respuesta = self.admin.get(f'/api/admin/files/{adjunto.pk}')
        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(respuesta['Location'],
                         'https://proyecto-sintetico.supabase.co/storage/v1/object/sign/registration-files/x.pdf?token=abc')

    def test_descarga_privada_sigue_exigiendo_sesion_de_staff(self):
        with patch('events.storage._request', return_value=(200, b'{"Key":"ok"}')):
            self.inscribir({'file_acta': self.pdf(), 'file_anexo': self.pdf('anexo.pdf')})
        from events.models import Attachment
        respuesta = self.client.get(f'/api/admin/files/{Attachment.objects.first().pk}')
        self.assertEqual(respuesta.status_code, 401)

    def test_si_falla_la_segunda_subida_se_borra_la_primera(self):
        respuestas = [(200, b'{"Key":"ok"}'), (500, b'{"error":"interno"}'), (200, b'')]
        with patch('events.storage._request', side_effect=respuestas) as llamada:
            respuesta = self.inscribir({'file_acta': self.pdf(), 'file_anexo': self.pdf('anexo.pdf')})
        self.assertEqual(respuesta.status_code, 502, respuesta.content)
        from events.models import Attachment, Registration
        self.assertFalse(Registration.objects.exists())
        self.assertFalse(Attachment.objects.exists())
        borrados = [c.args[1] for c in llamada.call_args_list if c.args[0] == 'DELETE']
        self.assertEqual(len(borrados), 1, 'la primera subida tiene que compensarse con un borrado')

    def test_la_purga_no_borra_la_fila_si_no_pudo_borrar_el_archivo(self):
        from django.core.management import call_command
        from django.core.management.base import CommandError
        from django.utils import timezone
        from events.models import Registration
        with patch('events.storage._request', return_value=(200, b'{"Key":"ok"}')):
            self.inscribir({'file_acta': self.pdf(), 'file_anexo': self.pdf('anexo.pdf')})
        Registration.objects.update(expires_at=timezone.now() - __import__('datetime').timedelta(days=1))
        with patch('events.storage._request', return_value=(500, b'{"error":"interno"}')):
            with self.assertRaises(CommandError):
                call_command('purge_expired', '--execute')
        self.assertTrue(Registration.objects.exists(),
                        'borrar la fila dejaría el adjunto huérfano fuera de retención')


@override_settings(**SUPABASE_SETTINGS)
class AusenciaSegunSupabaseTests(TestCase):
    # Supabase no responde 404 cuando un objeto no está: manda 400 con el 404 dentro del cuerpo.
    # Con HEAD ni siquiera manda cuerpo. Comprobado contra el servicio real el 2026-09-10.
    NO_ESTA = b'{"statusCode":"404","error":"not_found","message":"Object not found","code":"NoSuchKey"}'

    def test_exists_es_falso_cuando_supabase_responde_400_not_found(self):
        with patch('events.storage._request', return_value=(400, self.NO_ESTA)):
            self.assertFalse(storage.exists('a' * 32 + '.jpg', False))

    def test_exists_es_falso_con_head_400_sin_cuerpo(self):
        with patch('events.storage._request', return_value=(400, b'')):
            self.assertFalse(storage.exists('a' * 32 + '.jpg', False))

    def test_exists_usa_head_para_no_descargar_el_archivo(self):
        with patch('events.storage._request', return_value=(200, b'')) as llamada:
            self.assertTrue(storage.exists('b' * 32 + '.jpg', False))
        metodo, url = llamada.call_args.args[:2]
        self.assertEqual(metodo, 'HEAD')
        self.assertEqual(url, 'https://proyecto-sintetico.supabase.co/storage/v1/object/event-images/' + 'b' * 32 + '.jpg')

    def test_exists_propaga_un_error_real_del_servidor(self):
        with patch('events.storage._request', return_value=(500, b'{"error":"interno"}')):
            with self.assertRaises(ApiProblem):
                storage.exists('c' * 32 + '.jpg', False)

    def test_delete_repetido_no_falla_aunque_supabase_responda_400(self):
        # Si esto lanzara, purge_expired se atascaría: nunca borraría la fila de un registro
        # cuyo archivo ya no está, y la retención quedaría bloqueada para siempre.
        with patch('events.storage._request', return_value=(400, self.NO_ESTA)):
            storage.delete('d' * 32 + '.pdf', True)

    def test_portada_subida_se_acepta_al_guardar_el_evento(self):
        # El bug: image_url miraba MEDIA_ROOT, así que con Supabase activo era imposible
        # guardar un evento con una portada recién subida.
        from events.validation import image_url
        nombre = 'e' * 32 + '.jpg'
        with patch('events.storage._request', return_value=(200, b'')):
            self.assertEqual(image_url(f'/media/{nombre}'), f'/media/{nombre}')
        with patch('events.storage._request', return_value=(400, self.NO_ESTA)):
            with self.assertRaises(ApiProblem):
                image_url(f'/media/{nombre}')


TOKEN = 'token-sintetico-de-pruebas-con-longitud-suficiente'


@override_settings(**SUPABASE_SETTINGS)
class PurgaProgramadaTests(MontajeSupabase, TestCase):
    # Reutiliza el montaje de VistasSobreSupabaseTests (evento con preguntas de archivo,
    # SiteSettings listo y staff), y ejercita el disparador HTTP de la retención.
    URL = '/tareas/purga'

    def inscribir_vencida(self):
        from datetime import timedelta
        from django.utils import timezone
        from events.models import Registration
        with patch('events.storage._request', return_value=(200, b'{"Key":"ok"}')):
            self.inscribir({'file_acta': self.pdf(), 'file_anexo': self.pdf('anexo.pdf')})
        Registration.objects.update(expires_at=timezone.now() - timedelta(days=1))
        return Registration.objects.get()

    @override_settings(TAREAS_TOKEN='')
    def test_sin_token_configurado_el_endpoint_no_existe(self):
        self.assertEqual(self.client.post(self.URL).status_code, 404)

    @override_settings(TAREAS_TOKEN='corto')
    def test_un_token_corto_no_protege_y_se_rechaza(self):
        respuesta = self.client.post(self.URL, HTTP_AUTHORIZATION='Bearer corto')
        self.assertEqual(respuesta.status_code, 503)
        self.assertEqual(respuesta.json()['error']['code'], 'misconfigured')

    @override_settings(TAREAS_TOKEN=TOKEN)
    def test_sin_cabecera_no_autoriza(self):
        self.assertEqual(self.client.post(self.URL).status_code, 401)

    @override_settings(TAREAS_TOKEN=TOKEN)
    def test_token_incorrecto_no_autoriza_ni_borra(self):
        self.inscribir_vencida()
        from events.models import Registration
        respuesta = self.client.post(self.URL, HTTP_AUTHORIZATION='Bearer ' + TOKEN[:-1] + 'x')
        self.assertEqual(respuesta.status_code, 401)
        self.assertTrue(Registration.objects.exists())

    @override_settings(TAREAS_TOKEN=TOKEN)
    def test_get_no_sirve_para_disparar_la_purga(self):
        self.assertEqual(self.client.get(self.URL, HTTP_AUTHORIZATION='Bearer ' + TOKEN).status_code, 405)

    @override_settings(TAREAS_TOKEN=TOKEN)
    def test_con_token_purga_de_verdad(self):
        self.inscribir_vencida()
        from events.models import Attachment, Registration
        with patch('events.storage._request', return_value=(200, b'')) as llamada:
            respuesta = self.client.post(self.URL, HTTP_AUTHORIZATION='Bearer ' + TOKEN)
        self.assertEqual(respuesta.status_code, 200, respuesta.content)
        self.assertEqual(respuesta.json(), {'purgados': 1, 'fallidos': []})
        self.assertFalse(Registration.objects.exists())
        self.assertFalse(Attachment.objects.exists())
        self.assertTrue(any(c.args[0] == 'DELETE' for c in llamada.call_args_list),
                        'tiene que borrar el adjunto del bucket, no solo la fila')

    @override_settings(TAREAS_TOKEN=TOKEN)
    def test_si_falla_el_borrado_responde_500_y_conserva_la_fila(self):
        registro = self.inscribir_vencida()
        from events.models import Registration
        with patch('events.storage._request', return_value=(500, b'{"error":"interno"}')):
            respuesta = self.client.post(self.URL, HTTP_AUTHORIZATION='Bearer ' + TOKEN)
        self.assertEqual(respuesta.status_code, 500)
        self.assertEqual(respuesta.json()['fallidos'], [registro.reference])
        self.assertTrue(Registration.objects.exists(),
                        'la fila se queda para que el siguiente intento lo reintente')

    @override_settings(TAREAS_TOKEN=TOKEN)
    def test_no_necesita_csrf_porque_se_autentica_con_token(self):
        from django.test import Client
        estricto = Client(enforce_csrf_checks=True)
        self.assertEqual(estricto.post(self.URL, HTTP_AUTHORIZATION='Bearer ' + TOKEN).status_code, 200)
