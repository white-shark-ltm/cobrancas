"""
Testes E2E do módulo de clientes com Playwright.

Cobre: autenticação, CRUD, busca, desativação e isolamento entre tenants.
O servidor deve estar rodando em http://127.0.0.1:8000 antes de executar.
"""

import re

import pytest
from playwright.sync_api import Page, expect

BASE = "http://127.0.0.1:8000"


def login(page: Page, username: str, password: str = "senha123"):
    page.goto(f"{BASE}/login/")
    page.fill('[name=username]', username)
    page.fill('[name=password]', password)
    page.click('[type=submit]')
    page.wait_for_url(f"{BASE}/clientes/")


# ---------------------------------------------------------------------------
# Autenticação
# ---------------------------------------------------------------------------

def test_login_sucesso(page: Page):
    login(page, "freelancer1")
    expect(page).to_have_url(f"{BASE}/clientes/")


def test_acesso_sem_login_redireciona(page: Page):
    page.goto(f"{BASE}/clientes/")
    # Playwright aceita string ou regex — não lambda
    expect(page).to_have_url(re.compile(r"/login/"))


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------

def test_criar_cliente(page: Page):
    login(page, "freelancer1")
    page.goto(f"{BASE}/clientes/novo/")
    page.fill('[name=name]', "Empresa Playwright")
    page.fill('[name=email]', "playwright@teste.com")
    page.fill('[name=phone]', "11999990000")
    page.click('[type=submit]')
    expect(page).to_have_url(f"{BASE}/clientes/")
    expect(page.locator("body")).to_contain_text("Empresa Playwright")


def test_criar_cliente_email_duplicado(page: Page):
    login(page, "freelancer1")
    # Garante que o cliente base existe
    page.goto(f"{BASE}/clientes/novo/")
    page.fill('[name=name]', "Base Para Duplicar")
    page.fill('[name=email]', "duplicado@teste.com")
    page.click('[type=submit]')
    page.wait_for_url(f"{BASE}/clientes/")

    # Tenta criar com o mesmo email
    page.goto(f"{BASE}/clientes/novo/")
    page.fill('[name=name]', "Outro Nome")
    page.fill('[name=email]', "duplicado@teste.com")
    page.click('[type=submit]')
    # Deve permanecer no form com mensagem de erro
    expect(page).to_have_url(f"{BASE}/clientes/novo/")
    expect(page.locator("body")).to_contain_text("Já existe")


def test_editar_cliente(page: Page):
    login(page, "freelancer1")
    # Cria cliente para editar
    page.goto(f"{BASE}/clientes/novo/")
    page.fill('[name=name]', "Para Editar Original")
    page.fill('[name=email]', "editar.original@teste.com")
    page.click('[type=submit]')
    page.wait_for_url(f"{BASE}/clientes/")

    # Encontra o link de edição — usa filter em vez de has_text_regex
    row = page.locator("tr", has_text="Para Editar Original")
    row.locator("a[href*='/editar/']").click()
    page.fill('[name=name]', "Nome Editado Com Sucesso")
    page.click('[type=submit]')
    expect(page).to_have_url(f"{BASE}/clientes/")
    expect(page.locator("body")).to_contain_text("Nome Editado Com Sucesso")


def test_detalhe_cliente(page: Page):
    login(page, "freelancer1")
    # Cria cliente para ver detalhe
    page.goto(f"{BASE}/clientes/novo/")
    page.fill('[name=name]', "Cliente Detalhe")
    page.fill('[name=email]', "detalhe@teste.com")
    page.click('[type=submit]')
    page.wait_for_url(f"{BASE}/clientes/")

    row = page.locator("tr", has_text="Cliente Detalhe")
    row.locator("a").first.click()
    expect(page.locator("body")).to_contain_text("Projetos")
    expect(page.locator("body")).to_contain_text("Faturas")


def test_desativar_cliente(page: Page):
    login(page, "freelancer1")
    page.goto(f"{BASE}/clientes/novo/")
    page.fill('[name=name]', "Para Desativar PW")
    page.fill('[name=email]', "desativar.pw@teste.com")
    page.click('[type=submit]')
    page.wait_for_url(f"{BASE}/clientes/")

    row = page.locator("tr", has_text="Para Desativar PW")
    page.on("dialog", lambda d: d.accept())
    row.locator("form button[type=submit]").click()
    page.wait_for_url(f"{BASE}/clientes/")
    # Cliente desativado deve aparecer com badge Inativo ou desaparecer
    body = page.locator("body").text_content()
    # Aceita ambos os estados: oculto da lista ativa ou marcado como inativo
    if "Para Desativar PW" in body:
        expect(page.locator("body")).to_contain_text("Inativo")


# ---------------------------------------------------------------------------
# Busca
# ---------------------------------------------------------------------------

def test_busca_por_nome(page: Page):
    login(page, "freelancer1")
    # Garante que existe um cliente com "Empresa" no nome
    page.goto(f"{BASE}/clientes/novo/")
    page.fill('[name=name]', "Empresa Busca Teste")
    page.fill('[name=email]', "busca.nome@teste.com")
    page.click('[type=submit]')
    page.wait_for_url(f"{BASE}/clientes/")

    page.goto(f"{BASE}/clientes/?q=Empresa+Busca")
    expect(page.locator("body")).to_contain_text("Empresa Busca Teste")


def test_busca_sem_resultado(page: Page):
    login(page, "freelancer1")
    page.goto(f"{BASE}/clientes/?q=xyznaoeexiste999abc")
    body = page.locator("body").text_content().lower()
    assert any(w in body for w in ["nenhum", "vazio", "não encontrado", "no client", "empty"])


# ---------------------------------------------------------------------------
# Isolamento de Tenant (crítico)
# ---------------------------------------------------------------------------

def test_isolamento_tenant(browser):
    # --- Tenant 1 cria um cliente secreto ---
    ctx1 = browser.new_context()
    p1 = ctx1.new_page()
    login(p1, "freelancer1")
    p1.goto(f"{BASE}/clientes/novo/")
    p1.fill('[name=name]', "Cliente Secreto T1")
    p1.fill('[name=email]', "secreto.t1.isolation@teste.com")
    p1.click('[type=submit]')
    p1.wait_for_url(f"{BASE}/clientes/")

    # Captura href do detalhe do cliente recém-criado
    row = p1.locator("tr", has_text="Cliente Secreto T1")
    href = row.locator("a").first.get_attribute("href")
    ctx1.close()

    # --- Tenant 2: sessão completamente separada ---
    ctx2 = browser.new_context()
    p2 = ctx2.new_page()
    login(p2, "freelancer2")

    # Listagem não deve conter dados do tenant1
    p2.goto(f"{BASE}/clientes/")
    assert "Cliente Secreto T1" not in p2.content(), \
        "ISOLAMENTO FALHOU: tenant2 vê cliente do tenant1 na listagem"

    # Acesso direto ao PK do tenant1 deve retornar 404 ou redirecionar
    if href:
        p2.goto(f"{BASE}{href}")
        # Ou é 404, ou voltou para alguma lista — o que não deve ser é mostrar o cliente
        assert "Cliente Secreto T1" not in p2.content(), \
            f"ISOLAMENTO FALHOU: tenant2 conseguiu acessar {href} e ver dados do tenant1"

    ctx2.close()


# ---------------------------------------------------------------------------
# Validação de form
# ---------------------------------------------------------------------------

def test_form_vazio_exibe_erros(page: Page):
    login(page, "freelancer1")
    page.goto(f"{BASE}/clientes/novo/")
    page.click('[type=submit]')
    expect(page).to_have_url(f"{BASE}/clientes/novo/")
    body = page.locator("body").text_content().lower()
    assert any(w in body for w in ["obrigatório", "required", "este campo", "preencha"])


def test_email_invalido_exibe_erro(page: Page):
    login(page, "freelancer1")
    page.goto(f"{BASE}/clientes/novo/")
    page.fill('[name=name]', "Teste Validação")
    page.fill('[name=email]', "nao-e-um-email")
    page.click('[type=submit]')
    expect(page).to_have_url(f"{BASE}/clientes/novo/")
