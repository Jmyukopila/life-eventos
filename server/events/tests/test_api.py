import copy
import csv
import json
import tempfile
import time
import uuid
from datetime import timedelta
from io import BytesIO, StringIO
from pathlib import Path

from PIL import Image, PngImagePlugin
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import Client, TestCase, override_settings
from django.utils import timezone

from events.models import Attachment, Event, Membership, OrgNode, Registration, SiteSettings


class EventApiTests(TestCase):
    password = 'Synthetic-test-password-7391!'

    @classmethod
    def setUpTestData(cls):
        cls.staff = get_user_model().objects.create_user(
            username='test-staff', password=cls.password, is_staff=True,
        )
        cls.root, _ = OrgNode.objects.get_or_create(kind='organization', defaults={'name': 'Organización de prueba'})
        Membership.objects.create(user=cls.staff, node=cls.root, role='apostol')

    def setUp(self):
        root = Path(self.enterContext(tempfile.TemporaryDirectory(prefix='events-api-test-')))
        self.private_root = root / 'private'
        self.media_root = root / 'media'
        self.enterContext(override_settings(PRIVATE_ROOT=self.private_root, MEDIA_ROOT=self.media_root))
        cache.clear()
        self.addCleanup(cache.clear)
        self.admin = Client()
        self.authenticate_staff(self.admin)
        self.site = SiteSettings.objects.create(
            pk=1, organization='Organización sintética de pruebas',
            contact_email='privacy@example.test', address='Dirección ficticia para pruebas',
            privacy_policy=('Política sintética exclusiva de pruebas. Autorización informada, finalidad, '
                            'retención y derechos de acceso, corrección y eliminación de los datos. ') * 3,
            privacy_version='test-v1', retention_days=30, registration_enabled=True,
        )
        self.questions = [
            self.question('lider', 'radio', options=['Sí', 'No'],
                          rules=[{'value': 'No', 'target': 'availability'}]),
            self.question('team'),
            self.question('document', 'file', accept='documents'),
            self.question('availability'),
        ]
        self.event = Event.objects.create(**self.event_input(), owner=self.root)
        self.url = f'/api/events/{self.event.pk}/registrations'

    def authenticate_staff(self, client):
        client.force_login(self.staff, backend='django.contrib.auth.backends.ModelBackend')
        session = client.session
        session['authenticated_at'] = time.time()
        session.save()

    def question(self, qid, kind='text', **changes):
        return {'id': qid, 'label': f'Pregunta {qid}', 'type': kind, 'required': True,
                'help': '', 'options': [], 'rules': [], 'accept': 'both', **changes}

    def event_input(self, **changes):
        return {'title': 'Evento sintético', 'category': 'Iglesia', 'summary': 'Resumen de prueba',
                'description': 'Descripción de prueba', 'location': 'Lugar ficticio',
                'date': timezone.now() + timedelta(days=10), 'end_date': None,
                'capacity': 10, 'cover': '/posters/encuentro.svg', 'gallery': [],
                'status': 'published', 'featured': False, 'questions': copy.deepcopy(self.questions),
                **changes}

    def payload(self, **changes):
        return {'name': 'Persona adulta sintética', 'email': 'adult@example.test', 'phone': '',
                'is_minor': False, 'guardian_name': '', 'guardian_email': '',
                'guardian_consent': False, 'adult_confirmed': True, 'consent': True,
                'sensitive_consent': True, 'privacy_version': self.site.privacy_version,
                'form_version': self.event.form_version, 'request_id': str(uuid.uuid4()),
                'answers': {'lider': 'No', 'availability': 'Mañana'}, **changes}

    def register(self, payload=None, files=None, client=None):
        return (client or self.client).post(
            self.url, {'data': json.dumps(payload if payload is not None else self.payload()), **(files or {})},
        )

    def assert_error(self, response, status=400, code='invalid'):
        self.assertEqual(response.status_code, status, response.content)
        self.assertEqual(response.json()['error']['code'], code)

    def assert_no_registration(self):
        self.event.refresh_from_db()
        self.assertEqual(self.event.registered, 0)
        self.assertFalse(Registration.objects.exists())
        self.assertFalse(Attachment.objects.exists())
        self.assertFalse(self.private_root.exists() and any(self.private_root.iterdir()))

    def use_upload_question(self, accept='both'):
        self.event.questions = [self.question('document', 'file', accept=accept)]
        self.event.save(update_fields=['questions'])
        return self.payload(answers={})

    def pdf(self):
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
        return SimpleUploadedFile('test-document.pdf', b''.join(parts), content_type='application/pdf')

    def image_bytes(self):
        output = BytesIO()
        metadata = PngImagePlugin.PngInfo()
        metadata.add_text('Author', 'synthetic-private-metadata')
        image = Image.new('RGB', (32, 24), 'blue')
        exif = Image.Exif()
        exif[315] = 'synthetic-private-metadata'
        image.save(output, format='PNG', pnginfo=metadata, exif=exif)
        return output.getvalue()

    def test_public_list_and_detail_hide_drafts(self):
        draft = Event.objects.create(**self.event_input(status='draft'), owner=self.root)
        response = self.client.get('/api/events')
        self.assertEqual(response.status_code, 200)
        self.assertEqual([row['id'] for row in response.json()['events']], [str(self.event.pk)])
        self.assert_error(self.client.get(f'/api/events/{draft.pk}'), 404, 'not_found')
        self.assertEqual(self.client.get(f'/api/events/{self.event.pk}').status_code, 200)
        self.assertEqual(len(self.admin.get('/api/admin/events').json()['events']), 2)
        self.assert_error(self.client.post(f'/api/events/{draft.pk}/registrations',
                                           {'data': json.dumps(self.payload())}), 404, 'not_found')
        self.assert_no_registration()

    def test_admin_routes_require_authentication(self):
        routes = [('get', '/api/admin/events'), ('post', '/api/admin/events'),
                  ('put', f'/api/admin/events/{self.event.pk}'), ('put', '/api/admin/settings'),
                  ('post', '/api/admin/images'), ('get', '/api/admin/registrations'),
                  ('get', '/api/admin/registrations/export'),
                  ('get', f'/api/admin/files/{uuid.uuid4()}')]
        for method, url in routes:
            with self.subTest(method=method, url=url):
                self.assert_error(getattr(self.client, method)(url), 401, 'unauthorized')

    def test_nonstaff_and_expired_staff_session_rejected(self):
        user = get_user_model().objects.create_user(username='test-nonstaff')
        self.client.force_login(user, backend='django.contrib.auth.backends.ModelBackend')
        session = self.client.session
        session['authenticated_at'] = time.time()
        session.save()
        self.assert_error(self.client.get('/api/admin/events'), 401, 'unauthorized')
        session = self.admin.session
        session['authenticated_at'] = time.time() - 43201
        session.save()
        self.assert_error(self.admin.get('/api/admin/events'), 401, 'session_expired')

    def test_csrf_rejects_unprotected_mutations(self):
        client = Client(enforce_csrf_checks=True)
        self.authenticate_staff(client)
        for url, data in [('/api/login', {}), ('/api/logout', {}),
                          ('/api/admin/events', {}), (self.url, {'data': json.dumps(self.payload())})]:
            with self.subTest(url=url):
                self.assert_error(client.post(url, data), 403, 'csrf')
        self.assert_no_registration()

    def csrf_login(self):
        client = Client(enforce_csrf_checks=True)
        initial = client.get('/api/session').json()
        self.assertFalse(initial['authenticated'])
        cookie = client.cookies['csrftoken'].value
        response = client.post('/api/login', {'username': self.staff.username, 'password': self.password},
                               content_type='application/json', HTTP_X_CSRFTOKEN=initial['csrfToken'])
        self.assertEqual(response.status_code, 200, response.content)
        self.assertTrue(response.json()['authenticated'])
        self.assertEqual(response.json()['username'], self.staff.username)
        self.assertNotEqual(client.cookies['csrftoken'].value, cookie)
        self.assertGreater(client.session['authenticated_at'], time.time() - 60)
        return client, initial['csrfToken'], response.json()['csrfToken']

    def test_staff_login_rotates_csrf_and_logout_ends_session(self):
        client, old_token, token = self.csrf_login()
        self.assertEqual(client.get('/api/admin/events').status_code, 200)
        self.assert_error(client.post('/api/logout', HTTP_X_CSRFTOKEN=old_token), 403, 'csrf')
        response = client.post('/api/logout', HTTP_X_CSRFTOKEN=token)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'ok': True})
        self.assertFalse(client.get('/api/session').json()['authenticated'])
        self.assert_error(client.get('/api/admin/events'), 401, 'unauthorized')
        self.assertNotIn('authenticated_at', client.session)

    def test_logout_invalidates_prelogout_csrf_token(self):
        client, _, token = self.csrf_login()
        self.assertEqual(client.post('/api/logout', HTTP_X_CSRFTOKEN=token).status_code, 200)
        client.get('/api/session')
        response = client.post('/api/login', {'username': self.staff.username, 'password': self.password},
                               content_type='application/json', HTTP_X_CSRFTOKEN=token)
        self.assert_error(response, 403, 'csrf')

    def test_axes_locks_after_five_failed_logins(self):
        cache.clear()
        for attempt in range(5):
            response = self.client.post('/api/login',
                                        {'username': self.staff.username, 'password': 'incorrect-test-password'},
                                        content_type='application/json')
            self.assert_error(response, 429 if attempt == 4 else 401,
                              'locked_out' if attempt == 4 else 'invalid_credentials')
        response = self.client.post('/api/login', {'username': self.staff.username, 'password': self.password},
                                    content_type='application/json')
        self.assert_error(response, 429, 'locked_out')
        self.assertFalse(self.client.get('/api/session').json()['authenticated'])

    def test_readiness_and_disabled_policy_block_registration(self):
        for field, value in [('registration_enabled', False), ('privacy_policy', 'Insuficiente'),
                             ('contact_email', ''), ('address', '')]:
            with self.subTest(field=field):
                previous = getattr(self.site, field)
                setattr(self.site, field, value)
                self.site.save()
                self.assertFalse(self.client.get('/api/settings').json()['ready'])
                self.assert_error(self.register(), 503, 'registration_disabled')
                self.assert_no_registration()
                setattr(self.site, field, previous)
                self.site.save()

    def test_successful_registration_persists_snapshots_and_counts(self):
        payload = self.payload()
        response = self.register(payload)
        self.assertEqual(response.status_code, 201, response.content)
        self.assertFalse(response.json()['duplicate'])
        record = Registration.objects.get()
        self.event.refresh_from_db()
        self.assertEqual(self.event.registered, 1)
        self.assertEqual(record.reference, response.json()['reference'])
        self.assertEqual(str(record.request_id), payload['request_id'])
        self.assertEqual(record.answers, payload['answers'])
        self.assertEqual(record.form_snapshot, self.questions)
        self.assertEqual(record.privacy_version, 'test-v1')
        self.assertEqual(record.privacy_snapshot, self.site.privacy_policy)
        self.assertEqual(record.question_labels, {'lider': 'Pregunta lider', 'availability': 'Pregunta availability'})
        self.assertEqual(record.expires_at, self.event.date + timedelta(days=30))
        for key in ['consent', 'sensitive_consent', 'adult_confirmed']:
            self.assertIs(record.consent_evidence[key], True)
        self.assertIs(record.consent_evidence['guardian_consent'], False)
        self.event.questions = []
        self.event.form_version += 1
        self.event.save()
        self.site.privacy_policy = 'Política posterior ' * 20
        self.site.privacy_version = 'test-v2'
        self.site.save()
        record.refresh_from_db()
        self.assertEqual(record.form_snapshot, self.questions)
        self.assertEqual(record.privacy_version, 'test-v1')
        self.assertNotEqual(record.privacy_snapshot, self.site.privacy_policy)

    def test_no_lider_skips_required_questions_and_file(self):
        response = self.register()
        self.assertEqual(response.status_code, 201, response.content)
        record = Registration.objects.get()
        self.assertNotIn('team', record.question_labels)
        self.assertNotIn('document', record.question_labels)
        self.assertFalse(record.attachments.exists())

    def test_hidden_answer_is_rejected(self):
        self.assert_error(self.register(self.payload(answers={'lider': 'No', 'team': 'Oculto',
                                                              'availability': 'Mañana'})))
        self.assert_no_registration()

    def test_hidden_file_is_rejected(self):
        self.assert_error(self.register(files={'file_document': self.pdf()}))
        self.assert_no_registration()

    def test_required_visible_answers_and_files_are_rejected_when_missing(self):
        for answers, missing in [({'lider': 'No'}, 'availability'),
                                 ({'lider': 'Sí', 'availability': 'Mañana'}, 'team'),
                                 ({'lider': 'Sí', 'team': 'Equipo', 'availability': 'Mañana'}, 'document')]:
            with self.subTest(missing=missing):
                response = self.register(self.payload(answers=answers))
                self.assert_error(response)
                self.assertIn(missing, response.json()['error']['fields'])
                self.assert_no_registration()

    def test_event_put_rejects_backward_rule_without_mutation(self):
        questions = copy.deepcopy(self.questions)
        questions[0]['rules'] = [{'value': 'No', 'target': 'lider'}]
        response = self.admin.put(f'/api/admin/events/{self.event.pk}',
                                  self.event_input(questions=questions), content_type='application/json')
        self.assert_error(response)
        self.event.refresh_from_db()
        self.assertEqual(self.event.questions, self.questions)
        self.assertEqual(self.event.form_version, 1)

    def test_event_put_increments_version_only_for_form_changes(self):
        data = self.event_input(title='Título actualizado')
        response = self.admin.put(f'/api/admin/events/{self.event.pk}', data, content_type='application/json')
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()['form_version'], 1)
        data['questions'][0]['label'] = 'Pregunta modificada'
        response = self.admin.put(f'/api/admin/events/{self.event.pk}', data, content_type='application/json')
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()['form_version'], 2)

    def test_minor_requires_representative_and_guardian_consent(self):
        valid = self.payload(is_minor=True, guardian_name='Representante sintético',
                             guardian_email='guardian@example.test', guardian_consent=True)
        for field, value in [('guardian_consent', False), ('guardian_name', ''),
                             ('guardian_email', ''), ('guardian_email', 'invalid')]:
            with self.subTest(field=field, value=value):
                self.assert_error(self.register({**valid, field: value}))
                self.assert_no_registration()
        response = self.register(valid)
        self.assertEqual(response.status_code, 201, response.content)
        record = Registration.objects.get()
        self.assertTrue(record.is_minor)
        self.assertEqual(record.guardian_name, valid['guardian_name'])
        self.assertEqual(record.guardian_email, valid['guardian_email'])
        self.assertIs(record.consent_evidence['guardian_consent'], True)

    def test_each_required_consent_and_all_unchecked_reject(self):
        keys = ['consent', 'sensitive_consent', 'adult_confirmed']
        for changes in [{key: False} for key in keys] + [dict.fromkeys(keys, False)]:
            with self.subTest(changes=changes):
                self.assert_error(self.register(self.payload(**changes)))
                self.assert_no_registration()

    def test_capacity_conflict_does_not_increment(self):
        self.event.capacity = 1
        self.event.save(update_fields=['capacity'])
        self.assertEqual(self.register().status_code, 201)
        self.assert_error(self.register(self.payload(name='Otra persona adulta', email='other@example.test')),
                          409, 'full')
        self.event.refresh_from_db()
        self.assertEqual(self.event.registered, 1)
        self.assertEqual(Registration.objects.count(), 1)

    def test_exact_idempotent_retry_does_not_increment_even_when_full(self):
        self.event.capacity = 1
        self.event.save(update_fields=['capacity'])
        payload = self.payload()
        first = self.register(payload)
        self.assertEqual(first.status_code, 201, first.content)
        retry = self.register(payload)
        self.assertEqual(retry.status_code, 200, retry.content)
        self.assertEqual(retry.json(), {'reference': first.json()['reference'], 'duplicate': True})
        self.event.refresh_from_db()
        self.assertEqual(self.event.registered, 1)
        self.assertEqual(Registration.objects.count(), 1)

    def test_idempotency_key_rejects_changed_answers(self):
        payload = self.payload()
        self.assertEqual(self.register(payload).status_code, 201)
        payload['answers']['availability'] = 'Tarde'
        self.assert_error(self.register(payload), 409, 'duplicate_request')
        self.event.refresh_from_db()
        self.assertEqual(self.event.registered, 1)
        self.assertEqual(Registration.objects.get().answers['availability'], 'Mañana')

    def test_idempotency_key_rejects_changed_identity(self):
        payload = self.payload()
        self.assertEqual(self.register(payload).status_code, 201)
        self.assert_error(self.register({**payload, 'email': 'different@example.test'}), 409, 'duplicate_request')
        self.assertEqual(Registration.objects.count(), 1)

    def test_stale_form_or_privacy_version_rejected(self):
        for changes in [{'form_version': self.event.form_version + 1}, {'privacy_version': 'old-test-version'}]:
            with self.subTest(changes=changes):
                self.assert_error(self.register(self.payload(**changes)), 409, 'version_conflict')
                self.assert_no_registration()

    def test_closed_or_past_events_reject_registration(self):
        for changes in [{'status': 'closed'}, {'status': 'published', 'date': timezone.now() - timedelta(days=1)}]:
            with self.subTest(changes=changes):
                Event.objects.filter(pk=self.event.pk).update(**changes)
                self.assert_error(self.register(), 409, 'closed')
                self.assert_no_registration()

    def test_registration_rate_limit_after_thirty_requests(self):
        cache.clear()
        for attempt in range(30):
            response = self.register(self.payload(consent=False))
            self.assert_error(response)
        self.assert_error(self.register(), 429, 'rate_limit')
        self.assert_no_registration()

    def test_fake_malformed_wrong_extension_and_oversized_images_rejected(self):
        payload = self.use_upload_question('images')
        image = self.image_bytes()
        cases = [('fake.png', b'not an image'), ('truncated.png', image[:40]),
                 ('image.exe', image), ('huge.png', b'x' * (5 * 1024 * 1024 + 1)),
                 ('empty.png', b'')]
        for name, raw in cases:
            with self.subTest(name=name):
                upload = SimpleUploadedFile(name, raw, content_type='image/png')
                self.assert_error(self.register(payload, {'file_document': upload}))
                self.assert_no_registration()

    def test_pdf_upload_stays_private_and_requires_staff_download(self):
        payload = self.use_upload_question('documents')
        upload = self.pdf()
        raw = upload.read()
        upload.seek(0)
        response = self.register(payload, {'file_document': upload})
        self.assertEqual(response.status_code, 201, response.content)
        attachment = Attachment.objects.get()
        path = self.private_root / attachment.storage_name
        self.assertEqual(path.read_bytes(), raw)
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        rows = self.admin.get('/api/admin/registrations').json()['registrations']
        url = rows[0]['attachments'][0]['url']
        self.assertEqual(url, f'/api/admin/files/{attachment.pk}')
        self.assertNotIn('/media/', url)
        self.assert_error(self.client.get(url), 401, 'unauthorized')
        self.assertEqual(self.client.get(f'/media/{attachment.storage_name}').status_code, 404)
        response = self.admin.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertIn('attachment;', response['Content-Disposition'])
        self.assertEqual(response['X-Content-Type-Options'], 'nosniff')
        self.assertIn('sandbox', response['Content-Security-Policy'])
        self.assertEqual(b''.join(response.streaming_content), raw)
        response.close()

    def test_duplicate_file_fields_are_rejected(self):
        payload = self.use_upload_question('documents')
        self.assert_error(self.register(payload, {'file_document': [self.pdf(), self.pdf()]}))
        self.assert_no_registration()

    def test_event_image_upload_is_reencoded_without_metadata(self):
        raw = self.image_bytes()
        with Image.open(BytesIO(raw)) as source:
            self.assertEqual(source.info['Author'], 'synthetic-private-metadata')
            self.assertEqual(source.getexif()[315], 'synthetic-private-metadata')
        response = self.admin.post('/api/admin/images',
                                   {'file': SimpleUploadedFile('metadata.png', raw, content_type='image/png')})
        self.assertEqual(response.status_code, 201, response.content)
        url = response.json()['url']
        self.assertRegex(url, r'^/media/[a-f0-9]{32}\.jpg$')
        stored = (self.media_root / url.rsplit('/', 1)[1]).read_bytes()
        self.assertNotIn(b'synthetic-private-metadata', stored)
        with Image.open(BytesIO(stored)) as image:
            self.assertEqual(image.format, 'JPEG')
            self.assertFalse(image.getexif())
            self.assertNotIn('Author', image.info)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(b''.join(response.streaming_content), stored)
        response.close()
        self.assertFalse(Attachment.objects.exists())

    def test_event_image_rejects_fake_and_nonimage_files(self):
        for name, raw in [('fake.jpg', b'fake'), ('image.svg', self.image_bytes()),
                          ('large.png', b'x' * (5 * 1024 * 1024 + 1))]:
            with self.subTest(name=name):
                self.assert_error(self.admin.post('/api/admin/images',
                                                  {'file': SimpleUploadedFile(name, raw)}))
                self.assertFalse(self.media_root.exists() and any(self.media_root.iterdir()))

    def test_csv_export_neutralizes_formula_prefixes(self):
        for index, prefix in enumerate(['=', '+', '-', '@', '  =']):
            response = self.register(self.payload(name=f'{prefix}SUM(1,1)',
                                                  email=f'csv{index}@example.test', phone='+12345'))
            self.assertEqual(response.status_code, 201, response.content)
        response = self.admin.get('/api/admin/registrations/export')
        self.assertEqual(response.status_code, 200)
        rows = list(csv.reader(StringIO(response.content.decode('utf-8-sig'))))
        self.assertEqual(len(rows), 6)
        for row in rows[1:]:
            self.assertTrue(row[3].startswith("'"), row)
            self.assertEqual(row[5], "'+12345")

    def test_retention_dry_run_preserves_records_counts_and_files(self):
        payload = self.use_upload_question('documents')
        response = self.register(payload, {'file_document': self.pdf()})
        self.assertEqual(response.status_code, 201, response.content)
        Registration.objects.update(expires_at=timezone.now() - timedelta(days=1))
        before_records = list(Registration.objects.values())
        before_attachments = list(Attachment.objects.values())
        before_events = list(Event.objects.values())
        attachment = Attachment.objects.get()
        path = self.private_root / attachment.storage_name
        before_file = path.read_bytes()
        output = StringIO()
        call_command('purge_expired', stdout=output)
        self.assertIn('Registros vencidos: 1', output.getvalue())
        self.assertIn('Simulación: no se modificó ningún dato.', output.getvalue())
        self.assertEqual(list(Registration.objects.values()), before_records)
        self.assertEqual(list(Attachment.objects.values()), before_attachments)
        self.assertEqual(list(Event.objects.values()), before_events)
        self.assertEqual(path.read_bytes(), before_file)

    def test_recorrido_ignora_saltos_corruptos_sin_colgarse(self):
        # Los datos escritos fuera de la API (seeds, shell, fixtures) no pasan por questions_schema,
        # así que el recorrido debe tolerar saltos hacia atrás o a preguntas inexistentes.
        from events.validation import active_questions
        preguntas = [
            self.question('uno', 'radio', options=['Sí', 'No'], rules=[{'value': 'No', 'target': 'uno'}]),
            self.question('dos', 'radio', options=['Sí', 'No'], rules=[{'value': 'No', 'target': 'fantasma'}]),
            self.question('tres'),
        ]
        self.assertEqual([q['id'] for q in active_questions(preguntas, {'uno': 'No'})], ['uno', 'dos', 'tres'])
        self.assertEqual([q['id'] for q in active_questions(preguntas, {'dos': 'No'})], ['uno', 'dos', 'tres'])
