import { cpSync, mkdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = dirname(fileURLToPath(import.meta.url));
const output = join(root, "dist");
const apiBase = String(process.env.BACKEND_API_BASE_URL || "http://127.0.0.1:8000").replace(/\/$/, "");

rmSync(output, { recursive: true, force: true });
mkdirSync(output, { recursive: true });
cpSync(join(root, "static"), join(output, "static"), { recursive: true });
writeFileSync(join(output, "index.html"), readFileSync(join(root, "templates", "dashboard.html")));
writeFileSync(
  join(output, "config.js"),
  `window.RUNTIME_CONFIG = Object.freeze({ API_BASE_URL: ${JSON.stringify(apiBase)} });\n`,
);

console.log(`Built frontend for API ${apiBase}`);
