// Minimal pre-commit hook for TriPSs/conventional-changelog-action
// Updates codex/__init__.py __version__ to the new version.
// Must export a CommonJS function named `preCommit(props)`.

const fs = require('fs');
const path = require('path');

exports.preCommit = ({ version }) => {
  const file = path.join(process.cwd(), 'codex', '__init__.py');
  const src = fs.readFileSync(file, 'utf8');
  const re = /(\n__version__\s*=\s*")([^"]*)("\s*\n?)/;
  if (!re.test(src)) {
    throw new Error(`Could not locate __version__ assignment in ${file}`);
  }
  const out = src.replace(re, `$1${version}$3`);
  fs.writeFileSync(file, out, 'utf8');
  console.log(`Updated codex/__init__.py to version ${version}`);
};
