# tools

## validate_mermaid.mjs

CLAUDE.md requires validating Mermaid syntax before writing it to a file. This parses
every ```mermaid block in a markdown file and reports which ones fail.

    npm install mermaid jsdom      # one time, anywhere
    cd /path/with/node_modules && node <repo>/tools/validate_mermaid.mjs <repo>/plan.md

Exits non-zero if any block is invalid, so it works as a pre-commit check.

Note: mermaid needs a DOM, so this shims one via jsdom. On Node 24+, `navigator` is a
getter-only global, which is why the shim uses Object.defineProperty rather than plain
assignment.

Deps are NOT vendored in this repo. Install them somewhere and run the script from that
directory so Node can resolve `mermaid` and `jsdom`:

    mkdir -p ~/.mmv && cd ~/.mmv && npm install mermaid jsdom
    cd ~/.mmv && node /path/to/repo/tools/validate_mermaid.mjs /path/to/repo/plan.md
