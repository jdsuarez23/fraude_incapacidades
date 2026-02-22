from playwright.sync_api import sync_playwright

def test_adres():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        try:
            page.goto("https://servicios.adres.gov.co/BDUA/Consulta-Afiliados-BDUA", timeout=30000)
            page.wait_for_load_state("networkidle")
            
            with open("test/adres_page.html", "w", encoding="utf-8") as f:
                f.write(page.content())
            
        except Exception as e:
            print(f"Error: {e}")
        finally:
            browser.close()

if __name__ == "__main__":
    test_adres()
