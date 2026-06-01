"""
Forms do módulo de clientes.

ClientForm adiciona validação de unicidade de email por tenant no nível do
form, evitando IntegrityError ao submeter um email já cadastrado.
"""

from django import forms

from accounts.middleware import get_current_tenant
from clients.models import Client


class ClientForm(forms.ModelForm):
    class Meta:
        model = Client
        fields = ['name', 'email', 'phone', 'document', 'notes']

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email:
            tenant = get_current_tenant()
            if tenant:
                qs = Client.all_objects.filter(tenant=tenant, email=email)
                if self.instance.pk:
                    qs = qs.exclude(pk=self.instance.pk)
                if qs.exists():
                    raise forms.ValidationError(
                        "Já existe um cliente com este email cadastrado."
                    )
        return email


class ClientUpdateForm(ClientForm):
    class Meta(ClientForm.Meta):
        fields = ['name', 'email', 'phone', 'document', 'notes', 'active']
