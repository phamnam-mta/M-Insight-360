from fastapi import FastAPI

app = FastAPI(title="M-Insight 360")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/")
def root():
    return {"service": "m-insight-360", "status": "placeholder — foundation not built yet"}
