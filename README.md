# MdevTrade: Multi-Agent Trading Research Firm

MdevTrade (formerly `mdevmt5`) is a fully automated AI-driven **Investment Research Firm**, built on top of LangGraph and Large Language Models (LLMs).

Operating on a microservices architecture, this system serves as the analytical "Brain" of the operation, outputting structured **Trading Reports (JSON)**. It is designed to seamlessly integrate with execution "Hands" (Trading Firms—such as MT5 Expert Advisors, Binance Bots, or K3s deployments) that execute orders in the live market.

## 🌟 12-Node Architecture (Industrial Pipeline)

The system orchestrates a rigorous workflow featuring 12 sequential "AI Employees":

1. **Phase 1 (Data Gathering):** 4 Analysts (Market, Social, News, Fundamentals) gather macro and micro data. Real-time pricing data and technical indicators are fetched deterministically to prevent AI hallucination.
2. **Phase 2 (Investment Debate):** Bull and Bear factions engage in two rounds of debate (Blind Thesis Writing &rarr; Cross-Rebuttal). The `Research Manager` acts as a referee, breaking deadlocks and determining the final market direction.
3. **Phase 3 (Trading):** The `Trader` agent calculates position sizing, utilizing real-time ATR (Average True Range) volatility to output precise Stop Loss and Take Profit levels, eliminating guesswork.
4. **Phase 4 (Risk Management):** 3 Risk Managers (Aggressive, Conservative, Neutral) independently dissect the Trader's plan. Finally, the `Portfolio Manager` performs the ultimate review and approves the final order.

**Output:** All decisions are strictly constrained and validated into a structured JSON format, ready for downstream trading infrastructures to parse and execute reliably.

## ⚙️ Installation & Usage

1. **Environment Setup:**
This project manages dependencies via `pyproject.toml` and `uv`.

```bash
# Recommended: Install dependencies using uv
uv sync
```

2. **API Keys Configuration:**
Copy `.env.example` to `.env` and fill in your credentials:

```bash
cp .env.example .env
```

Key environment variables:
- `LLM_BASE_URL`: OpenAI-compatible API endpoint (e.g., LiteLLM, Ollama).
- `LLM_API_KEY`: Your LLM API key.
- `LLM_DEEP_MODEL`: Deep reasoning model for Managers and complex nodes (e.g., `gemini-3-pro-preview`, `gpt-4o`, `claude-3-opus`).
- `BINANCE_API_KEY` / `BINANCE_SECRET_KEY`: For real-time spot trading execution and data fetching.
- `DATABASE_URI` / `REDIS_URI`: For state persistence and LangGraph checkpointers.

3. **Running the System:**
To spin up the system using LangGraph Studio or Dev mode:

```bash
make dev
```
Alternatively, to build the production Docker image:
```bash
make build
```

## 🙏 Acknowledgments

This project is inspired by and inherits the core philosophy of the original **[TradingAgents](https://github.com/TauricResearch/TradingAgents)** project by TauricResearch.

