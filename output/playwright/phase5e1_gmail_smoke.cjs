const fs = require('fs');
const path = require('path');
const os = require('os');
const { chromium } = require('playwright');

async function main() {
  const rootDir = process.cwd();
  const extensionDir = path.join(rootDir, 'chrome-extension');
  const outputDir = path.join(rootDir, 'output', 'playwright');
  const resultPath = path.join(outputDir, 'phase5e1_gmail_smoke_result.json');
  const screenshotPath = path.join(outputDir, 'phase5e1_gmail_smoke.png');

  const userDataDir = fs.mkdtempSync(path.join(os.tmpdir(), 'recall-phase5e1-profile-'));

  const htmlFixture = `<!doctype html>
<html>
  <head><meta charset="utf-8"><title>Inbox - Gmail</title></head>
  <body>
    <main>
      <div id="message-shell">
        <div gh="tm" id="toolbar-primary"></div>
        <h2 class="hP">Solutions Engineer Interview Follow-up</h2>
        <h3><span email="recruiter@openai.com" name="Jane Recruiter">Jane Recruiter</span></h3>
        <div class="a3s aiL">Thanks for your time today. Please review the role packet before next steps.</div>
        <span class="aV3">role-packet.pdf</span>
      </div>
    </main>
  </body>
</html>`;

  const result = {
    success: false,
    buttonInjected: false,
    prefillSaved: false,
    group: null,
    tags: [],
    reinjectedAfterDomMutation: false,
    error: null,
  };

  let context;

  async function getServiceWorker(browserContext) {
    const existing = browserContext.serviceWorkers();
    if (existing.length > 0) {
      return existing[0];
    }
    return await browserContext.waitForEvent('serviceworker', { timeout: 15000 });
  }

  async function getExtensionStorageValue(browserContext, key) {
    const worker = await getServiceWorker(browserContext);
    return await worker.evaluate(async (storageKey) => {
      return await new Promise((resolve) => {
        chrome.storage.local.get([storageKey], (items) => {
          resolve(items[storageKey] || null);
        });
      });
    }, key);
  }
  try {
    context = await chromium.launchPersistentContext(userDataDir, {
      headless: false,
      args: [
        `--disable-extensions-except=${extensionDir}`,
        `--load-extension=${extensionDir}`,
      ],
    });

    await context.route('https://mail.google.com/**', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'text/html',
        body: htmlFixture,
      });
    });

    const page = await context.newPage();
    await page.goto('https://mail.google.com/mail/u/0/#inbox/test-message', { waitUntil: 'domcontentloaded' });

    await page.waitForSelector('[data-recall-gmail-button]', { timeout: 15000 });
    result.buttonInjected = true;

    await page.click('[data-recall-gmail-button]');

    let prefill = null;
    for (let i = 0; i < 30; i += 1) {
      prefill = await getExtensionStorageValue(context, 'recall_gmail_prefill');
      if (prefill) {
        break;
      }
      await page.waitForTimeout(100);
    }

    result.prefillSaved = Boolean(prefill);
    result.group = prefill?.group || null;
    result.tags = Array.isArray(prefill?.tags) ? prefill.tags : [];

    await page.evaluate(() => {
      const oldToolbar = document.querySelector('#toolbar-primary');
      if (oldToolbar) {
        oldToolbar.remove();
      }
      const replacement = document.createElement('div');
      replacement.setAttribute('gh', 'tm');
      replacement.id = 'toolbar-replacement';
      document.querySelector('#message-shell')?.appendChild(replacement);
    });

    await page.waitForSelector('#toolbar-replacement [data-recall-gmail-button]', { timeout: 15000 });
    result.reinjectedAfterDomMutation = true;

    await page.screenshot({ path: screenshotPath, fullPage: true });

    result.success =
      result.buttonInjected &&
      result.prefillSaved &&
      result.reinjectedAfterDomMutation &&
      result.group === 'job-search' &&
      result.tags.includes('openai');
  } catch (error) {
    result.error = String(error && error.message ? error.message : error);
  } finally {
    if (context) {
      await context.close();
    }
    fs.rmSync(userDataDir, { recursive: true, force: true });
  }

  fs.writeFileSync(resultPath, `${JSON.stringify(result, null, 2)}\n`, 'utf8');
  console.log(JSON.stringify(result, null, 2));

  if (!result.success) {
    process.exitCode = 1;
  }
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
