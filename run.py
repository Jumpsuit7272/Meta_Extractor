#!/usr/bin/env python
"""Run the RPD extraction and comparison service."""
import uvicorn

from rpd.config import settings

if __name__ == "__main__":
    uvicorn.run(
        "rpd.main:app",
        host=settings.host,
        port=settings.port,
        reload=True,
    )
