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


class InvalidInvoiceTransition(Exception):
    """
    Transição de status recusada pela regra de negócio.

    Exceção de domínio: representa a violação de uma invariante do ciclo de
    vida da fatura, independente da camada que tentou a transição (view, admin,
    API, shell). Quem chama deve traduzi-la para o canal apropriado.
    """


class Invoice(TenantModel):
    """Fatura emitida para um cliente. Isolada por tenant."""

    project = models.ForeignKey(
        'projects.Project',
        on_delete=models.PROTECT,
        related_name='invoices',
        verbose_name='Projeto',
    )
    client = models.ForeignKey(
        'clients.Client',
        on_delete=models.PROTECT,
        related_name='invoices',
        verbose_name='Cliente',
    )
    number = models.CharField(max_length=20, verbose_name='Número')
    status = models.CharField(
        max_length=20,
        choices=InvoiceStatus.choices,
        default=InvoiceStatus.DRAFT,
    )
    issue_date = models.DateField(default=date.today, verbose_name='Data de Emissão')
    due_date = models.DateField(verbose_name='Vencimento')
    notes = models.TextField(blank=True, verbose_name='Observações')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Máquina de estados do ciclo de vida da fatura.
    # Fonte única de verdade sobre quais transições são legais — toda mudança
    # de status passa por aqui, garantindo a invariante em qualquer chamador.
    ALLOWED_TRANSITIONS = {
        InvoiceStatus.DRAFT:     {InvoiceStatus.SENT, InvoiceStatus.CANCELLED},
        InvoiceStatus.SENT:      {InvoiceStatus.PAID, InvoiceStatus.OVERDUE, InvoiceStatus.CANCELLED},
        InvoiceStatus.OVERDUE:   {InvoiceStatus.PAID, InvoiceStatus.CANCELLED},
        InvoiceStatus.PAID:      set(),   # estado terminal
        InvoiceStatus.CANCELLED: set(),   # estado terminal
    }

    class Meta:
        # '-id' como desempate garante ordem total e estável na paginação:
        # sem ele, faturas de mesma data têm ordem indefinida e podem repetir
        # ou sumir entre páginas.
        ordering = ['-issue_date', '-id']
        unique_together = [['tenant', 'number']]
        verbose_name = 'Fatura'
        verbose_name_plural = 'Faturas'

    def __str__(self):
        return f'Fatura #{self.number} — {self.client.name}'

    @property
    def total(self):
        return sum(item.total for item in self.items.all()) or Decimal('0.00')

    @property
    def is_past_due(self):
        """
        Predicado de DATA: a fatura passou do vencimento sem ter sido quitada
        ou cancelada. É o gatilho que promove a fatura ao estado 'Vencida' —
        não é o estado em si. O estado de ciclo de vida é sempre `status`.
        """
        terminal = {InvoiceStatus.PAID, InvoiceStatus.CANCELLED}
        return self.due_date < date.today() and self.status not in terminal

    def can_transition_to(self, new_status):
        """Indica se a transição para `new_status` é permitida a partir do estado atual."""
        return new_status in self.ALLOWED_TRANSITIONS.get(self.status, set())

    def _transition_to(self, new_status):
        """
        Aplica uma transição de status validando a máquina de estados.

        Levanta InvalidInvoiceTransition se a transição for ilegal. Persiste
        apenas os campos afetados para evitar sobrescrever escritas concorrentes.
        """
        if not self.can_transition_to(new_status):
            raise InvalidInvoiceTransition(
                f"Não é possível mudar a fatura de "
                f"'{self.get_status_display()}' para "
                f"'{InvoiceStatus(new_status).label}'."
            )
        self.status = new_status
        self.save(update_fields=['status', 'updated_at'])

    def mark_as_sent(self):
        self._transition_to(InvoiceStatus.SENT)

    def mark_as_paid(self):
        self._transition_to(InvoiceStatus.PAID)

    def mark_as_overdue(self):
        self._transition_to(InvoiceStatus.OVERDUE)

    def cancel(self):
        self._transition_to(InvoiceStatus.CANCELLED)


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
