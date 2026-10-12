import os

import uvicorn

if __name__ == "__main__":
    uvicorn.run("micro_models.api:create_app", factory=True, host="0.0.0.0",
                port=int(os.environ.get("PORT", "8000")), workers=1)
