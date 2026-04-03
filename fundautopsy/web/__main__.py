"""Launch Fund Autopsy dashboard: python -m fundautopsy.web"""

import uvicorn

if __name__ == "__main__":
    print("\n  Fund Autopsy Dashboard — http://localhost:8000\n")
    uvicorn.run("fundautopsy.web.app:app", host="0.0.0.0", port=8000, reload=True)
