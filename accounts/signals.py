"""
Signals do app accounts.

Garante que todo User criado receba automaticamente um ProfessionalProfile,
mantendo a invariante de que user.profile sempre existe.
"""

from django.db.models.signals import post_save
from django.dispatch import receiver


@receiver(post_save, sender='accounts.User')
def create_profile_for_new_user(sender, instance, created, **kwargs):
    """Cria ProfessionalProfile quando um User é criado pela primeira vez."""
    if created:
        from accounts.models import ProfessionalProfile
        ProfessionalProfile.objects.create(
            user=instance,
            name=instance.get_full_name() or instance.username,
        )
