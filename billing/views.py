from datetime import date
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import IntegrityError, transaction
from django.db.models import Q, Sum
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from clients.models import Client
from projects.models import Project

from .forms import InvoiceItemFormSet, PaymentForm
from .models import (
    InvalidInvoiceTransition,
    Invoice,
    InvoiceItem,
    InvoiceStatus,
    Payment,
)


def _next_invoice_number(tenant):
    year = date.today().year
    last = (
        Invoice.all_objects
        .filter(tenant=tenant, number__startswith=f"{year}-")
        .order_by('-number')
        .values_list('number', flat=True)
        .first()
    )
    seq = 1
    if last:
        try:
            seq = int(last.split('-')[1]) + 1
        except (IndexError, ValueError):
            pass
    return f"{year}-{seq:03d}"


class InvoiceListView(LoginRequiredMixin, ListView):
    model = Invoice
    template_name = 'billing/list.html'
    context_object_name = 'invoices'
    paginate_by = 20

    def get_queryset(self):
        qs = super().get_queryset().select_related('client', 'project')
        q = self.request.GET.get('q', '').strip()
        status = self.request.GET.get('status', '').strip()
        client_id = self.request.GET.get('client', '').strip()
        month = self.request.GET.get('month', '').strip()

        if q:
            qs = qs.filter(Q(number__icontains=q) | Q(client__name__icontains=q))
        if status:
            qs = qs.filter(status=status)
        if client_id:
            qs = qs.filter(client_id=client_id)
        if month:
            try:
                year, mon = month.split('-')
                qs = qs.filter(issue_date__year=int(year), issue_date__month=int(mon))
            except (ValueError, AttributeError):
                pass

        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['clients'] = Client.objects.filter(active=True).order_by('name')
        ctx['status_choices'] = InvoiceStatus.choices

        all_qs = Invoice.objects.prefetch_related('items')
        summary = {'total_draft': Decimal('0'), 'total_sent': Decimal('0'),
                   'total_paid': Decimal('0'), 'total_overdue': Decimal('0')}
        for inv in all_qs:
            t = inv.total
            if inv.status == InvoiceStatus.DRAFT:
                summary['total_draft'] += t
            elif inv.status == InvoiceStatus.SENT:
                summary['total_sent'] += t
            elif inv.status == InvoiceStatus.PAID:
                summary['total_paid'] += t
            elif inv.status == InvoiceStatus.OVERDUE:
                summary['total_overdue'] += t

        ctx['summary'] = summary
        return ctx


class InvoiceCreateView(LoginRequiredMixin, CreateView):
    model = Invoice
    fields = ['project', 'client', 'number', 'issue_date', 'due_date', 'notes']
    template_name = 'billing/form.html'

    def get_success_url(self):
        return reverse_lazy('billing:detail', kwargs={'pk': self.object.pk})

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.fields['project'].queryset = Project.objects.all().order_by('name')
        form.fields['client'].queryset = Client.objects.filter(active=True).order_by('name')
        form.fields['issue_date'].widget = __import__('django').forms.DateInput(
            attrs={'type': 'date'}, format='%Y-%m-%d')
        form.fields['issue_date'].input_formats = ['%Y-%m-%d']
        form.fields['due_date'].widget = __import__('django').forms.DateInput(
            attrs={'type': 'date'}, format='%Y-%m-%d')
        form.fields['due_date'].input_formats = ['%Y-%m-%d']
        # Número é opcional — gerado automaticamente se não for preenchido
        form.fields['number'].required = False
        form.fields['issue_date'].required = False

        project_pk = self.request.GET.get('project')
        if project_pk:
            try:
                form.fields['project'].initial = int(project_pk)
            except (ValueError, TypeError):
                pass

        return form

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        if self.request.POST:
            ctx['formset'] = InvoiceItemFormSet(self.request.POST)
        else:
            ctx['formset'] = InvoiceItemFormSet()
        return ctx

    # Quantas vezes regenerar o número auto ante colisão concorrente antes de desistir.
    MAX_NUMBER_ATTEMPTS = 5

    def post(self, request, *args, **kwargs):
        self.object = None
        form = self.get_form()
        formset = InvoiceItemFormSet(request.POST)

        if form.is_valid() and formset.is_valid():
            response = self._save(form, formset)
            if response is not None:
                return response

        return self.render_to_response(self.get_context_data(form=form))

    def _save(self, form, formset):
        """
        Persiste fatura + itens de forma atômica, resolvendo colisões de número.

        O número auto-gerado tem uma janela de corrida (dois POSTs leem o mesmo
        "último número"). Em vez de confiar na leitura, deixamos a constraint
        `unique_together(tenant, number)` ser a autoridade: ao colidir, a
        transação reverte e tentamos de novo com um número novo. Número informado
        manualmente pelo usuário não é regenerado — a colisão vira erro de campo.

        Retorna o redirect em caso de sucesso, ou None para re-renderizar o form.
        """
        from accounts.middleware import get_current_tenant

        invoice = form.save(commit=False)
        if not invoice.issue_date:
            invoice.issue_date = date.today()
        auto_number = not invoice.number

        for attempt in range(self.MAX_NUMBER_ATTEMPTS):
            if auto_number:
                invoice.number = _next_invoice_number(get_current_tenant())
            try:
                with transaction.atomic():
                    invoice.save()
                    formset.instance = invoice
                    formset.save()
            except IntegrityError:
                invoice.pk = None  # transação revertida: força novo INSERT
                if not auto_number:
                    form.add_error('number', 'Já existe uma fatura com este número.')
                    return None
                if attempt == self.MAX_NUMBER_ATTEMPTS - 1:
                    raise  # esgotou as tentativas: deixa o erro subir, não mascara
                continue
            self.object = invoice
            return redirect(self.get_success_url())


class InvoiceUpdateView(LoginRequiredMixin, UpdateView):
    model = Invoice
    fields = ['project', 'client', 'number', 'issue_date', 'due_date', 'notes']
    template_name = 'billing/form.html'

    def get_success_url(self):
        return reverse_lazy('billing:detail', kwargs={'pk': self.object.pk})

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        if self.object.status != InvoiceStatus.DRAFT:
            messages.error(request, "Somente faturas em Rascunho podem ser editadas.")
            return redirect('billing:detail', pk=self.object.pk)
        return super().get(request, *args, **kwargs)

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.fields['project'].queryset = Project.objects.all().order_by('name')
        form.fields['client'].queryset = Client.objects.filter(active=True).order_by('name')
        from django import forms as dj_forms
        form.fields['issue_date'].widget = dj_forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d')
        form.fields['issue_date'].input_formats = ['%Y-%m-%d']
        form.fields['due_date'].widget = dj_forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d')
        form.fields['due_date'].input_formats = ['%Y-%m-%d']
        # O número é um identificador imutável, atribuído na emissão. Campo
        # disabled: o Django ignora qualquer valor enviado e preserva o original,
        # impedindo renumeração acidental ou maliciosa via POST.
        form.fields['number'].disabled = True
        return form

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        if self.request.POST:
            ctx['formset'] = InvoiceItemFormSet(self.request.POST, instance=self.object)
        else:
            ctx['formset'] = InvoiceItemFormSet(instance=self.object)
        return ctx

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        if self.object.status != InvoiceStatus.DRAFT:
            messages.error(request, "Somente faturas em Rascunho podem ser editadas.")
            return redirect('billing:detail', pk=self.object.pk)

        form = self.get_form()
        formset = InvoiceItemFormSet(request.POST, instance=self.object)

        if form.is_valid() and formset.is_valid():
            with transaction.atomic():
                form.save()
                formset.save()
            return redirect(self.get_success_url())

        return self.render_to_response(self.get_context_data(form=form))


class InvoiceDetailView(LoginRequiredMixin, DetailView):
    model = Invoice
    template_name = 'billing/detail.html'
    context_object_name = 'invoice'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        items = self.object.items.all()
        payments = self.object.payments.all()
        total_paid = sum(p.amount for p in payments) or Decimal('0')
        ctx['items'] = items
        ctx['payments'] = payments
        ctx['total_paid'] = total_paid
        ctx['balance'] = self.object.total - total_paid
        ctx['payment_form'] = PaymentForm(initial={'paid_at': date.today()})
        return ctx


class InvoicePrintView(LoginRequiredMixin, DetailView):
    model = Invoice
    template_name = 'billing/print.html'
    context_object_name = 'invoice'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        payments = self.object.payments.all()
        ctx['items'] = self.object.items.all()
        ctx['payments'] = payments
        ctx['total_paid'] = sum(p.amount for p in payments) or Decimal('0')
        ctx['balance'] = self.object.total - ctx['total_paid']
        return ctx


class InvoiceStatusView(LoginRequiredMixin, View):
    # Mapeia a ação do formulário para o nome do método de transição do domínio.
    # A view não decide a regra — apenas despacha; o model valida e aplica.
    ACTIONS = {
        'send': 'mark_as_sent',
        'pay': 'mark_as_paid',
        'cancel': 'cancel',
    }

    def post(self, request, pk):
        invoice = get_object_or_404(Invoice, pk=pk)
        method_name = self.ACTIONS.get(request.POST.get('action'))

        if method_name is None:
            messages.error(request, "Ação inválida.")
            return redirect('billing:detail', pk=pk)

        try:
            getattr(invoice, method_name)()
        except InvalidInvoiceTransition as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, f"Fatura marcada como {invoice.get_status_display()}.")

        return redirect('billing:detail', pk=pk)


class PaymentCreateView(LoginRequiredMixin, View):
    # Estados em que uma fatura pode receber pagamento.
    PAYABLE_STATUSES = (InvoiceStatus.SENT, InvoiceStatus.OVERDUE)

    def post(self, request, invoice_pk):
        invoice = get_object_or_404(Invoice, pk=invoice_pk)

        # Invariante de negócio: só faturas cobráveis aceitam pagamento.
        # Bloqueia rascunhos, faturas pagas e canceladas, mesmo via POST direto.
        if invoice.status not in self.PAYABLE_STATUSES:
            messages.error(
                request,
                "Pagamentos só podem ser registrados em faturas Enviadas ou Vencidas.",
            )
            return redirect('billing:detail', pk=invoice_pk)

        form = PaymentForm(request.POST)

        if form.is_valid():
            with transaction.atomic():
                payment = form.save(commit=False)
                payment.invoice = invoice
                payment.save()

                total_paid = sum(
                    p.amount for p in invoice.payments.all()
                ) or Decimal('0')
                # Quitação total promove a fatura a Paga. A transição é segura:
                # o guard acima garante origem em SENT/OVERDUE.
                if total_paid >= invoice.total:
                    invoice.mark_as_paid()

            messages.success(request, "Pagamento registrado com sucesso.")
        else:
            messages.error(request, "Erro ao registrar pagamento. Verifique os dados.")

        return redirect('billing:detail', pk=invoice_pk)
