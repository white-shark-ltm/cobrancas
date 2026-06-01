"""
Middleware de isolamento de tenant por thread.

Injeta o ProfessionalProfile do usuário autenticado em threading.local()
para que managers e models consigam filtrar dados automaticamente sem
precisar receber o tenant como parâmetro explícito.

O tenant é limpo ao final de cada request para evitar vazamento entre
requisições reutilizadas pelo mesmo thread (ex: servidores WSGI em pool).
"""

import threading

from django.contrib.auth.models import AnonymousUser

_thread_locals = threading.local()


def get_current_tenant():
    """Retorna o ProfessionalProfile ativo no contexto da thread atual, ou None."""
    return getattr(_thread_locals, 'tenant', None)


class TenantMiddleware:
    """Popula _thread_locals.tenant para cada request autenticado."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        _thread_locals.tenant = None

        user = getattr(request, 'user', None)
        if user and not isinstance(user, AnonymousUser) and user.is_authenticated:
            # Usa select_related para evitar query extra por request
            profile = getattr(user, 'profile', None)
            _thread_locals.tenant = profile

        try:
            response = self.get_response(request)
        finally:
            # Limpa independente de exceções para evitar vazamento entre threads
            _thread_locals.tenant = None

        return response
