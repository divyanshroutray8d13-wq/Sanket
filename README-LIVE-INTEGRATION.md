# SANKET live integration

The live path is:

`Browser → FastAPI → RailRadar → Sanket forecast_full → Browser`

Set these in `frontend/.env.local` for local live mode:

```env
VITE_API_URL=http://localhost:8000
VITE_LIVE_MODE=true
```

The backend caches each `(train_no, profile)` live response for 90 seconds.
Refreshing the train page during that window does not create another RailRadar
request. Restarting the FastAPI process clears the in-memory cache.

Replay remains the default when `VITE_LIVE_MODE=false`.

## Run

Terminal 1:

```powershell
python -m uvicorn src.api.main:app --reload --host 127.0.0.1 --port 8000
```

Terminal 2:

```powershell
cd frontend
npm run dev
```

Then open `/train/12951`.

Do not run the historical collector for this integration test; it makes many
provider requests and is unrelated to the live endpoint.
