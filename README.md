# Connect Suggests – Customer Approves · Nordic Opening-Hours Simulator

A simulator framework and API backend for automated opening-hours suggestion, verification, and Yext integration for Nordic business locations.

## Overview

This project provides an end-to-end framework to evaluate, suggest, and publish business holiday and special opening hours across Finland, Sweden, and Norway. It integrates with Yext APIs (or local mock services) to maintain findability and accuracy for business listings.

## Requirements

### Python Requirements
- **Python 3.9+**
- Install dependencies specified in `requirements.txt`:
  ```bash
  python -m venv .venv
  source .venv/bin/activate  # On Windows: .venv\Scripts\Activate.ps1
  pip install -r requirements.txt
  ```

### Node.js Requirements
- **Node.js v20.11.0** (locked via `.nvmrc`, `package.json`, `.npmrc`)
- Use `nvm` to manage Node versions:
  ```bash
  nvm install
  nvm use
  npm ci
  ```

## Environment Setup

Create your local `.env` file from the template `env_mockup`:

```bash
cp env_mockup .env
```

Configure your environment variables in `.env` (e.g. `YEXT_API_KEY`, `YEXT_BASE_URL`).

## Running the API Server

Start the API backend server using either the simulator backend or the mock Yext API server:

- **Simulator App Server**:
  ```bash
  python -m app.server
  ```
- **Mock API Server**:
  ```bash
  python mock_api/server.py
  ```

The server runs locally by default (e.g., `http://localhost:8787`).

## Testing & Evaluation

### Yext Connection / Integration Test
Run the Yext API integration test (Node.js):
```bash
npm run test:yext
```

### Evaluation & Scoring
Run the Python evaluation suite to score predictions against benchmark datasets:
```bash
python evaluation/evaluate.py
```
To run baseline predictions and score the output:
```bash
python baseline.py
python evaluation/evaluate.py --predictions outputs/baseline_predictions_2026.csv
```

