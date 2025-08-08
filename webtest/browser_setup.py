from playwright.sync_api import sync_playwright

def browser_init(runnable_funct, headless=True):
    playwright = sync_playwright().start()
    browser = playwright.chromium.launch(headless=headless, args=["--start-maximized"], slow_mo=250)
    context = browser.new_context(no_viewport=True)
    page = context.new_page()
    try:
        runnable_funct(page)
    except Exception as e:
        print(f"error with function: {e}")
        raise
    page.wait_for_timeout(3000)
    browser.close()
    playwright.stop()