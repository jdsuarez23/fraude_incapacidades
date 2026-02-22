from playwright.sync_api import sync_playwright

def test_adres2():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        try:
            print("Navegando a ADRES ifame...")
            page.goto("https://aplicaciones.adres.gov.co/BDUA_Internet/Pages/ConsultarAfiliadoWeb_2.aspx", timeout=30000)
            page.wait_for_load_state("networkidle")
            
            with open("test/adres_page2.html", "w", encoding="utf-8") as f:
                f.write(page.content())
            print("Guardado en adres_page2.html")
        except Exception as e:
            print(f"Error: {e}")
        finally:
            browser.close()

if __name__ == "__main__":
    test_adres2()
