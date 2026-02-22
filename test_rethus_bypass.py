from playwright.sync_api import sync_playwright

def test_rethus():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        try:
            page.goto("https://web.sispro.gov.co/THS/Cliente/ConsultasPublicas/ConsultaPublicaDeTHxIdentificacion.aspx", timeout=30000)
            page.wait_for_selector("body")
            
            # Read captcha value from javascript variable `tc`
            captcha_val = page.evaluate("window.tc")
            print(f"CAPTCHA value bypassed: {captcha_val}")
            
            # Fill form
            page.select_option("select#ctl00_cntContenido_ddlTipoIdentificacion", "CC")
            page.fill("input#ctl00_cntContenido_txtNumeroIdentificacion", "12345678") # Fake ID
            page.fill("input#ctl00_cntContenido_txtCatpchaConfirmation", str(captcha_val))
            
            # Submit
            page.click("input#ctl00_cntContenido_btnVerificarIdentificacion")
            
            # Wait for results panel or error
            try:
                page.wait_for_selector("div#ctl00_cntContenido_UpdatePanelResultado, span#ctl00_cntContenido_cvlValCaptcha", timeout=10000)
                print("Resultados cargados:")
                # Let's extract all text from the result div
                result_text = page.inner_text("div#ctl00_cntContenido_UpdatePanelResultado")
                print(result_text)
            except Exception as e:
                print("Error esperando resultados:", e)
                
        except Exception as e:
            print(f"Error: {e}")
        finally:
            browser.close()

if __name__ == "__main__":
    test_rethus()
