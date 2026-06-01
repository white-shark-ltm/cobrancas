"""
Fixtures para os testes E2E do sistema Cobranças.

Limpa os clientes, projetos e faturas dos tenants de teste antes de cada sessão
para garantir que os testes sejam idempotentes ao rodar múltiplas vezes na mesma DB.
"""

import django
import pytest


@pytest.fixture(scope="session", autouse=True)
def clean_test_tenants(django_db_setup, django_db_blocker):
    """Apaga todos os clientes, projetos e faturas dos tenants de teste antes da sessão."""
    with django_db_blocker.unblock():
        from django.contrib.auth import get_user_model
        from clients.models import Client
        from projects.models import Project

        User = get_user_model()
        test_users = User.objects.filter(username__in=["freelancer1", "freelancer2"])
        for user in test_users:
            try:
                profile = user.profile
                from billing.models import Invoice, Payment
                # Payments têm on_delete=PROTECT em Invoice — deletar primeiro
                Payment.all_objects.filter(tenant=profile).delete()
                Invoice.all_objects.filter(tenant=profile).delete()
                Project.all_objects.filter(tenant=profile).delete()
                Client.all_objects.filter(tenant=profile).delete()
            except Exception:
                pass

        # Recria clientes mínimos necessários para os testes de projetos
        u1 = User.objects.filter(username="freelancer1").first()
        u2 = User.objects.filter(username="freelancer2").first()

        if u1:
            profile1 = u1.profile
            clients1 = []
            for i, (name, email) in enumerate([
                ("Cliente Teste A", "cliente.a.setup@teste.com"),
                ("Cliente Teste B", "cliente.b.setup@teste.com"),
            ]):
                c, _ = Client.all_objects.get_or_create(
                    tenant=profile1,
                    email=email,
                    defaults={"name": name, "active": True},
                )
                clients1.append(c)

            # Recria projetos mínimos necessários para os testes de billing
            for i, (pname, client) in enumerate([
                ("Projeto Setup Alpha", clients1[0]),
                ("Projeto Setup Beta", clients1[1]),
            ]):
                Project.all_objects.get_or_create(
                    tenant=profile1,
                    name=pname,
                    defaults={
                        "client": client,
                        "status": "active",
                        "rate": 3000,
                        "rate_type": "fixed",
                    },
                )

        if u2:
            profile2 = u2.profile
            c2, _ = Client.all_objects.get_or_create(
                tenant=profile2,
                email="cliente.t2.setup@teste.com",
                defaults={"name": "Cliente T2 Setup", "active": True},
            )
            Project.all_objects.get_or_create(
                tenant=profile2,
                name="Projeto Setup T2",
                defaults={
                    "client": c2,
                    "status": "active",
                    "rate": 1500,
                    "rate_type": "fixed",
                },
            )
