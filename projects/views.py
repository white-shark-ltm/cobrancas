from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from clients.models import Client

from .forms import ProjectForm
from .models import Project, ProjectStatus


class ProjectListView(LoginRequiredMixin, ListView):
    model = Project
    template_name = 'projects/list.html'
    context_object_name = 'projects'
    paginate_by = 20

    def get_queryset(self):
        qs = super().get_queryset().select_related('client')
        q = self.request.GET.get('q', '').strip()
        status = self.request.GET.get('status', '').strip()
        client_id = self.request.GET.get('client', '').strip()

        if q:
            qs = qs.filter(Q(name__icontains=q) | Q(description__icontains=q))
        if status:
            qs = qs.filter(status=status)
        if client_id:
            qs = qs.filter(client_id=client_id)

        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['clients'] = Client.objects.filter(active=True).order_by('name')
        ctx['status_choices'] = ProjectStatus.choices
        return ctx


class ProjectCreateView(LoginRequiredMixin, CreateView):
    model = Project
    form_class = ProjectForm
    template_name = 'projects/form.html'
    success_url = reverse_lazy('projects:list')


class ProjectUpdateView(LoginRequiredMixin, UpdateView):
    model = Project
    form_class = ProjectForm
    template_name = 'projects/form.html'
    success_url = reverse_lazy('projects:list')


class ProjectDetailView(LoginRequiredMixin, DetailView):
    model = Project
    template_name = 'projects/detail.html'
    context_object_name = 'project'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        invoices = list(
            self.object.invoices.prefetch_related('items', 'payments').order_by('-issue_date')
        )
        total_invoiced = sum(inv.total for inv in invoices)
        total_paid = sum(
            payment.amount
            for inv in invoices
            for payment in inv.payments.all()
        )
        ctx['invoices'] = invoices
        ctx['total_invoiced'] = total_invoiced
        ctx['total_paid'] = total_paid
        ctx['total_pending'] = total_invoiced - total_paid
        return ctx


class ProjectArchiveView(LoginRequiredMixin, View):
    def post(self, request, pk):
        project = get_object_or_404(Project, pk=pk)
        project.status = ProjectStatus.CANCELLED
        project.save()
        return redirect('projects:list')
