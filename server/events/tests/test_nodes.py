import time
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.utils import timezone

from events.models import Event, Membership, OrgNode

PASSWORD = 'Synthetic-test-password-7391!'


class NodeApiTests(TestCase):
    # Dos congregaciones bajo la raíz, cada una con red -> subred -> grupo. Réplica mínima
    # del montaje de test_scope.py (no importable sin arrastrar sus propios tests).
    def setUp(self):
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
            ('apostol', self.root, 'apostol-nodes'),
            ('pastor', self.cong_a, 'pastor-nodes-a'),
            ('estaca', self.group_a, 'estaca-nodes-a'),
        ]:
            user = get_user_model().objects.create_user(username=username, password=PASSWORD, is_staff=True)
            Membership.objects.create(user=user, node=node, role=role)
            self.users[role] = user

    def login(self, role):
        client = Client()
        client.force_login(self.users[role], backend='django.contrib.auth.backends.ModelBackend')
        session = client.session
        session['authenticated_at'] = time.time()
        session.save()
        return client

    def make_event(self, owner, title):
        return Event.objects.create(
            title=title, category='Iglesia', summary='Resumen', description='Descripción',
            date=timezone.now() + timedelta(days=15), location='Lugar ficticio', capacity=10,
            cover='/posters/encuentro.svg', gallery=[], status='draft', featured=False,
            questions=[], owner=owner,
        )

    # ---- GET ----

    def test_apostol_lista_toda_la_organizacion(self):
        response = self.login('apostol').get('/api/admin/nodes')
        self.assertEqual(response.status_code, 200)
        ids = [node['id'] for node in response.json()['nodes']]
        self.assertCountEqual(ids, [str(node.pk) for node in [
            self.root, self.cong_a, self.net_a, self.sub_a, self.group_a,
            self.cong_b, self.net_b, self.sub_b, self.group_b,
        ]])

    def test_pastor_lista_solo_su_subarbol(self):
        response = self.login('pastor').get('/api/admin/nodes')
        self.assertEqual(response.status_code, 200)
        ids = [node['id'] for node in response.json()['nodes']]
        self.assertCountEqual(ids, [str(node.pk) for node in [self.cong_a, self.net_a, self.sub_a, self.group_a]])
        self.assertNotIn(str(self.root.pk), ids)
        self.assertNotIn(str(self.cong_b.pk), ids)
        self.assertNotIn(str(self.net_b.pk), ids)
        self.assertNotIn(str(self.sub_b.pk), ids)
        self.assertNotIn(str(self.group_b.pk), ids)

    # ---- POST ----

    def test_post_valido_en_cadena(self):
        client = self.login('pastor')
        response = client.post('/api/admin/nodes', {'kind': 'network', 'name': 'Red Nueva', 'parent': str(self.cong_a.pk)}, content_type='application/json')
        self.assertEqual(response.status_code, 201, response.content)
        network = response.json()
        self.assertEqual(network['parent'], str(self.cong_a.pk))

        response = client.post('/api/admin/nodes', {'kind': 'subnetwork', 'name': 'Subred Nueva', 'parent': network['id']}, content_type='application/json')
        self.assertEqual(response.status_code, 201, response.content)
        subnetwork = response.json()
        self.assertEqual(subnetwork['parent'], network['id'])

        response = client.post('/api/admin/nodes', {'kind': 'group', 'name': 'Grupo Nuevo', 'parent': subnetwork['id']}, content_type='application/json')
        self.assertEqual(response.status_code, 201, response.content)
        group = response.json()
        self.assertEqual(group['parent'], subnetwork['id'])

    def test_post_kind_organization_rechazado(self):
        response = self.login('pastor').post('/api/admin/nodes', {'kind': 'organization', 'name': 'Otra raíz', 'parent': str(self.cong_a.pk)}, content_type='application/json')
        self.assertEqual(response.status_code, 400)

    def test_post_parent_fuera_de_ambito_da_404(self):
        response = self.login('pastor').post('/api/admin/nodes', {'kind': 'network', 'name': 'Red Intrusa', 'parent': str(self.cong_b.pk)}, content_type='application/json')
        self.assertEqual(response.status_code, 404)
        mensaje_ajeno = response.json()['error']['message']

        response = self.login('pastor').post('/api/admin/nodes', {'kind': 'network', 'name': 'Red Fantasma', 'parent': '00000000-0000-0000-0000-000000000000'}, content_type='application/json')
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()['error']['message'], mensaje_ajeno)

    def test_post_padre_de_tipo_incorrecto(self):
        response = self.login('pastor').post('/api/admin/nodes', {'kind': 'group', 'name': 'Grupo Directo', 'parent': str(self.cong_a.pk)}, content_type='application/json')
        self.assertEqual(response.status_code, 400)

    def test_post_nombre_duplicado_entre_hermanos(self):
        client = self.login('pastor')
        response = client.post('/api/admin/nodes', {'kind': 'network', 'name': 'Red Norte', 'parent': str(self.cong_a.pk)}, content_type='application/json')
        self.assertEqual(response.status_code, 201)
        response = client.post('/api/admin/nodes', {'kind': 'network', 'name': 'red norte', 'parent': str(self.cong_a.pk)}, content_type='application/json')
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()['error']['code'], 'duplicate_name')

    # ---- PUT ----

    def test_put_renombrar(self):
        response = self.login('pastor').put(f'/api/admin/nodes/{self.net_a.pk}', {'name': 'Red A Renombrada'}, content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['name'], 'Red A Renombrada')
        self.net_a.refresh_from_db()
        self.assertEqual(self.net_a.name, 'Red A Renombrada')

    def test_put_archivar(self):
        response = self.login('pastor').put(f'/api/admin/nodes/{self.net_a.pk}', {'active': False}, content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()['active'])
        self.net_a.refresh_from_db()
        self.assertFalse(self.net_a.active)

    def test_put_nodo_ajeno_da_404(self):
        response = self.login('pastor').put(f'/api/admin/nodes/{self.net_b.pk}', {'name': 'Intento'}, content_type='application/json')
        self.assertEqual(response.status_code, 404)

    def test_put_ignora_kind_y_parent(self):
        response = self.login('pastor').put(f'/api/admin/nodes/{self.net_a.pk}', {'kind': 'group', 'parent': str(self.cong_b.pk), 'name': 'Red A'}, content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.net_a.refresh_from_db()
        self.assertEqual(self.net_a.kind, 'network')
        self.assertEqual(self.net_a.parent_id, self.cong_a.pk)

    def test_put_no_puede_archivar_la_raiz(self):
        response = self.login('apostol').put(f'/api/admin/nodes/{self.root.pk}', {'active': False}, content_type='application/json')
        self.assertEqual(response.status_code, 400)

    # ---- DELETE ----

    def test_delete_hoja_limpia(self):
        hoja = OrgNode.objects.create(kind='group', name='Grupo Temporal', parent=self.sub_a)
        response = self.login('pastor').delete(f'/api/admin/nodes/{hoja.pk}')
        self.assertEqual(response.status_code, 204)
        self.assertFalse(OrgNode.objects.filter(pk=hoja.pk).exists())

    def test_delete_con_hijo(self):
        response = self.login('pastor').delete(f'/api/admin/nodes/{self.sub_a.pk}')
        self.assertEqual(response.status_code, 409)
        body = response.json()['error']
        self.assertEqual(body['code'], 'protected')
        self.assertEqual(body['fields']['children'], 1)

    def test_delete_con_evento(self):
        hoja = OrgNode.objects.create(kind='group', name='Grupo Con Evento', parent=self.sub_a)
        self.make_event(hoja, 'Evento del grupo')
        response = self.login('pastor').delete(f'/api/admin/nodes/{hoja.pk}')
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()['error']['fields']['events'], 1)

    def test_delete_con_membresia(self):
        hoja = OrgNode.objects.create(kind='group', name='Grupo Con Membresía', parent=self.sub_a)
        otro = get_user_model().objects.create_user(username='miembro-temporal', password=PASSWORD, is_staff=True)
        Membership.objects.create(user=otro, node=hoja, role='estaca')
        response = self.login('pastor').delete(f'/api/admin/nodes/{hoja.pk}')
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()['error']['fields']['memberships'], 1)

    def test_delete_raiz_rechazado(self):
        response = self.login('apostol').delete(f'/api/admin/nodes/{self.root.pk}')
        self.assertEqual(response.status_code, 400)

    def test_delete_nodo_ajeno_da_404(self):
        response = self.login('pastor').delete(f'/api/admin/nodes/{self.group_b.pk}')
        self.assertEqual(response.status_code, 404)

    # ---- Estaca sin node.manage ----

    def test_estaca_recibe_403_en_los_cuatro_metodos(self):
        client = self.login('estaca')
        self.assertEqual(client.get('/api/admin/nodes').status_code, 403)
        self.assertEqual(client.post('/api/admin/nodes', {'kind': 'network', 'name': 'X', 'parent': str(self.cong_a.pk)}, content_type='application/json').status_code, 403)
        self.assertEqual(client.put(f'/api/admin/nodes/{self.group_a.pk}', {'name': 'Y'}, content_type='application/json').status_code, 403)
        self.assertEqual(client.delete(f'/api/admin/nodes/{self.group_a.pk}').status_code, 403)
