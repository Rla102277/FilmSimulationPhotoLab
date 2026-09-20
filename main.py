#!/usr/bin/env python3
"""Run the web app; --verify checks the immutable Leica reference offline."""
import os, sys
if __name__ == "__main__":
    if "--verify" in sys.argv:
        from verify_bundle import validate
        validate()
        print("Authoritative Leica reference verified")
    else:
        import uvicorn
        uvicorn.run("server.main:app", host="0.0.0.0", port=int(os.getenv("PORT", "5000")))
