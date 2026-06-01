"""
Model de clientes do freelancer.

Client herda de TenantModel, garantindo isolamento automático por tenant.
Cada registro de cliente pertence a exatamente um ProfessionalProfile,
e a constraint unique_together impede emails duplicados dentro do mesmo tenant.
"""

from django.db import models

from core.models import TenantModel


class Client(TenantModel):
    """Cliente de um freelancer. Isolado automaticamente por tenant."""

    name = models.CharField(max_length=200)
    email = models.EmailField()
    phone = models.CharField(max_length=20, blank=True)
    document = models.CharField(max_length=20, blank=True)  # CPF ou CNPJ
    notes = models.TextField(blank=True)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']
        unique_together = [['tenant', 'email']]
        verbose_name = 'Cliente'
        verbose_name_plural = 'Clientes'

    def __str__(self):
        return self.name
