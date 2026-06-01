"""
Models de faturamento: Invoice, InvoiceItem e Payment.

Invoice representa uma cobrança emitida para um cliente em um projeto.
InvoiceItem detalha os serviços cobrados. Payment registra recebimentos.
Todos herdam de TenantModel para isolamento automático por tenant.
"""

from datetime import date
from decimal import Decimal

from django.db import models

from core.models import TenantModel


class InvoiceStatus(models.TextChoices):
    DRAFT = 'draft', 'Rascunho'
    SENT = 'sent', 'Enviada'
    PAID = 'paid', 'Paga'
    OVERDUE = 'overdue', 'Vencida'
    CANCELLED = 'cancelled', 'Cancelada'


class Invoice(TenantModel):
    """Fatura emitida para um cliente. Isolada por tenant."""

    project = models.ForeignKey(
        'projects.Project',
        on_delete=models.PROTECT,
        related_name='invoices',
    )
    client = models.ForeignKey(
        'clients.Client',
        on_delete=models.PROTECT,
        related_name='invoices',
    )
    number = models.CharField(max_length=20)
    status = models.CharField(
        max_length=20,
        choices=InvoiceStatus.choices,
        default=InvoiceStatus.DRAFT,
    )
    issue_date = models.DateField(default=date.today)
    due_date = models.DateField()
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-issue_date']
        unique_together = [['tenant', 'number']]
        verbose_name = 'Fatura'
        verbose_name_plural = 'Faturas'

    def __str__(self):
        return f'Fatura #{self.number} — {self.client.name}'

    @property
    def total(self):
        return sum(item.total for item in self.items.all()) or Decimal('0.00')

    @property
    def is_overdue(self):
        terminal = {InvoiceStatus.PAID, InvoiceStatus.CANCELLED}
        return self.due_date < date.today() and self.status not in terminal

    def mark_as_sent(self):
        self.status = InvoiceStatus.SENT
        self.save()

    def mark_as_paid(self):
        self.status = InvoiceStatus.PAID
        self.save()


class InvoiceItem(TenantModel):
    """Linha de serviço dentro de uma fatura."""

    invoice = models.ForeignKey(
        Invoice,
        on_delete=models.CASCADE,
        related_name='items',
    )
    description = models.CharField(max_length=200)
    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=1)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']
        verbose_name = 'Item de Fatura'
        verbose_name_plural = 'Itens de Fatura'

    def __str__(self):
        return f'{self.description} (x{self.quantity})'

    @property
    def total(self):
        return self.quantity * self.unit_price


class Payment(TenantModel):
    """Registro de recebimento vinculado a uma fatura."""

    METHOD_CHOICES = [
        ('pix', 'PIX'),
        ('bank_transfer', 'Transferência'),
        ('cash', 'Dinheiro'),
        ('other', 'Outro'),
    ]

    invoice = models.ForeignKey(
        Invoice,
        on_delete=models.PROTECT,
        related_name='payments',
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    method = models.CharField(max_length=20, choices=METHOD_CHOICES)
    paid_at = models.DateField(default=date.today)
    notes = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-paid_at']
        verbose_name = 'Pagamento'
        verbose_name_plural = 'Pagamentos'

    def __str__(self):
        return f'R${self.amount} em {self.paid_at}'
