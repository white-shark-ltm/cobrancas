"""Admin para Client com filtro automático por tenant."""

from django.contrib import admin

from clients.models import Client


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'phone', 'document', 'active', 'tenant', 'created_at')
    list_filter = ('active', 'tenant')
    search_fields = ('name', 'email', 'document')
    readonly_fields = ('tenant', 'created_at')

    def get_queryset(self, request):
        # Admin usa all_objects para enxergar todos os tenants
        return Client.all_objects.all()
