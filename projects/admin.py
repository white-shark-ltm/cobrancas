"""Admin para Project."""

from django.contrib import admin

from projects.models import Project


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ('name', 'client', 'status', 'rate_type', 'rate', 'deadline', 'is_overdue', 'tenant')
    list_filter = ('status', 'rate_type', 'tenant')
    search_fields = ('name', 'client__name')
    readonly_fields = ('tenant', 'created_at', 'updated_at')
    date_hierarchy = 'created_at'

    def get_queryset(self, request):
        return Project.all_objects.select_related('client', 'tenant')

    @admin.display(boolean=True, description='Atrasado?')
    def is_overdue(self, obj):
        return obj.is_overdue
