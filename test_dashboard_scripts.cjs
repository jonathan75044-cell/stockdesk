// Classic scripts share a global lexical scope in the dashboard.
// Checking each file separately misses duplicate top-level declarations.
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const html = fs.readFileSync(path.join(__dirname, 'index.html'), 'utf8');
const scripts = [...html.matchAll(/<script\b([^>]*)>([\s\S]*?)<\/script>/gi)].map(([, attrs, inline]) => {
  const src = attrs.match(/\bsrc=["']([^"']+)["']/i);
  return src ? fs.readFileSync(path.join(__dirname, src[1].replace(/^\//, '')), 'utf8') : inline;
});
new vm.Script(scripts.join('\n;\n'), {filename: 'dashboard-combined.js'});
console.log(`All ${scripts.length} dashboard scripts compile together without global declaration conflicts.`);
