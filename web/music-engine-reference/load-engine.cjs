const fs = require('node:fs');
const path = require('node:path');
function load(relative) {
  const target = {exports: {}};
  const source = fs.readFileSync(path.join(__dirname, relative), 'utf8').replace('export const Music = globalThis.Music;', '');
  new Function('module', 'exports', source)(target, target.exports);
  return target.exports;
}
module.exports = {Music: load('../frontend/src/lib/music.js'), Fingerprint: load('../frontend/public/fingerprint.js')};
