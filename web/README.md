# Research workbench frontend

The frontend uses the shared Node installation and user-wide or machine-wide npm packages. It does not require a project-local `node_modules` directory.

Install the versions declared in `package.json` in the shared npm location. If more than one installation exists, set `MF_SHARED_NODE_MODULES` to the intended global `node_modules` directory. The launcher uses one physical package root for React and its renderer, including packaged Windows terminal environments.

From this directory:

```text
node scripts/vite.mjs dev
node scripts/vite.mjs build
node --test tests/*.test.mjs
```

The development server defaults to `127.0.0.1:5173` and proxies the API to `127.0.0.1:8766`. `MF_WEB_PORT` and `MF_API_URL` override those addresses. Vite's cache stays in the system temporary directory. Production output is written to `dist`.

On Windows, a restricted terminal may be unable to access an existing shared installation or an ancestor of the project. Verify with normal access before treating a dependency as missing.

Semantic and rendered-component tests cover the scientific outcome mapping, branch isolation, exact target references, dependency defects and large graphs, and hidden diagnostic failures. Live browser verification is still required for navigation, keyboard/focus interactions, streaming progress, viewport layout, and the complete backend workflow.
