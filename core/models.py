"""
Base de isolamento multi-tenant para todo o sistema.

TenantModel é a classe abstrata que todos os models de negócio herdam.
Garante que:
  - Cada registro pertence a exatamente um ProfessionalProfile (tenant).
  - O campo tenant é preenchido automaticamente no save() via contexto de thread.
  - Queries via `objects` são sempre filtradas pelo tenant ativo.
  - `all_objects` oferece acesso irrestrito para o admin do Django.
"""

from django.db import models


class TenantQuerySet(models.QuerySet):
    """QuerySet com método de filtragem por tenant."""

    def for_tenant(self, tenant):
        return self.filter(tenant=tenant)


class TenantManager(models.Manager):
    """
    Manager padrão dos models de negócio.

    Filtra automaticamente pelo tenant ativo na thread atual.
    Se não houver tenant (admin, shell sem contexto), devolve tudo.
    """

    def get_queryset(self):
        from accounts.middleware import get_current_tenant
        qs = TenantQuerySet(self.model, using=self._db)
        tenant = get_current_tenant()
        if tenant is not None:
            return qs.for_tenant(tenant)
        return qs

    def get_queryset_unscoped(self):
        """Escape hatch explícito — retorna todos os registros sem filtro de tenant."""
        return TenantQuerySet(self.model, using=self._db)


class TenantModel(models.Model):
    """
    Model abstrato base para todos os models de negócio do sistema.

    Subclasses ganham automaticamente:
      - Campo `tenant` vinculado ao ProfessionalProfile.
      - Manager `objects` com filtragem automática por tenant.
      - Manager `all_objects` sem filtragem (para admin/sistema).
    """

    tenant = models.ForeignKey(
        'accounts.ProfessionalProfile',
        on_delete=models.CASCADE,
        db_index=True,
        editable=False,
        related_name='+',
    )

    objects = TenantManager()
    all_objects = models.Manager()

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if not self.tenant_id:
            from accounts.middleware import get_current_tenant
            tenant = get_current_tenant()
            if tenant is None:
                raise ValueError(
                    f"Não há tenant ativo no contexto. Impossível salvar {self.__class__.__name__}."
                )
            self.tenant = tenant
        super().save(*args, **kwargs)
