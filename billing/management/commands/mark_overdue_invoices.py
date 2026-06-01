"""
Materializa o estado 'Vencida' das faturas.

Promove para OVERDUE toda fatura ENVIADA cujo vencimento já passou. Mantém o
campo `status` como fonte única de verdade do ciclo de vida — pensado para ser
agendado (ex.: cron diário). Idempotente: rodar várias vezes não tem efeito
colateral, pois só toca faturas ainda em SENT.

Uso:
    python manage.py mark_overdue_invoices [--dry-run]
"""

from django.core.management.base import BaseCommand

from billing.models import Invoice, InvoiceStatus


class Command(BaseCommand):
    help = "Promove faturas Enviadas vencidas para o status Vencida."

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Apenas relata o que seria promovido, sem gravar.',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']

        # all_objects: a varredura é global a todos os tenants. Cada instância
        # já carrega seu tenant_id, então a transição persiste sem depender do
        # contexto de thread do middleware.
        candidates = Invoice.all_objects.filter(status=InvoiceStatus.SENT)

        promoted = 0
        for invoice in candidates:
            if not invoice.is_past_due:
                continue
            if dry_run:
                self.stdout.write(f"  [dry-run] #{invoice.number} venceu em {invoice.due_date}")
            else:
                invoice.mark_as_overdue()
            promoted += 1

        verb = "seria(m) promovida(s)" if dry_run else "promovida(s)"
        self.stdout.write(self.style.SUCCESS(f"{promoted} fatura(s) {verb} para Vencida."))
