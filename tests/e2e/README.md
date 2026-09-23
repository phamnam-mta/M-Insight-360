Playwright end-to-end tests (Phần C, T22–T28 of instruction v2.3's
regression suite). Run with `cd web && npx playwright test`, not `pytest`
— this directory is TypeScript/Playwright, not Python.

Requires a locally running server (build the frontend, then serve it the
same way `Dockerfile` does):

```
cd web && npm run build
cd .. && uvicorn app.main:app --host 0.0.0.0 --port 8080
```

Then, in another shell: `cd web && npx playwright test`.
