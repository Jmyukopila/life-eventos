import json
import tempfile
import time
import uuid
from datetime import timedelta
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.utils import timezone

from events.models import Attachment, Event, EventGuest, Membership, OrgNode, Registration, SiteSettings

PASSWORD = 'Synthetic-test-password-7391!'

FILE_QUESTION = [{'id': 'doc', 'label': 'Documento', 'type': 'file', 'required': False,
                  'help': '', 'options': [], 'rules': [], 'accept': 'documents'}]


def pdf_bytes():
    parts = [b'%PDF-1.4\n']
    offsets = []
    objects = [b'<< /Type /Catalog /Pages 2 0 R >>',
               b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
               b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 100 100] >>']
    for number, obj in enumerate(objects, 1):
        offsets.append(sum(map(len, parts)))
        parts.append(f'{number} 0 obj\n'.encode() + obj + b'\nendobj\n')
    xref = sum(map(len, parts))
    parts.append(b'xref\n0 4\n0000000000 65535 f \n')
    parts.extend(f'{offset:010d} 00000 n \n'.encode() for offset in offsets)
    parts.append(f'trailer\n<< /Size 4 /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n'.encode())
    return b''.join(parts)


class ScopeApiTests(TestCase):
    # Dos congregaciones bajo la raíz, cada una con red -> subred -> grupo, y un usuario por
    # rol en la congregación A. Sirve de fixture a toda la matriz de permisos de la fase 2.
    def setUp(self):
        root_dir = Path(self.enterContext(tempfile.TemporaryDirectory(prefix='events-scope-test-')))
        self.enterContext(override_settings(PRIVATE_ROOT=root_dir / 'private', MEDIA_ROOT=root_dir / 'media'))
        cache.clear()
        self.addCleanup(cache.clear)

        self.root = OrgNode.objects.get(kind='organization')
        self.cong_a = OrgNode.objects.create(kind='congregation', name='Congregación A', parent=self.root)
        self.net_a = OrgNode.objects.create(kind='network', name='Red A', parent=self.cong_a)
        self.sub_a = OrgNode.objects.create(kind='subnetwork', name='Subred A', parent=self.net_a)
        self.group_a = OrgNode.objects.create(kind='group', name='Grupo A', parent=self.sub_a)
        self.cong_b = OrgNode.objects.create(kind='congregation', name='Congregación B', parent=self.root)
        self.net_b = OrgNode.objects.create(kind='network', name='Red B', parent=self.cong_b)
        self.sub_b = OrgNode.objects.create(kind='subnetwork', name='Subred B', parent=self.net_b)
        self.group_b = OrgNode.objects.create(kind='group', name='Grupo B', parent=self.sub_b)

        self.users = {}
        for role, node, username in [
            ('apostol', self.root, 'apostol-a'),
            ('pastor', self.cong_a, 'pastor-a'),
            ('lider_red', self.net_a, 'lider-red-a'),
            ('lider', self.group_a, 'lider-a'),
            ('estaca', self.group_a, 'estaca-a'),
        ]:
            user = get_user_model().objects.create_user(username=username, password=PASSWORD, is_staff=True)
            Membership.objects.create(user=user, node=node, role=role)
            self.users[role] = user

        self.staff_sin_membresia = get_user_model().objects.create_user(
            username='staff-sin-membresia', password=PASSWORD, is_staff=True)

        self.site = SiteSettings.objects.create(
            pk=1, organization='Organización sintética', contact_email='privacy@example.test',
            address='Dirección ficticia', privacy_policy=((
                'Política sintética de pruebas sobre finalidad, retención y derechos de acceso, '
                'corrección y eliminación de los datos personales tratados. ') * 3).strip(),
            privacy_version='test-v1', retention_days=30, registration_enabled=True,
        )

        self.event_root = self.make_event(self.root, 'Evento raíz', questions=FILE_QUESTION)
        self.event_cong_a = self.make_event(self.cong_a, 'Evento Congregación A', questions=FILE_QUESTION)
        self.event_net_a = self.make_event(self.net_a, 'Evento Red A', questions=FILE_QUESTION)
        self.event_sub_a = self.make_event(self.sub_a, 'Evento Subred A')
        self.event_group_a = self.make_event(self.group_a, 'Evento Grupo A', questions=FILE_QUESTION)
        self.event_group_a_draft = self.make_event(self.group_a, 'Evento borrador Grupo A', status='draft')
        self.event_cong_b = self.make_event(self.cong_b, 'Evento Congregación B', questions=FILE_QUESTION)
        self.event_net_b = self.make_event(self.net_b, 'Evento Red B')
        self.event_sub_b = self.make_event(self.sub_b, 'Evento Subred B')
        self.event_group_b = self.make_event(self.group_b, 'Evento Grupo B')
        self.event_joint = self.make_event(self.net_b, 'Evento conjunto B con A invitada')
        EventGuest.objects.create(event=self.event_joint, node=self.cong_a)

        self.registration_root = self.submit_registration(self.event_root, 'root@a.test', 'Persona Root')
        self.registration_cong_a = self.submit_registration(self.event_cong_a, 'alice@a.test', 'Alice A')
        self.registration_net_a = self.submit_registration(self.event_net_a, 'networka@a.test', 'Network A')
        self.registration_group_a = self.submit_registration(self.event_group_a, 'groupa@a.test', 'Group A')
        self.registration_cong_b = self.submit_registration(self.event_cong_b, 'bob@b.test', 'Bob B')

        self.own_event = {
            'apostol': self.event_root, 'pastor': self.event_cong_a,
            'lider_red': self.event_net_a, 'lider': self.event_group_a, 'estaca': self.event_group_a,
        }
        self.own_attachment = {
            'apostol': self.registration_root.attachments.get(),
            'pastor': self.registration_cong_a.attachments.get(),
            'lider_red': self.registration_net_a.attachments.get(),
            'lider': self.registration_group_a.attachments.get(),
            'estaca': self.registration_group_a.attachments.get(),
        }

    # ---- helpers de montaje ----

    def make_event(self, owner, title, status='published', questions=None):
        return Event.objects.create(
            title=title, category='Iglesia', summary='Resumen', description='Descripción',
            date=timezone.now() + timedelta(days=15), location='Lugar ficticio', capacity=10,
            cover='/posters/encuentro.svg', gallery=[], status=status, featured=False,
            questions=questions if questions is not None else [], owner=owner,
        )

    def submit_registration(self, event, email_addr, name):
        payload = {
            'name': name, 'email': email_addr, 'phone': '', 'is_minor': False,
            'guardian_name': '', 'guardian_email': '', 'guardian_consent': False,
            'adult_confirmed': True, 'consent': True, 'sensitive_consent': True,
            'privacy_version': self.site.privacy_version, 'form_version': event.form_version,
            'request_id': str(uuid.uuid4()), 'answers': {},
        }
        upload = SimpleUploadedFile('documento.pdf', pdf_bytes(), content_type='application/pdf')
        response = self.client.post(f'/api/events/{event.pk}/registrations',
                                     {'data': json.dumps(payload), 'file_doc': upload})
        assert response.status_code == 201, response.content
        return Registration.objects.get(event=event, email=email_addr)

    def login(self, role):
        client = Client()
        client.force_login(self.users[role], backend='django.contrib.auth.backends.ModelBackend')
        session = client.session
        session['authenticated_at'] = time.time()
        session.save()
        return client

    def event_payload(self, event, **changes):
        return {
            'title': event.title, 'category': event.category, 'summary': event.summary,
            'description': event.description, 'location': event.location, 'date': event.date,
            'end_date': event.end_date, 'capacity': event.capacity, 'cover': event.cover,
            'gallery': event.gallery, 'status': event.status, 'featured': event.featured,
            'questions': event.questions, **changes,
        }

    def new_event_payload(self):
        return {
            'title': 'Evento nuevo de matriz', 'category': 'Iglesia', 'summary': 'Resumen',
            'description': 'Descripción', 'location': 'Lugar', 'date': timezone.now() + timedelta(days=20),
            'end_date': None, 'capacity': 5, 'cover': '/posters/encuentro.svg', 'gallery': [],
            'status': 'draft', 'featured': False, 'questions': [],
        }

    def settings_payload(self):
        return {
            'organization': self.site.organization, 'contact_email': self.site.contact_email,
            'contact_phone': self.site.contact_phone, 'address': self.site.address,
            'privacy_policy': self.site.privacy_policy, 'privacy_version': self.site.privacy_version,
            'retention_days': self.site.retention_days, 'registration_enabled': self.site.registration_enabled,
        }

    def png_upload(self):
        from io import BytesIO
        from PIL import Image
        output = BytesIO()
        Image.new('RGB', (10, 10), 'red').save(output, format='PNG')
        return SimpleUploadedFile('imagen.png', output.getvalue(), content_type='image/png')

    def assert_error(self, response, status, code):
        self.assertEqual(response.status_code, status, response.content)
        self.assertEqual(response.json()['error']['code'], code)

    # ---- 1. matriz dirigida por datos ----

    def test_matriz_de_permisos_por_rol(self):
        matriz = {
            'apostol':   {'settings_put': 200, 'events_post': 201, 'export_get': 200},
            'pastor':    {'settings_put': 403, 'events_post': 201, 'export_get': 200},
            'lider_red': {'settings_put': 403, 'events_post': 201, 'export_get': 200},
            'lider':     {'settings_put': 403, 'events_post': 201, 'export_get': 200},
            'estaca':    {'settings_put': 403, 'events_post': 403, 'export_get': 403},
        }
        for role, casos in matriz.items():
            client = self.login(role)
            own_event = self.own_event[role]
            own_attachment = self.own_attachment[role]
            with self.subTest(role=role, accion='admin_settings PUT'):
                response = client.put('/api/admin/settings', self.settings_payload(), content_type='application/json')
                self.assertEqual(response.status_code, casos['settings_put'], response.content)
            with self.subTest(role=role, accion='admin_events GET'):
                self.assertEqual(client.get('/api/admin/events').status_code, 200)
            with self.subTest(role=role, accion='admin_events POST'):
                response = client.post('/api/admin/events', self.new_event_payload(), content_type='application/json')
                self.assertEqual(response.status_code, casos['events_post'], response.content)
            with self.subTest(role=role, accion='admin_event PUT'):
                response = client.put(f'/api/admin/events/{own_event.id}', self.event_payload(own_event), content_type='application/json')
                self.assertEqual(response.status_code, 200, response.content)
            with self.subTest(role=role, accion='admin_images POST'):
                response = client.post('/api/admin/images', {'file': self.png_upload()})
                self.assertEqual(response.status_code, 201, response.content)
            with self.subTest(role=role, accion='admin_registrations GET'):
                self.assertEqual(client.get('/api/admin/registrations').status_code, 200)
            with self.subTest(role=role, accion='private_file GET'):
                self.assertEqual(client.get(f'/api/admin/files/{own_attachment.id}').status_code, 200)
            with self.subTest(role=role, accion='export_registrations GET'):
                response = client.get('/api/admin/registrations/export')
                self.assertEqual(response.status_code, casos['export_get'], response.content)

    # ---- 2. acceso lateral por id directo (Pastor de A contra recursos de B) ----

    def test_acceso_lateral_a_recursos_de_otro_ambito_da_404(self):
        pastor = self.login('pastor')
        self.assert_error(
            pastor.put(f'/api/admin/events/{self.event_cong_b.id}', self.event_payload(self.event_cong_b), content_type='application/json'),
            404, 'not_found')
        self.assert_error(pastor.get(f'/api/admin/files/{self.registration_cong_b.attachments.get().id}'), 404, 'not_found')
        self.assert_error(pastor.get(f'/api/admin/registrations?event_id={self.event_cong_b.id}'), 404, 'not_found')
        self.assert_error(pastor.get(f'/api/admin/registrations/export?event_id={self.event_cong_b.id}'), 404, 'not_found')

    # ---- 3. publicar sin permiso: solo la transición cuenta ----

    def test_publicar_o_destacar_requiere_permiso_solo_en_la_transicion(self):
        estaca = self.login('estaca')
        response = estaca.put(f'/api/admin/events/{self.event_group_a_draft.id}',
                               self.event_payload(self.event_group_a_draft, status='published'), content_type='application/json')
        self.assert_error(response, 403, 'forbidden')
        self.event_group_a_draft.refresh_from_db()
        self.assertEqual(self.event_group_a_draft.status, 'draft')

        response = estaca.put(f'/api/admin/events/{self.event_group_a_draft.id}',
                               self.event_payload(self.event_group_a_draft, status='draft'), content_type='application/json')
        self.assertEqual(response.status_code, 200, response.content)

        # El evento ya estaba publicado: mantenerlo publicado no es una transición.
        response = estaca.put(f'/api/admin/events/{self.event_group_a.id}',
                               self.event_payload(self.event_group_a, status='published'), content_type='application/json')
        self.assertEqual(response.status_code, 200, response.content)

    # ---- 4. sin fuga por listado ----

    def test_sin_fuga_por_listado_de_eventos_e_inscripciones(self):
        pastor = self.login('pastor')
        ids = {row['id'] for row in pastor.get('/api/admin/events').json()['events']}
        esperados = {str(self.event_cong_a.id), str(self.event_net_a.id), str(self.event_sub_a.id),
                     str(self.event_group_a.id), str(self.event_group_a_draft.id), str(self.event_joint.id)}
        self.assertCountEqual(ids, esperados)

        registros = pastor.get('/api/admin/registrations').json()['registrations']
        ids_registros = {row['id'] for row in registros}
        esperados_registros = {str(self.registration_cong_a.id), str(self.registration_net_a.id),
                                str(self.registration_group_a.id)}
        self.assertCountEqual(ids_registros, esperados_registros)

        csv_response = pastor.get('/api/admin/registrations/export')
        self.assertEqual(csv_response.status_code, 200)
        contenido = csv_response.content.decode('utf-8-sig')
        self.assertNotIn('b.test', contenido)
        self.assertIn('alice@a.test', contenido)

    # ---- 5. herencia del subárbol ----

    def test_herencia_del_subarbol_es_descendente(self):
        lider_red = self.login('lider_red')
        ids = {row['id'] for row in lider_red.get('/api/admin/events').json()['events']}
        self.assertIn(str(self.event_group_a.id), ids)

        lider = self.login('lider')
        ids = {row['id'] for row in lider.get('/api/admin/events').json()['events']}
        self.assertNotIn(str(self.event_cong_a.id), ids)
        self.assert_error(
            lider.put(f'/api/admin/events/{self.event_cong_a.id}', self.event_payload(self.event_cong_a), content_type='application/json'),
            404, 'not_found')

    # ---- 6. evento conjunto: el invitado es solo lectura ----

    def test_evento_conjunto_visible_para_el_invitado_pero_de_solo_lectura(self):
        pastor = self.login('pastor')
        ids = {row['id'] for row in pastor.get('/api/admin/events').json()['events']}
        self.assertIn(str(self.event_joint.id), ids)
        response = pastor.put(f'/api/admin/events/{self.event_joint.id}',
                              self.event_payload(self.event_joint), content_type='application/json')
        self.assert_error(response, 404, 'not_found')

    # ---- 7. staff sin membresía ----

    def test_staff_sin_membresia_no_tiene_permiso_alguno(self):
        client = Client()
        client.force_login(self.staff_sin_membresia, backend='django.contrib.auth.backends.ModelBackend')
        session = client.session
        session['authenticated_at'] = time.time()
        session.save()
        self.assert_error(client.get('/api/admin/events'), 403, 'forbidden')

    # ---- 8. sesión pública intacta ----

    def test_sitio_publico_no_cambia(self):
        response = self.client.get('/api/events')
        self.assertEqual(response.status_code, 200)
        ids = {row['id'] for row in response.json()['events']}
        self.assertIn(str(self.event_cong_a.id), ids)
        self.assertIn(str(self.event_cong_b.id), ids)
