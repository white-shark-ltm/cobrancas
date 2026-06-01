"""
Models de projetos do freelancer.

Project representa um trabalho contratado por um Client. Herda de TenantModel,
garantindo isolamento automático por tenant em todas as queries.
"""

from datetime import date

from django.db import models

from core.models import TenantModel


class ProjectStatus(models.TextChoices):
    DRAFT = 'draft', 'Rascunho'
    ACTIVE = 'active', 'Ativo'
    PAUSED = 'paused', 'Pausado'
    COMPLETED = 'completed', 'Concluído'
    CANCELLED = 'cancelled', 'Cancelado'


class Project(TenantModel):
    """Projeto contratado por um cliente. Isolado por tenant."""

    RATE_TYPE_CHOICES = [
        ('hourly', 'Por hora'),
        ('fixed', 'Fixo'),
    ]

    client = models.ForeignKey(
        'clients.Client',
        on_delete=models.PROTECT,
        related_name='projects',
    )
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    status = models.CharField(
        max_length=20,
        choices=ProjectStatus.choices,
        default=ProjectStatus.DRAFT,
    )
    rate = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    rate_type = models.CharField(max_length=10, choices=RATE_TYPE_CHOICES, default='fixed')
    started_at = models.DateField(null=True, blank=True)
    deadline = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Projeto'
        verbose_name_plural = 'Projetos'

    def __str__(self):
        return f'{self.client.name} — {self.name}'

    @property
    def is_overdue(self):
        if not self.deadline:
            return False
        terminal = {ProjectStatus.COMPLETED, ProjectStatus.CANCELLED}
        return self.deadline < date.today() and self.status not in terminal
