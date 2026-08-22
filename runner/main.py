# this is the lightweigth backend that exists on the cloud vm instance in order to get code, run code and return the results
# runs with uvicorn main:app --host 0.0.0.0 --port 8001

import asyncio
import logging
from concurrent.futures import TimeoutError as FutureTimeoutError
from contextlib import asynccontextmanager
from dataclasses import asdict

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from runner import LANGS, CodeRunner

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 2 C++ slots + 2 Python slots kept warm; each recycles back to its own
# language after a job, so the balance holds under mixed load.
runner = CodeRunner(warm={"cpp": 2, "python": 2})


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting CodeRunner...")
    # start() spins up containers (blocking Docker calls) — run it off the
    # event loop so startup doesn't stall the async runtime.
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, runner.start)
    logger.info("CodeRunner ready.")
    yield
    logger.info("Shutting down CodeRunner...")
    runner.stop()


app = FastAPI(lifespan=lifespan)


# ---------------------------------------------------------------------------
# Single run — no test cases, just execute once
# ---------------------------------------------------------------------------
class RunRequest(BaseModel):
    code:     str
    language: str
    stdin:    str = ""
    timeout:  int = 10


@app.post("/run")
async def run_code(payload: RunRequest):
    try:
        result = await runner.submit(
            code=payload.code,
            language=payload.language,
            timeout=payload.timeout,
            stdin=payload.stdin,
        )
        return asdict(result)
    except ValueError as e:
        # e.g. unsupported language — client error, not a server fault.
        raise HTTPException(status_code=400, detail=str(e))
    except FutureTimeoutError:
        raise HTTPException(status_code=504, detail="Execution timed out")
    except Exception as e:
        logger.exception("Run failed")
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Batch run — one execution per test case, SAME container, single recycle
# ---------------------------------------------------------------------------
class RunBatchRequest(BaseModel):
    code:       str
    language:   str
    stdin_list: list[str]
    timeout:    int = 10


@app.post("/run-batch")
async def run_code_batch(payload: RunBatchRequest):
    try:
        results = await runner.submit_batch(
            code=payload.code,
            language=payload.language,
            stdin_list=payload.stdin_list,
            timeout=payload.timeout,
        )
        return {"results": [asdict(r) for r in results]}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except FutureTimeoutError:
        raise HTTPException(status_code=504, detail="Execution timed out")
    except Exception as e:
        logger.exception("Batch run failed")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
def health():
    return {"status": "ok", "languages": sorted(LANGS)}