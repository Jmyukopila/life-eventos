from django.db.models import Q
from .models import Event, Membership, OrgNode

PERMISOS_POR_ROL = {
    'apostol':   {'settings.edit', 'event.view', 'event.create', 'event.edit', 'event.publish', 'event.assign',
                  'registration.view', 'registration.export', 'node.manage', 'user.manage'},
    'pastor':    {'event.view', 'event.create', 'event.edit', 'event.publish', 'event.assign',
                  'registration.view', 'registration.export', 'node.manage', 'user.manage'},
    'lider_red': {'event.view', 'event.create', 'event.edit', 'event.publish', 'event.assign',
                  'registration.view', 'registration.export', 'node.manage', 'user.manage'},
    'lider':     {'event.view', 'event.create', 'event.edit', 'event.publish',
                  'registration.view', 'registration.export', 'node.manage', 'user.manage'},
    'estaca':    {'event.view', 'event.edit', 'registration.view'},
}

# Orden de rango, del más alto al más bajo: decide, entre varias membresías, cuál manda
# (por ejemplo, el nodo dueño de un evento nuevo).
RANGO_ROL = ['apostol', 'pastor', 'lider_red', 'lider', 'estaca']


class Scope:
    def __init__(self, user):
        self.memberships = list(Membership.objects.filter(user=user).select_related('node'))
        # Sin membresías, permissions queda vacío: un is_staff sin Membership no ve nada
        # ni puede nada, aunque haya pasado la comprobación de staff.
        self.permissions = frozenset().union(*(PERMISOS_POR_ROL.get(m.role, set()) for m in self.memberships)) if self.memberships else frozenset()

    def can(self, permission):
        return permission in self.permissions

    def nodes(self):
        if not self.memberships:
            return OrgNode.objects.none()
        query = Q()
        for membership in self.memberships:
            query |= Q(path__startswith=membership.node.path)
        return OrgNode.objects.filter(query)

    def covers(self, node):
        return any(node.path.startswith(membership.node.path) for membership in self.memberships)

    def events(self):
        nodes = self.nodes()
        return Event.objects.filter(Q(owner__in=nodes) | Q(guests__in=nodes)).distinct()

    def owned_events(self):
        return Event.objects.filter(owner__in=self.nodes())
