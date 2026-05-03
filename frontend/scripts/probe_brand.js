// Probe key chrome computed styles + screenshots after the LC brand
// alignment pass. Requires the frontend to be running on :3080.
const puppeteer = require('puppeteer');
const path = require('path');

(async () => {
  const browser = await puppeteer.launch({
    headless: 'new',
    args: ['--no-sandbox'],
  });
  const page = await browser.newPage();
  await page.setViewport({ width: 1440, height: 900, deviceScaleFactor: 1 });

  const url = 'http://127.0.0.1:3080/login';
  await page.goto(url, { waitUntil: 'networkidle0', timeout: 30000 });

  const styles = await page.evaluate(() => {
    function pick(el, props) {
      if (!el) return null;
      const cs = getComputedStyle(el);
      return Object.fromEntries(props.map((p) => [p, cs.getPropertyValue(p)]));
    }
    return {
      product: pick(
        document.querySelector('.login-editorial__product'),
        ['font-family', 'font-size', 'font-weight', 'letter-spacing', 'text-transform', 'color']
      ),
      rule: pick(
        document.querySelector('.login-editorial__rule'),
        ['width', 'height', 'background-color']
      ),
      sso: pick(
        document.querySelector('.login-sso'),
        ['background-color', 'color', 'border-color', 'border-width']
      ),
      headline: pick(
        document.querySelector('.login-editorial__headline'),
        ['font-family', 'font-size', 'font-weight']
      ),
      brandMarkBg: pick(
        document.querySelector('.login-brand span[role="img"]'),
        ['background-color', 'width', 'height']
      ),
    };
  });
  console.log('LOGIN STYLES:', JSON.stringify(styles, null, 2));

  await page.screenshot({
    path: path.join(__dirname, 'probe_login.png'),
    fullPage: false,
  });

  // Favicon check — fetch the SVG and the PNG, log their first bytes.
  const svg = await page.evaluate(() =>
    fetch('/icon.svg').then((r) => r.text())
  );
  console.log('FAVICON SVG SNIPPET:', svg.slice(0, 200));

  await browser.close();
})().catch((e) => {
  console.error(e);
  process.exit(1);
});
