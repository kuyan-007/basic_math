// Build-time converter. The reader only needs a browser with native MathML.
const fs = require("node:fs");
const path = require("node:path");
const roots = [process.cwd(), __dirname];
let katex;
try {
  katex = require(require.resolve("katex", { paths: roots }));
} catch {
  const npmRoot = path.resolve(path.dirname(process.execPath), "../lib/node_modules");
  roots.push(npmRoot, path.join(npmRoot, "@mermaid-js/mermaid-cli"));
  katex = require(require.resolve("katex", { paths: roots }));
}
const expressions = JSON.parse(fs.readFileSync(0, "utf8"));
const rendered = expressions.map((expression) => {
  const result = katex.renderToString(expression, {
    output: "mathml", displayMode: true, throwOnError: true, trust: false,
  });
  return result.slice(result.indexOf("<math"), result.lastIndexOf("</math>") + 7);
});
process.stdout.write(JSON.stringify(rendered));
