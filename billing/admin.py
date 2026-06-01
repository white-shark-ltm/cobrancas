"""Admin para Invoice, InvoiceItem e Payment."""

from django.contrib import admin

from billing.models import Invoice, InvoiceItem, Payment


class InvoiceItemInline(admin.TabularInline):
    model = InvoiceItem
    extra = 1
    fields = ('description', 'quantity', 'unit_price')
    readonly_fields = ('tenant',)

    def get_queryset(self, request):
        return InvoiceItem.all_objects.all()


class PaymentInline(admin.TabularInline):
    model = Payment
    extra = 0
    fields = ('amount', 'method', 'paid_at', 'notes')
    readonly_fields = ('tenant',)

    def get_queryset(self, request):
        return Payment.all_objects.all()


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ('number', 'client', 'project', 'status', 'issue_date', 'due_date', 'total', 'is_overdue', 'tenant')
    list_filter = ('status', 'tenant')
    search_fields = ('number', 'client__name', 'project__name')
    readonly_fields = ('tenant', 'total', 'created_at', 'updated_at')
    date_hierarchy = 'issue_date'
    inlines = (InvoiceItemInline, PaymentInline)
    actions = ('mark_sent', 'mark_paid')

    def get_queryset(self, request):
        return Invoice.all_objects.select_related('client', 'project', 'tenant')

    @admin.display(boolean=True, description='Vencida?')
    def is_overdue(self, obj):
        return obj.is_overdue

    @admin.action(description='Marcar como Enviada')
    def mark_sent(self, request, queryset):
        for invoice in queryset:
            invoice.mark_as_sent()

    @admin.action(description='Marcar como Paga')
    def mark_paid(self, request, queryset):
        for invoice in queryset:
            invoice.mark_as_paid()


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('invoice', 'amount', 'method', 'paid_at', 'tenant')
    list_filter = ('method', 'tenant')
    search_fields = ('invoice__number', 'invoice__client__name')
    readonly_fields = ('tenant', 'created_at')

    def get_queryset(self, request):
        return Payment.all_objects.select_related('invoice', 'tenant')
