from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import IntegrityError, connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.db.models import ProtectedError
from django.test import TestCase, TransactionTestCase
from django.utils import timezone

from events.models import Event, Membership, OrgNode
from events.security import ApiProblem
from events.validation import validar_membresia, validar_nodo


class OrgNodeTests(TestCase):
    def setUp(self):
        # La raíz ya existe: la crea la migración 0004 al construir la base de pruebas.
        self.root = OrgNode.objects.get(kind='organization')

    def build_tree(self):
        congregation = OrgNode.objects.create(kind='congregation', name='Congregación Norte', parent=self.root)
        network = OrgNode.objects.create(kind='network', name='Red Uno', parent=congregation)
        subnetwork = OrgNode.objects.create(kind='subnetwork', name='Subred Uno', parent=network)
        group = OrgNode.objects.create(kind='group', name='Grupo Uno', parent=subnetwork)
        return congregation, network, subnetwork, group

    def test_path_se_calcula_solo_al_guardar(self):
        congregation, network, subnetwork, group = self.build_tree()
        self.assertEqual(congregation.path, f'{self.root.path}{congregation.id}/')
        self.assertEqual(network.path, f'{congregation.path}{network.id}/')
        self.assertEqual(subnetwork.path, f'{network.path}{subnetwork.id}/')
        self.assertEqual(group.path, f'{subnetwork.path}{group.id}/')

    def test_descendants_devuelve_el_subarbol(self):
        congregation, network, subnetwork, group = self.build_tree()
        self.assertEqual(set(network.descendants()), {network, subnetwork, group})
        self.assertEqual(set(group.descendants()), {group})

    def test_dos_organizaciones_lanza_integrity_error(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                OrgNode.objects.create(kind='organization', name='Otra organización')

    def test_hermanos_con_mismo_nombre_ignorando_mayusculas_lanza_integrity_error(self):
        OrgNode.objects.create(kind='congregation', name='Congregación Sur', parent=self.root)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                OrgNode.objects.create(kind='congregation', name='congregación sur', parent=self.root)

    def test_mismo_nombre_bajo_padres_distintos_no_lanza_error(self):
        congregation_a = OrgNode.objects.create(kind='congregation', name='Congregación A', parent=self.root)
        congregation_b = OrgNode.objects.create(kind='congregation', name='Congregación B', parent=self.root)
        OrgNode.objects.create(kind='network', name='Red compartida', parent=congregation_a)
        # No debe lanzar: el nombre se repite pero bajo un padre distinto.
        OrgNode.objects.create(kind='network', name='Red compartida', parent=congregation_b)

    def test_borrar_nodo_con_hijos_lanza_protected_error(self):
        congregation, *_ = self.build_tree()
        with self.assertRaises(ProtectedError):
            congregation.delete()

    def test_borrar_nodo_con_membresias_lanza_protected_error(self):
        congregation = OrgNode.objects.create(kind='congregation', name='Congregación con líder', parent=self.root)
        user = get_user_model().objects.create_user(username='pastor-test', password='Synthetic-test-password-7391!')
        Membership.objects.create(user=user, node=congregation, role='pastor')
        with self.assertRaises(ProtectedError):
            congregation.delete()

    def test_borrar_nodo_con_eventos_lanza_protected_error(self):
        congregation = OrgNode.objects.create(kind='congregation', name='Congregación con eventos', parent=self.root)
        Event.objects.create(title='Evento de prueba', category='Iglesia', summary='Resumen', description='Descripción',
                              date=timezone.now() + timedelta(days=5), location='Lugar ficticio', cover='/posters/encuentro.svg',
                              owner=congregation)
        with self.assertRaises(ProtectedError):
            congregation.delete()


class ValidacionOrgTests(TestCase):
    def setUp(self):
        self.root = OrgNode.objects.get(kind='organization')

    def test_validar_nodo_caso_valido(self):
        validar_nodo('congregation', self.root)  # no debe lanzar

    def test_validar_nodo_padre_incorrecto_lanza_api_problem(self):
        congregation = OrgNode.objects.create(kind='congregation', name='Congregación válida', parent=self.root)
        with self.assertRaises(ApiProblem):
            validar_nodo('network', self.root)
        with self.assertRaises(ApiProblem):
            validar_nodo('subnetwork', congregation)

    def test_validar_membresia_caso_valido(self):
        congregation = OrgNode.objects.create(kind='congregation', name='Congregación de membresía', parent=self.root)
        validar_membresia('pastor', congregation)  # no debe lanzar

    def test_validar_membresia_rol_no_aplica_al_nodo_lanza_api_problem(self):
        network = OrgNode.objects.create(kind='network', name='Red de prueba', parent=self.root)
        with self.assertRaises(ApiProblem):
            validar_membresia('pastor', network)
        with self.assertRaises(ApiProblem):
            validar_membresia('rol-inexistente', self.root)


class MigracionDeDatosTests(TransactionTestCase):
    # TransactionTestCase porque MigrationExecutor aplica cambios reales de esquema:
    # una TestCase normal (con transacción envolvente) no puede convivir con eso.
    def test_backfill_de_0004_asigna_raiz_owner_y_membresia_apostol(self):
        executor = MigrationExecutor(connection)
        executor.migrate([('events', '0003_org_expand')])
        executor.loader.build_graph()
        old_apps = executor.loader.project_state([('events', '0003_org_expand')]).apps
        OldEvent = old_apps.get_model('events', 'Event')
        OldUser = old_apps.get_model(*settings.AUTH_USER_MODEL.split('.'))

        # Evento huérfano y usuario de staff sin membresía, como quedarían tras 0003
        # si el contenedor viejo siguiera escribiendo durante el despliegue.
        orphan = OldEvent.objects.create(
            title='Evento huérfano', category='Iglesia', summary='Resumen', description='Descripción',
            date=timezone.now() + timedelta(days=1), location='Lugar ficticio', cover='/posters/encuentro.svg',
        )
        staffer = OldUser.objects.create(username='huerfano-staff', is_staff=True, password='!')

        executor = MigrationExecutor(connection)
        executor.migrate([('events', '0005_org_contract')])

        roots = OrgNode.objects.filter(kind='organization')
        self.assertEqual(roots.count(), 1)
        root = roots.get()
        self.assertEqual(Event.objects.get(pk=orphan.pk).owner_id, root.pk)
        self.assertTrue(Membership.objects.filter(user_id=staffer.pk, node=root, role='apostol').exists())
