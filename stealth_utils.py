import logging

async def apply_stealth_js(page):
    """
    Applies various JavaScript injections to make Playwright less detectable.
    """
    try:
        # Pass the User-Agent test (though Playwright usually handles this well)
        # user_agent = await page.evaluate("() => navigator.userAgent")
        # await page.set_extra_http_headers({'User-Agent': user_agent.replace("HeadlessChrome", "Chrome")}) # Example

        # Pass the WebGL test
        await page.add_init_script("(() => { const getParameter = WebGLRenderingContext.prototype.getParameter; WebGLRenderingContext.prototype.getParameter = function(parameter) { if (parameter === 37445) { return 'Intel Open Source Technology Center'; } if (parameter === 37446) { return 'Mesa DRI Intel(R) Ivybridge Mobile '; } return getParameter(parameter); }; })()")

        # Pass the Chrome test
        await page.add_init_script("(() => { Object.defineProperty(navigator, 'webdriver', { get: () => false }); })()")
        await page.add_init_script("(() => { window.chrome = { runtime: {}, loadTimes: function(){}, csi: function(){} }; })()")

        # Pass the Permissions test
        await page.add_init_script("(() => { const originalQuery = window.navigator.permissions.query; window.navigator.permissions.query = (parameters) => ( parameters.name === 'notifications' ? Promise.resolve({ state: Notification.permission }) : originalQuery(parameters) ); })()")

        # Pass the Plugins Length test
        await page.add_init_script("(() => { Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] }); })()")

        # Pass the Languages test
        await page.add_init_script("(() => { Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] }); })()")

        logging.info("Applied JavaScript stealth techniques from stealth_utils.")
    except Exception as e:
        logging.error(f"Error applying stealth JS from stealth_utils: {e}", exc_info=True)
