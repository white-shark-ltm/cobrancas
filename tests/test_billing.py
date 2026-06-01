"""
Testes E2E do módulo de faturamento (billing) com Playwright.

Cobre: CRUD com formset, transições de status, pagamentos,
filtros, impressão e isolamento entre tenants.
O servidor deve estar rodando em http://127.0.0.1:8000 antes de executar.
"""

import re
import uuid

import pytest
from playwright.sync_api import Page, expect

BASE = "http://127.0.0.1:8000"
BILLING_LIST = f"{BASE}/faturas/"
BILLING_NEW = f"{BASE}/faturas/nova/"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def login(page: Page, username: str, password: str = "senha123"):
    page.goto(f"{BASE}/login/")
    page.fill('[name=username]', username)
    page.fill('[name=password]', password)
    page.click('[type=submit]')
    page.wait_for_url(re.compile(r"(?!/login/)"))


def logout(page: Page):
    page.goto(f"{BASE}/logout/")


def uid() -> str:
    return uuid.uuid4().hex[:8]


def _get_select_first_real_option(page: Page, selector: str) -> str:
    """Returns the value of the first non-empty option of a select element."""
    options = page.locator(f"{selector} option")
    count = options.count()
    for i in range(count):
        val = options.nth(i).get_attribute("value") or ""
        if val.strip():
            return val
    return ""


def _get_all_real_options(page: Page, selector: str) -> list:
    """Returns list of (value, text) for all non-empty options."""
    options = page.locator(f"{selector} option")
    count = options.count()
    result = []
    for i in range(count):
        val = options.nth(i).get_attribute("value") or ""
        text = options.nth(i).text_content().strip()
        if val.strip():
            result.append((val, text))
    return result


def create_invoice(
    page: Page,
    description: str = "Servico Teste",
    qty: str = "1",
    price: str = "1000",
    extra_items: list = None,
    due_date: str = "2026-12-31",
    notes: str = "",
    number: str = "",
) -> str:
    """
    Cria uma fatura via formulário web com um item obrigatório.
    Retorna a URL do detalhe após salvar.

    extra_items: lista de dicts com keys 'description', 'qty', 'price' para
    itens adicionais (requer adicionar via JS addItem()).
    """
    page.goto(BILLING_NEW)

    # Seleciona projeto
    proj_val = _get_select_first_real_option(page, "#id_project")
    if not proj_val:
        raise RuntimeError("Nenhum projeto disponível no select do formulário de fatura")
    page.locator("#id_project").select_option(value=proj_val)

    # Seleciona cliente
    client_val = _get_select_first_real_option(page, "#id_client")
    if not client_val:
        raise RuntimeError("Nenhum cliente disponível no select do formulário de fatura")
    page.locator("#id_client").select_option(value=client_val)

    # Número (opcional — gerado automaticamente se vazio)
    if number:
        page.fill("#id_number", number)

    # Datas
    page.fill("#id_due_date", due_date)

    # Item 0
    page.fill("#id_items-0-description", description)
    page.fill("#id_items-0-quantity", qty)
    page.fill("#id_items-0-unit_price", price)

    # Itens adicionais via JS addItem()
    if extra_items:
        for idx, item in enumerate(extra_items, start=1):
            page.evaluate("addItem()")
            page.fill(f"#id_items-{idx}-description", item["description"])
            page.fill(f"#id_items-{idx}-quantity", item["qty"])
            page.fill(f"#id_items-{idx}-unit_price", item["price"])

    if notes:
        page.fill("#id_notes", notes)

    page.click('[type=submit]')
    # Aguarda redirecionamento para página de detalhe
    page.wait_for_url(re.compile(r"/faturas/\d+/"))
    return page.url


def _invoice_pk_from_url(url: str) -> str:
    m = re.search(r"/faturas/(\d+)/", url)
    return m.group(1) if m else ""


def _status_action(page: Page, invoice_pk: str, action: str):
    """POST direto na view de status. Contorna necessidade de botão visível."""
    page.goto(f"{BASE}/faturas/{invoice_pk}/")
    csrf = page.evaluate("() => document.cookie")
    csrf_match = re.search(r"csrftoken=([^;]+)", csrf)
    csrf_val = csrf_match.group(1) if csrf_match else ""
    resp = page.request.post(
        f"{BASE}/faturas/{invoice_pk}/status/",
        headers={
            "Referer": f"{BASE}/faturas/{invoice_pk}/",
            "X-CSRFToken": csrf_val,
        },
        form={"csrfmiddlewaretoken": csrf_val, "action": action},
    )
    page.goto(f"{BASE}/faturas/{invoice_pk}/")
    return resp


# ---------------------------------------------------------------------------
# CRUD e Formset
# ---------------------------------------------------------------------------

def test_create_invoice_with_items(page: Page):
    """Criar fatura com 2 itens: total deve ser R$ 2300,00."""
    login(page, "freelancer1")
    url = create_invoice(
        page,
        description="Desenvolvimento",
        qty="1",
        price="2000",
        extra_items=[{"description": "Revisão", "qty": "3", "price": "100"}],
        due_date="2026-12-31",
    )
    body = page.locator("body").text_content()
    # Total deve aparecer como 2300,00
    assert "2300" in body, f"Total 2300 não encontrado no detalhe. Trecho: {body[:500]}"


def test_create_invoice_without_due_date(page: Page):
    """Tentar criar fatura sem data de vencimento deve causar erro de validação."""
    login(page, "freelancer1")
    page.goto(BILLING_NEW)

    proj_val = _get_select_first_real_option(page, "#id_project")
    client_val = _get_select_first_real_option(page, "#id_client")
    if proj_val:
        page.locator("#id_project").select_option(value=proj_val)
    if client_val:
        page.locator("#id_client").select_option(value=client_val)

    # Deixa due_date em branco
    page.fill("#id_due_date", "")
    page.fill("#id_items-0-description", "Item Teste")
    page.fill("#id_items-0-quantity", "1")
    page.fill("#id_items-0-unit_price", "500")

    page.click('[type=submit]')

    # Deve permanecer no form ou exibir erro
    body = page.locator("body").text_content().lower()
    on_form = "/faturas/nova/" in page.url or "/faturas/nova" in page.url
    has_error = any(w in body for w in [
        "obrigatório", "required", "este campo", "preencha", "campo obrigatório",
        "não pode ser em branco", "fill in this field", "vencimento",
    ])
    assert on_form or has_error, (
        f"Esperava permanecer no form ou ver erro de due_date. URL: {page.url}"
    )


def test_edit_invoice_draft(page: Page):
    """Criar fatura DRAFT, editar as notas e verificar que foi salvo."""
    login(page, "freelancer1")
    url = create_invoice(page, description="Para Editar", qty="1", price="500")
    pk = _invoice_pk_from_url(url)

    page.goto(f"{BASE}/faturas/{pk}/editar/")
    page.fill("#id_notes", "Nota atualizada pelo teste")
    page.click('[type=submit]')

    page.wait_for_url(re.compile(r"/faturas/\d+/"))
    body = page.locator("body").text_content()
    assert "Nota atualizada pelo teste" in body, (
        "Nota editada não aparece no detalhe após salvar"
    )


def test_cannot_edit_sent_invoice(page: Page):
    """Fatura com status SENT não deve poder ser editada — deve redirecionar."""
    login(page, "freelancer1")
    url = create_invoice(page, description="Fatura Enviada", qty="1", price="800")
    pk = _invoice_pk_from_url(url)

    # Manda a fatura via POST direto
    _status_action(page, pk, "send")

    # Tenta acessar /editar/
    page.goto(f"{BASE}/faturas/{pk}/editar/")

    # Deve ter redirecionado para o detalhe
    assert "/editar/" not in page.url, (
        f"Fatura SENT ainda acessível em /editar/. URL atual: {page.url}"
    )
    # Mensagem de erro deve aparecer
    body = page.locator("body").text_content().lower()
    has_error_msg = any(w in body for w in [
        "rascunho", "editada", "somente", "apenas", "draft",
    ])
    assert has_error_msg, (
        f"Mensagem de bloqueio de edição não encontrada. Trecho: {body[:400]}"
    )


# ---------------------------------------------------------------------------
# Transições de Status
# ---------------------------------------------------------------------------

def test_invoice_send(page: Page):
    """DRAFT → clicar botão 'Enviar' → status deve virar SENT (Enviada)."""
    login(page, "freelancer1")
    url = create_invoice(page, description="Para Enviar", qty="1", price="1500")
    pk = _invoice_pk_from_url(url)

    # Aceita possível dialog de confirmação
    page.on("dialog", lambda d: d.accept())
    # Clica no botão Enviar (action=send) que aparece para DRAFT
    page.locator('form button[type=submit]', has_text="Enviar").click()
    page.wait_for_url(re.compile(r"/faturas/\d+/"))

    body = page.locator("body").text_content().lower()
    assert any(w in body for w in ["enviada", "sent"]), (
        f"Status 'Enviada' não encontrado após envio. Trecho: {body[:400]}"
    )


def test_invoice_cancel(page: Page):
    """DRAFT → cancelar → status deve virar Cancelada."""
    login(page, "freelancer1")
    url = create_invoice(page, description="Para Cancelar", qty="1", price="600")
    pk = _invoice_pk_from_url(url)

    # Aceita o dialog de confirmação de cancelamento
    page.on("dialog", lambda d: d.accept())
    page.locator('form button[type=submit]', has_text="Cancelar").click()
    page.wait_for_url(re.compile(r"/faturas/\d+/"))

    body = page.locator("body").text_content().lower()
    assert any(w in body for w in ["cancelada", "cancelled"]), (
        f"Status 'Cancelada' não encontrado. Trecho: {body[:400]}"
    )


def test_invoice_pay_via_status(page: Page):
    """SENT → marcar como PAID → status deve virar Paga."""
    login(page, "freelancer1")
    url = create_invoice(page, description="Para Pagar", qty="1", price="900")
    pk = _invoice_pk_from_url(url)

    # Primeiro envia
    _status_action(page, pk, "send")
    # Depois paga via POST direto (não há botão de 'pay' explícito para SENT no template)
    _status_action(page, pk, "pay")

    body = page.locator("body").text_content().lower()
    assert any(w in body for w in ["paga", "paid"]), (
        f"Status 'Paga' não encontrado após marcar como paga. Trecho: {body[:400]}"
    )


# ---------------------------------------------------------------------------
# Pagamentos
# ---------------------------------------------------------------------------

def _register_payment(page: Page, pk: str, amount: str, method: str = "pix"):
    """Abre o modal de pagamento e submete."""
    page.goto(f"{BASE}/faturas/{pk}/")
    # Abre o modal via JS
    page.evaluate("openPaymentModal()")
    page.wait_for_selector("#payment-modal:not(.hidden)", timeout=3000)
    page.fill("#id_amount", amount)
    page.locator("#id_method").select_option(value=method)
    page.fill("#id_paid_at", "2026-06-01")
    # Submete o formulário de pagamento
    page.locator("#payment-form button[type=submit]").click()
    page.wait_for_url(re.compile(r"/faturas/\d+/"))


def test_partial_payment(page: Page):
    """Fatura R$2000 → registrar R$500 → saldo devedor R$1500 visível."""
    login(page, "freelancer1")
    url = create_invoice(page, description="Parcial", qty="1", price="2000")
    pk = _invoice_pk_from_url(url)

    # Precisa estar em SENT para exibir botão de pagamento
    _status_action(page, pk, "send")
    _register_payment(page, pk, "500")

    body = page.locator("body").text_content()
    # Saldo devedor deve ser 1500
    assert "1500" in body, (
        f"Saldo devedor R$1500 não encontrado após pagamento parcial. Trecho: {body[:600]}"
    )
    # Status NÃO deve ser PAID
    body_lower = body.lower()
    # "paga" aparece em "Total Paga" e "R$ 500,00" — verificar que não está como badge "Paga"
    # Na página, o badge de status usa get_status_display: 'Enviada' ou 'Paga'
    assert "enviada" in body_lower or "sent" in body_lower, (
        f"Status deveria ser Enviada após pagamento parcial. Trecho: {body_lower[:400]}"
    )


def test_full_payment_changes_status(page: Page):
    """Fatura R$1000 → registrar R$1000 → status muda para PAID automaticamente."""
    login(page, "freelancer1")
    url = create_invoice(page, description="Pagamento Total", qty="1", price="1000")
    pk = _invoice_pk_from_url(url)

    _status_action(page, pk, "send")
    _register_payment(page, pk, "1000")

    body = page.locator("body").text_content().lower()
    assert any(w in body for w in ["paga", "paid"]), (
        f"Status não mudou para PAID após pagamento total. Trecho: {body[:400]}"
    )


# ---------------------------------------------------------------------------
# Invariantes da máquina de estados (POST direto, contornando a UI)
# ---------------------------------------------------------------------------

def _post_payment(page: Page, pk: str, amount: str = "100", method: str = "pix"):
    """POST direto na view de pagamento, sem depender do modal (que some em DRAFT)."""
    page.goto(f"{BASE}/faturas/{pk}/")
    csrf = page.evaluate("() => document.cookie")
    m = re.search(r"csrftoken=([^;]+)", csrf)
    csrf_val = m.group(1) if m else ""
    return page.request.post(
        f"{BASE}/faturas/{pk}/pagamento/",
        headers={"Referer": f"{BASE}/faturas/{pk}/", "X-CSRFToken": csrf_val},
        form={
            "csrfmiddlewaretoken": csrf_val,
            "amount": amount,
            "method": method,
            "paid_at": "2026-06-01",
        },
    )


def _status_of(page: Page, pk: str) -> str:
    """Lê o status atual da fatura pelo badge da página de detalhe."""
    page.goto(f"{BASE}/faturas/{pk}/")
    return page.locator("body").text_content().lower()


def test_payment_blocked_on_draft(page: Page):
    """BUG-001: pagamento em fatura DRAFT deve ser recusado e não mudar o status."""
    login(page, "freelancer1")
    url = create_invoice(page, description="Draft sem pagar", qty="1", price="1000")
    pk = _invoice_pk_from_url(url)

    _post_payment(page, pk, amount="1000")  # tenta pagar um rascunho

    body = _status_of(page, pk)
    # Status deve permanecer Rascunho — NÃO pode virar Paga
    assert "rascunho" in body, f"Fatura DRAFT mudou de status após pagamento indevido. Trecho: {body[:400]}"
    assert "registrado com sucesso" not in body, "Pagamento em DRAFT foi aceito indevidamente"


def test_payment_blocked_on_cancelled(page: Page):
    """BUG-001: pagamento em fatura CANCELADA deve ser recusado."""
    login(page, "freelancer1")
    url = create_invoice(page, description="Cancelada sem pagar", qty="1", price="500")
    pk = _invoice_pk_from_url(url)
    _status_action(page, pk, "cancel")

    _post_payment(page, pk, amount="500")

    body = _status_of(page, pk)
    assert "cancelada" in body, f"Fatura CANCELADA mudou de status após pagamento. Trecho: {body[:400]}"


def test_invalid_transition_cancelled_to_sent(page: Page):
    """BUG-002: fatura CANCELADA não pode ser 'reenviada' (ressuscitada)."""
    login(page, "freelancer1")
    url = create_invoice(page, description="Não ressuscita", qty="1", price="700")
    pk = _invoice_pk_from_url(url)
    _status_action(page, pk, "cancel")

    _status_action(page, pk, "send")  # transição ilegal

    body = _status_of(page, pk)
    assert "cancelada" in body, f"Fatura CANCELADA virou Enviada (transição ilegal). Trecho: {body[:400]}"


def test_invalid_transition_paid_to_cancelled(page: Page):
    """BUG-002: fatura PAGA não pode ser cancelada sem fluxo de estorno."""
    login(page, "freelancer1")
    url = create_invoice(page, description="Paga imutável", qty="1", price="800")
    pk = _invoice_pk_from_url(url)
    _status_action(page, pk, "send")
    _status_action(page, pk, "pay")

    _status_action(page, pk, "cancel")  # transição ilegal

    body = _status_of(page, pk)
    assert "paga" in body, f"Fatura PAGA foi cancelada (transição ilegal). Trecho: {body[:400]}"


def test_invalid_transition_draft_to_paid(page: Page):
    """BUG-002: não se marca um rascunho diretamente como pago via status."""
    login(page, "freelancer1")
    url = create_invoice(page, description="Draft direto pago", qty="1", price="400")
    pk = _invoice_pk_from_url(url)

    _status_action(page, pk, "pay")  # transição ilegal (draft -> paid)

    body = _status_of(page, pk)
    assert "rascunho" in body, f"Rascunho virou Pago direto (transição ilegal). Trecho: {body[:400]}"


def test_invoice_number_immutable_on_edit(page: Page):
    """BUG-004: o número da fatura não pode ser alterado na edição."""
    login(page, "freelancer1")
    url = create_invoice(page, description="Número fixo", qty="1", price="300")
    pk = _invoice_pk_from_url(url)

    page.goto(f"{BASE}/faturas/{pk}/")
    original_number = page.locator("h2.font-mono").first.text_content().strip().lstrip("#")

    # Campo deve renderizar como readonly e o salvamento deve preservar o número
    page.goto(f"{BASE}/faturas/{pk}/editar/")
    number_input = page.locator("#id_number")
    assert number_input.get_attribute("readonly") is not None, "Campo número não está readonly na edição"
    page.fill("#id_notes", "edicao sem mexer no numero")
    page.click('[type=submit]')
    page.wait_for_url(re.compile(r"/faturas/\d+/"))

    page.goto(f"{BASE}/faturas/{pk}/")
    final_number = page.locator("h2.font-mono").first.text_content().strip().lstrip("#")
    assert final_number == original_number, (
        f"Número da fatura mudou na edição: {original_number} -> {final_number}"
    )


def test_root_url_redirects(page: Page):
    """UX-002: a raiz '/' não deve mais retornar 404."""
    login(page, "freelancer1")
    resp = page.goto(f"{BASE}/")
    assert resp.status != 404, "Raiz '/' ainda retorna 404"
    assert "/faturas" in page.url or "/login" in page.url, f"Raiz não redirecionou para destino útil: {page.url}"


def test_duplicate_number_shows_form_error(page: Page):
    """Dívida-1: número duplicado deve virar erro de formulário, nunca 500."""
    login(page, "freelancer1")
    num = f"DUP-{uid()}"
    create_invoice(page, description="primeira", number=num)  # sucesso

    # Segunda fatura com o MESMO número
    page.goto(BILLING_NEW)
    page.locator("#id_project").select_option(value=_get_select_first_real_option(page, "#id_project"))
    page.locator("#id_client").select_option(value=_get_select_first_real_option(page, "#id_client"))
    page.fill("#id_number", num)
    page.fill("#id_due_date", "2026-12-31")
    page.fill("#id_items-0-description", "segunda")
    page.fill("#id_items-0-quantity", "1")
    page.fill("#id_items-0-unit_price", "100")
    page.click('[type=submit]')
    page.wait_for_timeout(1500)

    body = page.locator("body").text_content().lower()
    assert "/faturas/nova" in page.url, f"Deveria permanecer no form após colisão. URL: {page.url}"
    assert "já existe uma fatura com este número" in body, (
        f"Erro de número duplicado não exibido (possível 500?). Trecho: {body[:400]}"
    )


# ---------------------------------------------------------------------------
# Materialização do estado 'Vencida' (management command) — Dívida-2
# ---------------------------------------------------------------------------

def _run_mark_overdue():
    """Executa o command contra o MESMO banco usado pelo servidor vivo."""
    import os
    import subprocess
    import sys
    proj_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    subprocess.run(
        [sys.executable, "manage.py", "mark_overdue_invoices"],
        cwd=proj_dir, check=True, capture_output=True, text=True,
    )


def test_overdue_materialized_into_ui(page: Page):
    """
    Dívida-2: uma fatura ENVIADA já vencida só vira 'Vencida' (estado persistido)
    após o command de materialização — confirmando status como fonte única.
    """
    login(page, "freelancer1")
    url = create_invoice(page, description="Vai vencer", qty="1", price="100", due_date="2020-01-01")
    pk = _invoice_pk_from_url(url)
    _status_action(page, pk, "send")

    # Antes do command: estado persistido ainda é Enviada (não há verdade dupla)
    body_before = _status_of(page, pk)
    assert "enviada" in body_before, f"Esperava Enviada antes do command. Trecho: {body_before[:300]}"
    assert "vencida" not in body_before, "Status 'Vencida' apareceu sem o command rodar"

    _run_mark_overdue()

    # Depois: o badge de status reflete o estado materializado
    body_after = _status_of(page, pk)
    assert "vencida" in body_after, f"Fatura não virou Vencida após o command. Trecho: {body_after[:400]}"


def test_overdue_command_ignores_draft_and_future(page: Page):
    """Dívida-2: o command não promove rascunho vencido nem fatura a vencer."""
    login(page, "freelancer1")

    # Rascunho vencido — não é cobrável, não deve virar Vencida
    url_draft = create_invoice(page, description="Rascunho velho", qty="1", price="100", due_date="2020-01-01")
    pk_draft = _invoice_pk_from_url(url_draft)

    # Enviada a vencer no futuro — não deve virar Vencida
    url_future = create_invoice(page, description="Enviada futura", qty="1", price="100", due_date="2099-12-31")
    pk_future = _invoice_pk_from_url(url_future)
    _status_action(page, pk_future, "send")

    _run_mark_overdue()

    body_draft = _status_of(page, pk_draft)
    assert "rascunho" in body_draft, f"Rascunho vencido foi promovido. Trecho: {body_draft[:300]}"
    body_future = _status_of(page, pk_future)
    assert "enviada" in body_future, f"Fatura a vencer foi promovida. Trecho: {body_future[:300]}"


# ---------------------------------------------------------------------------
# Filtros
# ---------------------------------------------------------------------------

def test_filter_by_status(page: Page):
    """Criar faturas em status diferentes → filtrar por 'draft' → só rascunhos."""
    login(page, "freelancer1")

    desc_draft = f"Draft {uid()}"
    url_draft = create_invoice(page, description=desc_draft, qty="1", price="300")
    pk_draft = _invoice_pk_from_url(url_draft)

    desc_sent = f"Enviada {uid()}"
    url_sent = create_invoice(page, description=desc_sent, qty="1", price="400")
    pk_sent = _invoice_pk_from_url(url_sent)
    _status_action(page, pk_sent, "send")

    # Filtro por draft
    page.goto(f"{BILLING_LIST}?status=draft")
    content = page.content()
    # O número da fatura draft deve aparecer
    # (desc_draft pode não aparecer na listagem, mas o número sim)
    # Verificamos que fatura enviada não aparece na listagem filtrada por draft
    # Para isso, capturamos os números das faturas
    page.goto(f"{BASE}/faturas/{pk_draft}/")
    draft_number = page.locator("h2.font-mono, h2").first.text_content().strip().lstrip("#")
    page.goto(f"{BASE}/faturas/{pk_sent}/")
    sent_number = page.locator("h2.font-mono, h2").first.text_content().strip().lstrip("#")

    page.goto(f"{BILLING_LIST}?status=draft")
    content = page.content()
    assert draft_number in content, (
        f"Fatura draft #{draft_number} não aparece no filtro draft"
    )
    assert sent_number not in content, (
        f"Fatura sent #{sent_number} aparece no filtro draft"
    )


def test_filter_by_client(page: Page):
    """Criar faturas para clientes diferentes → filtrar por cliente → só do cliente."""
    login(page, "freelancer1")
    page.goto(BILLING_NEW)

    # Pega os dois primeiros clientes disponíveis
    opts = _get_all_real_options(page, "#id_client")
    if len(opts) < 2:
        pytest.skip("freelancer1 precisa de ao menos 2 clientes para este teste")

    pk_a, name_a = opts[0]
    pk_b, name_b = opts[1]

    # Fatura para cliente A
    page.goto(BILLING_NEW)
    proj_val = _get_select_first_real_option(page, "#id_project")
    page.locator("#id_project").select_option(value=proj_val)
    page.locator("#id_client").select_option(value=pk_a)
    page.fill("#id_due_date", "2026-12-31")
    page.fill("#id_items-0-description", f"Item A {uid()}")
    page.fill("#id_items-0-quantity", "1")
    page.fill("#id_items-0-unit_price", "100")
    page.click('[type=submit]')
    page.wait_for_url(re.compile(r"/faturas/\d+/"))
    inv_a_pk = _invoice_pk_from_url(page.url)

    # Fatura para cliente B
    page.goto(BILLING_NEW)
    proj_val = _get_select_first_real_option(page, "#id_project")
    page.locator("#id_project").select_option(value=proj_val)
    page.locator("#id_client").select_option(value=pk_b)
    page.fill("#id_due_date", "2026-12-31")
    page.fill("#id_items-0-description", f"Item B {uid()}")
    page.fill("#id_items-0-quantity", "1")
    page.fill("#id_items-0-unit_price", "200")
    page.click('[type=submit]')
    page.wait_for_url(re.compile(r"/faturas/\d+/"))
    inv_b_pk = _invoice_pk_from_url(page.url)

    # Captura números das faturas
    page.goto(f"{BASE}/faturas/{inv_a_pk}/")
    num_a = page.locator("h2.font-mono").first.text_content().strip().lstrip("#")
    page.goto(f"{BASE}/faturas/{inv_b_pk}/")
    num_b = page.locator("h2.font-mono").first.text_content().strip().lstrip("#")

    # Filtra por cliente A
    page.goto(f"{BILLING_LIST}?client={pk_a}")
    content = page.content()
    assert num_a in content, f"Fatura do cliente A não aparece no filtro"
    assert num_b not in content, f"Fatura do cliente B aparece no filtro do cliente A"


# ---------------------------------------------------------------------------
# Impressão
# ---------------------------------------------------------------------------

def test_print_view_no_sidebar(page: Page):
    """Página de impressão NÃO deve ter sidebar; dados da fatura devem estar presentes."""
    login(page, "freelancer1")
    url = create_invoice(page, description="Item Para Imprimir", qty="2", price="750")
    pk = _invoice_pk_from_url(url)

    page.goto(f"{BASE}/faturas/{pk}/imprimir/")
    content = page.content()
    body_text = page.locator("body").text_content().lower()

    # Sidebar típica tem id="sidebar" ou nav com links internos do app
    # A página de impressão usa um template próprio sem base.html
    has_sidebar = bool(
        page.locator("#sidebar").count() or
        page.locator("nav.sidebar").count()
    )
    assert not has_sidebar, "Sidebar encontrada na página de impressão"

    # Dados da fatura devem estar presentes
    assert "fatura" in body_text or "invoice" in body_text, (
        f"Palavra 'fatura' não encontrada na página de impressão"
    )


# ---------------------------------------------------------------------------
# Isolamento de Tenant (CRÍTICO)
# ---------------------------------------------------------------------------

def test_invoice_tenant_isolation(browser):
    """freelancer2 NÃO deve ver faturas do freelancer1 na listagem."""
    ctx1 = browser.new_context()
    p1 = ctx1.new_page()
    login(p1, "freelancer1")
    inv_url = create_invoice(p1, description="Fatura Secreta T1", qty="1", price="999")
    pk = _invoice_pk_from_url(inv_url)
    # Captura o número da fatura
    p1.goto(f"{BASE}/faturas/{pk}/")
    inv_number = p1.locator("h2.font-mono").first.text_content().strip().lstrip("#")
    ctx1.close()

    ctx2 = browser.new_context()
    p2 = ctx2.new_page()
    login(p2, "freelancer2")
    p2.goto(BILLING_LIST)
    content = p2.content()
    assert inv_number not in content, (
        f"ISOLAMENTO FALHOU: freelancer2 viu fatura #{inv_number} do tenant1"
    )
    ctx2.close()


def test_invoice_detail_404_cross_tenant(browser):
    """freelancer2 acessando detalhe de fatura do freelancer1 deve receber 404."""
    ctx1 = browser.new_context()
    p1 = ctx1.new_page()
    login(p1, "freelancer1")
    inv_url = create_invoice(p1, description="Cross Tenant Test", qty="1", price="777")
    pk = _invoice_pk_from_url(inv_url)
    ctx1.close()

    ctx2 = browser.new_context()
    p2 = ctx2.new_page()
    login(p2, "freelancer2")
    p2.goto(f"{BASE}/faturas/{pk}/")

    content = p2.content()
    # Não pode mostrar a fatura do tenant1
    assert "Cross Tenant Test" not in content, (
        f"ISOLAMENTO FALHOU: freelancer2 conseguiu acessar fatura {pk} do tenant1"
    )
    # Deve ser 404 ou redirect (fora da URL de detalhe esperada)
    is_404 = "404" in content or "Not Found" in content or "não encontrado" in content.lower()
    redirected_away = f"/faturas/{pk}/" not in p2.url or is_404
    assert redirected_away or is_404, (
        f"Acesso cross-tenant não bloqueado. URL atual: {p2.url}"
    )
    ctx2.close()


def test_payment_cross_tenant_blocked(browser):
    """freelancer2 fazendo POST em /faturas/{pk_f1}/pagamento/ deve receber 404."""
    ctx1 = browser.new_context()
    p1 = ctx1.new_page()
    login(p1, "freelancer1")
    inv_url = create_invoice(p1, description="Payment Block Test", qty="1", price="500")
    pk = _invoice_pk_from_url(inv_url)
    ctx1.close()

    ctx2 = browser.new_context()
    p2 = ctx2.new_page()
    login(p2, "freelancer2")
    p2.goto(BILLING_LIST)

    csrf = p2.evaluate("() => document.cookie")
    csrf_match = re.search(r"csrftoken=([^;]+)", csrf)
    csrf_val = csrf_match.group(1) if csrf_match else ""

    resp = p2.request.post(
        f"{BASE}/faturas/{pk}/pagamento/",
        headers={
            "Referer": BILLING_LIST,
            "X-CSRFToken": csrf_val,
        },
        form={
            "csrfmiddlewaretoken": csrf_val,
            "amount": "500",
            "method": "pix",
            "paid_at": "2026-06-01",
        },
    )
    assert resp.status in (404, 403), (
        f"Esperava 404 ou 403 no pagamento cross-tenant, recebeu {resp.status}"
    )
    ctx2.close()


def test_form_selects_isolation(browser):
    """No form de nova fatura, freelancer2 não deve ver dados do freelancer1."""
    # Captura nomes de clientes e projetos do freelancer1
    ctx1 = browser.new_context()
    p1 = ctx1.new_page()
    login(p1, "freelancer1")
    p1.goto(BILLING_NEW)

    f1_clients = [text for _, text in _get_all_real_options(p1, "#id_client")]
    f1_projects = [text for _, text in _get_all_real_options(p1, "#id_project")]
    ctx1.close()

    assert f1_clients, "freelancer1 não tem clientes no select — verifique o setup"
    assert f1_projects, "freelancer1 não tem projetos no select — verifique o setup"

    # Verifica que nenhum dado do f1 aparece no form do f2
    ctx2 = browser.new_context()
    p2 = ctx2.new_page()
    login(p2, "freelancer2")
    p2.goto(BILLING_NEW)

    client_html = p2.locator("#id_client").inner_html()
    project_html = p2.locator("#id_project").inner_html()

    for name in f1_clients:
        assert name not in client_html, (
            f"ISOLAMENTO FALHOU: cliente '{name}' do freelancer1 aparece no select do freelancer2"
        )
    for name in f1_projects:
        assert name not in project_html, (
            f"ISOLAMENTO FALHOU: projeto '{name}' do freelancer1 aparece no select do freelancer2"
        )
    ctx2.close()
