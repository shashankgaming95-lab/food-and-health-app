# Food & Health Smart Assistant

## Chosen Vertical
Food & Health – helping users make better food choices through contextual insights and Google AI.

## Approach & Logic
**Data persistence**: Google Sheets (serverless, zero setup for judging).
**Smart swap suggestions**: Google Gemini API analyzes meal name and returns a healthier alternative based on nutrition knowledge.
**User context**: Stores goals and preferences in Sheets to personalise insights.
**Decision making**: The assistant compares daily intake against goals and highlights what’s missing/exceeding.

## How It Works
1. User sets daily nutrition goals in the sidebar.
2. User logs meals via a simple form.
3. Data is saved to Google Sheets.
4. Dashboard shows progress against goals.
5. User can enter any meal name → Gemini suggests a healthier swap.
6. Weekly trend chart shows calorie patterns.

## Assumptions Made
User has a Google account and can enable Sheets API & Gemini API.
Service account credentials are provided via Streamlit secrets.
No real‑time food database – users manually enter meal nutrition (to keep the app lightweight and under 1 MB).

## Google Services Used
**Google Sheets API** – database.
**Gemini API** – intelligent meal swap suggestions.

## Setup Instructions (for evaluators)
1. Clone repo.
2. Create a Google Cloud project, enable Sheets API & Gemini API.
3. Create a service account and share a Google Sheet with it.
4. Add credentials to `.streamlit/secrets.toml`.
5. Run `streamlit run app.py`.
