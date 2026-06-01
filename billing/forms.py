from django import forms
from django.forms import inlineformset_factory

from .models import Invoice, InvoiceItem, Payment


class InvoiceItemForm(forms.ModelForm):
    class Meta:
        model = InvoiceItem
        fields = ['description', 'quantity', 'unit_price']


InvoiceItemFormSet = inlineformset_factory(
    Invoice,
    InvoiceItem,
    form=InvoiceItemForm,
    extra=0,
    can_delete=True,
    min_num=1,
    validate_min=True,
)


class PaymentForm(forms.ModelForm):
    class Meta:
        model = Payment
        fields = ['amount', 'method', 'paid_at', 'notes']
        widgets = {
            'paid_at': forms.DateInput(attrs={'type': 'date'}),
        }
