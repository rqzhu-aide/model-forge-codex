# Preparing an npm prerelease

Model Forge 0.9.1 is a documentation update to the 0.9.0 prerelease. This guide prepares a reviewed artifact;
it does not imply that the npm package or a GitHub release has been published.
The application version is 0.9.1. The workflow catalog has its own version,
pinned in `contracts/catalog-pin.json`.

The package uses existing shared Python 3.11+ and Node.js 22+ installations.
It does not install runtimes, create a virtual environment, or install
project-local dependencies. See the [development guide](../docs/development.md)
for shared build dependencies and the [model access guide](../docs/model-access.md)
for connections and Windows sandbox setup.

## Prepare and check the artifact

Align the application version in `package.json`, `pyproject.toml`,
`web/package.json`, and `src/model_forge_codex/__init__.py` before each release.
Keep the separately reviewed workflow catalog pin unchanged unless that catalog
is intentionally revised. npm versions cannot be replaced after publication.

From the repository root, using the shared runtimes:

```sh
npm pack
npm run test:npm
python -B scripts/smoke_npm_release.py rqzhu-aide-model-forge-codex-0.9.1.tgz
```

`npm pack` runs `scripts/prepare_npm_package.mjs`. It verifies catalog hashes,
rebuilds the interface, bundles the math validator and portable report exporter,
and checks npm's final file inventory. It generates `npm-release-manifest.json`
with hashes of the shipped files and a release identity derived from their
content and application version. It does not refresh the catalog manifest or
install dependencies. Do not bypass the prepack check for a release artifact.

The allowlist includes application Python source, the complete pinned catalog,
built interface assets, bundled math and report tools, dependency license
notices, README, model access and development guides, and package metadata.
Saved projects, provider configurations, credentials, architecture evidence,
tests, caches, and development dependencies are excluded. Inspect the actual
tarball inventory before publishing; GitHub source and npm have separate file
inventories and must each be reviewed.

The smoke script launches the tarball through npm's normal user-wide cache in
offline mode. It uses disposable research data and an unused port. It checks
replacement of an idle older release, served UI assets, the empty project API,
same-release reuse, clean shutdown, and preservation of a provider-file sentinel.
It sets an unavailable shared frontend package directory to confirm that the
artifact runs without globally installed React, Vite, or KaTeX. It makes no
model requests and does not use production research data.

The launcher copies verified application bytes into
`~/.model-forge-codex-app/releases/<release-id>` so npm cache updates cannot
change a running session. No language runtime or dependency installation is
copied there. Research remains separate, normally in `~/.model-forge-codex`.
Browser opening, Ctrl+C, native sandbox use, and actual model research require
their own checks. Record the operating systems and runtime versions actually
tested instead of treating the package's version ranges as platform certification.

Before publication, record the tarball SHA-256, package version, catalog pin,
test results, and the exact commit containing its source. Rebuild and recheck
if any shipped file changes, including documentation. Keep the reviewed tarball
out of Git. A private GitHub repository does not make a public npm package
private; review the package contents and documentation for public distribution.

## Publish when authorized

After explicit publication authorization, an npm maintainer with access to the
`@rqzhu-aide` scope can publish the exact reviewed tarball under `next`:

```sh
npm publish rqzhu-aide-model-forge-codex-0.9.1.tgz --access public --tag next
```

The prerelease launch command then becomes:

```sh
npx @rqzhu-aide/model-forge-codex@next web
```

Publish prerelease updates with `--tag next` and leave an existing `latest`
tag unchanged. npm may assign `latest` on the first publication even when
another tag was requested; removing it can fail with HTTP 400, as recorded in
[npm/cli issue 8490](https://github.com/npm/cli/issues/8490). Do not promise
that the package can have no `latest` tag. The default npm page selects that
tag; use the version-specific page to inspect a prerelease README.

Verify the published version, distribution tags, integrity, and launch command
from a fresh user environment. GitHub
pushes, tags, releases, and npm publication are separate actions. Use the
reviewed artifact for any GitHub release attachment as well.
