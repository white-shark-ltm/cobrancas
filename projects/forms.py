"""
Forms do módulo de projetos.

Define ProjectForm com widgets estilizados com classes Tailwind CSS,
evitando o anti-padrão de envolver {{ form.field }} dentro de um <select>
manual no template (que gera HTML inválido com selects aninhados).
"""

from django import forms

from clients.models import Client

from .models import Project

SELECT_CLASSES = (
    "w-full px-3.5 py-2.5 text-sm "
    "text-slate-800 dark:text-zinc-100 "
    "bg-white dark:bg-zinc-900 "
    "border border-slate-300 dark:border-zinc-700 "
    "rounded-lg appearance-none outline-none transition-colors "
    "focus:border-blue-500 focus:ring-2 focus:ring-blue-100 dark:focus:ring-blue-500/20 "
    "bg-[url('data:image/svg+xml;charset=utf-8,%3Csvg xmlns=%22http://www.w3.org/2000/svg%22 "
    "fill=%22none%22 viewBox=%220 0 20 20%22%3E%3Cpath stroke=%22%236b7280%22 "
    "stroke-linecap=%22round%22 stroke-linejoin=%22round%22 stroke-width=%221.5%22 "
    "d=%22M6 8l4 4 4-4%22/%3E%3C/svg%3E')] "
    "bg-[position:right_0.75rem_center] bg-[size:1.25rem_1.25rem] bg-no-repeat pr-10"
)

INPUT_CLASSES = (
    "w-full px-3.5 py-2.5 text-sm "
    "text-slate-800 dark:text-zinc-100 "
    "bg-white dark:bg-zinc-900 "
    "border border-slate-300 dark:border-zinc-700 "
    "rounded-lg outline-none transition-colors "
    "placeholder:text-slate-400 dark:placeholder:text-zinc-500 "
    "focus:border-blue-500 focus:ring-2 focus:ring-blue-100 dark:focus:ring-blue-500/20"
)

TEXTAREA_CLASSES = INPUT_CLASSES + " resize-y"

DATE_CLASSES = (
    "w-full px-3.5 py-2.5 text-sm "
    "text-slate-800 dark:text-zinc-100 "
    "bg-white dark:bg-zinc-900 "
    "border border-slate-300 dark:border-zinc-700 "
    "rounded-lg outline-none transition-colors "
    "dark:[color-scheme:dark] "
    "focus:border-blue-500 focus:ring-2 focus:ring-blue-100 dark:focus:ring-blue-500/20"
)


class ProjectForm(forms.ModelForm):
    """Form de criação/edição de projetos com widgets estilizados."""

    class Meta:
        model = Project
        fields = [
            'client', 'name', 'description', 'status',
            'rate', 'rate_type', 'started_at', 'deadline',
        ]
        widgets = {
            'client': forms.Select(attrs={'class': SELECT_CLASSES}),
            'name': forms.TextInput(attrs={
                'class': INPUT_CLASSES,
                'placeholder': 'Nome do projeto',
            }),
            'description': forms.Textarea(attrs={
                'class': TEXTAREA_CLASSES,
                'rows': 4,
                'placeholder': 'Descreva o escopo, objetivos e entregas do projeto...',
            }),
            'status': forms.Select(attrs={'class': SELECT_CLASSES}),
            'rate': forms.NumberInput(attrs={
                'class': INPUT_CLASSES + " pl-9",
                'step': '0.01',
                'min': '0',
                'placeholder': '0,00',
            }),
            'rate_type': forms.Select(attrs={'class': SELECT_CLASSES}),
            'started_at': forms.DateInput(
                attrs={'class': DATE_CLASSES, 'type': 'date'},
                format='%Y-%m-%d',
            ),
            'deadline': forms.DateInput(
                attrs={'class': DATE_CLASSES, 'type': 'date'},
                format='%Y-%m-%d',
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['client'].queryset = Client.objects.filter(active=True).order_by('name')
        self.fields['client'].empty_label = '---------'
