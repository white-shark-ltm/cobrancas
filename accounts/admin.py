"""Admin para User e ProfessionalProfile."""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from accounts.models import ProfessionalProfile, User


class ProfessionalProfileInline(admin.StackedInline):
    model = ProfessionalProfile
    can_delete = False
    fields = ('name', 'document', 'phone')


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    inlines = (ProfessionalProfileInline,)


@admin.register(ProfessionalProfile)
class ProfessionalProfileAdmin(admin.ModelAdmin):
    list_display = ('name', 'user', 'document', 'phone', 'created_at')
    search_fields = ('name', 'user__username', 'document')
    readonly_fields = ('created_at',)
