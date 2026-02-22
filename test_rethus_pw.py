from playwright.sync_api import sync_playwright
import time

def test_rethus(tipo, doc):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        # Using a mobile user-agent or standard Windows user-agent
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        try:
            print("Navegando a SISPRO...")
            page.goto("https://web.sispro.gov.co/THS/Cliente/ConsultasPublicas/ConsultaPublicaDeTHxIdentificacion.aspx", timeout=30000)
            
            # Select document type
            print("Llenando formulario...")
            # We need to find the correct selectors. Let's wait for body
            page.wait_for_selector("body", timeout=10000)
            
            # Print page content to see selectors
            with open("test/rethus_page.html", "w", encoding="utf-8") as f:
                f.write(page.content())
            
            print("HTML guardado. Saliendo.")
        except Exception as e:
            print(f"Error: {e}")
        finally:
            browser.close()

if __name__ == "__main__":
    import os
    os.makedirs("test", exist_ok=True)
    test_rethus("1", "987654321")
