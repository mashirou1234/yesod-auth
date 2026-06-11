import { copyFile, mkdir, stat } from "node:fs/promises";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = dirname(dirname(fileURLToPath(import.meta.url)));
const files = [
  ["node_modules/driver.js/dist/driver.js.iife.js", "static/tour/vendor/driver.js"],
  ["node_modules/driver.js/dist/driver.css", "static/tour/vendor/driver.css"],
  ["node_modules/driver.js/license", "static/tour/vendor/driver.LICENSE"],
  ["tour/admin-tour.js", "static/tour/admin-tour.js"],
  ["tour/admin-tour.css", "static/tour/admin-tour.css"],
];

for (const [source, destination] of files) {
  const sourcePath = join(root, source);
  const destinationPath = join(root, destination);
  await stat(sourcePath);
  await mkdir(dirname(destinationPath), { recursive: true });
  await copyFile(sourcePath, destinationPath);
  console.log(`${source} -> ${destination}`);
}
