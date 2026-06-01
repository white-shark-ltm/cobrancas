"""
Modelos de autenticação e perfil do tenant.

User substitui o modelo padrão do Django para permitir extensões futuras.
ProfessionalProfile representa o tenant no modelo de isolamento lógico:
cada freelancer tem exatamente um perfil, e todos os dados do sistema
pertencem a um perfil.
"""

from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """Usuário customizado — ponto de extensão para campos futuros."""

    class Meta:
        verbose_name = 'Usuário'
        verbose_name_plural = 'Usuários'

    def __str__(self):
        return self.username


class ProfessionalProfile(models.Model):
    """
    Tenant do sistema. Cada instância representa um freelancer isolado.
    Todo model de negócio possui ForeignKey para este model.
    """

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='profile',
    )
    name = models.CharField(max_length=200)
    document = models.CharField(max_length=20, blank=True)  # CPF ou CNPJ
    phone = models.CharField(max_length=20, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Perfil Profissional'
        verbose_name_plural = 'Perfis Profissionais'

    def __str__(self):
        return self.name or self.user.username
