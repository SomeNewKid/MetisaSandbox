const { chromium } = require("playwright");

const port = 3000;
const wsPath = "/metisa-browser";

async function main() {
    if (process.argv.includes("--healthcheck")) {
        const browser = await chromium.connect(
            `ws://127.0.0.1:${port}${wsPath}`,
            { timeout: 3000 },
        );
        await browser.close();
        return;
    }

    const options = {
        host: "0.0.0.0",
        port,
        wsPath,
        headless: true,
        chromiumSandbox: true,
        timeout: 30000,
    };

    if (process.env.HTTPS_PROXY) {
        options.proxy = { server: process.env.HTTPS_PROXY };
    }

    const server = await chromium.launchServer(options);
    server.on("close", () => {
        process.exitCode = 1;
    });
}

main().catch((error) => {
    console.error(error);
    process.exitCode = 1;
});