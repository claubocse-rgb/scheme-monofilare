"""Comun pentru testele cu browser: Condițiile de participare la testare (static/beta.html) se acceptă la prima intrare
în aplicație (`sm.acord_beta`). Testele care nu verifică dialogul pornesc cu ele acceptate; tests/test_ui_e2.py
folosește contextul original (`Browser._sm_new_context_orig`) ca să vadă dialogul."""
import pytest

ACORD_BETA = "try { if (!localStorage.getItem('sm.acord_beta')) localStorage.setItem('sm.acord_beta', JSON.stringify({versiune:'0.1', la:'test'})); } catch (e) {}"


@pytest.fixture(autouse=True, scope="session")
def _acord_beta_implicit():
    try:
        from playwright.sync_api import Browser
    except Exception:
        yield
        return
    if not hasattr(Browser, "_sm_new_context_orig"):
        orig = Browser.new_context

        def new_context(self, *a, **k):
            c = orig(self, *a, **k)
            c.add_init_script(ACORD_BETA)
            return c
        orig_pg = Browser.new_page

        def new_page(self, *a, **k):
            pg = orig_pg(self, *a, **k)
            pg.add_init_script(ACORD_BETA)
            return pg
        Browser._sm_new_context_orig = orig
        Browser.new_context = new_context
        Browser.new_page = new_page
    yield
