# On-Chain Fundamentals & Risk Analyzer - Frontend

## Overview
The frontend is a Streamlit-based Risk Dashboard designed to interact with the On-Chain Fundamentals API. It provides an intuitive interface for evaluating crypto projects and visualizing their risk assessments.

## Features
- Input fields for project details, whitepapers, or audit texts.
- Real-time connection to the backend's `/api/v1/analyze` endpoint.
- Visualization of aggregate risk scores (Safe, Moderate, High, Critical).
- Display of flagged issues, vulnerabilities, and extracted project fundamentals (Tokenomics, etc.).

## Setup & Execution

### 1. Install dependencies
Ensure you have Python 3.12+ installed, then run:
```bash
pip install -r requirements.txt
```

### 2. Run the dashboard
The backend must be running locally (usually at `http://localhost:8000`) before you submit analysis requests.

Start the Streamlit UI:
```bash
streamlit run Home.py
```

The application will be available at:
```
http://localhost:8501
```

## Deployment
The project includes a `Procfile` for easy deployment to platforms like Heroku or Railway:
```
web: streamlit run Home.py --server.port $PORT --server.address 0.0.0.0
```
