# Dishwise

Dishwise is a multimodal food-understanding prototype that identifies a dish from an image or text, asks clarifying questions when needed, and generates ingredients, recipe steps, and nutrition estimates.

## Run

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
 # add OPENAI_API_KEY to .env
streamlit run ui/app.py
```

## Demo Steps

1) Upload a food image or type a dish description.
2) Answer up to two clarification questions if shown.
3) Review the dish candidates, ingredients, nutrition, and recipe.
4) (Optional) Enable Swiggy MCP and try commerce lookup.

## Swiggy MCP

This prototype can optionally call Swiggy MCP HTTP endpoints using the MCP streamable HTTP transport.
To enable:

- Set `SWIGGY_MCP_ENABLED=true`
- Choose a server: `SWIGGY_MCP_SERVER_NAME=swiggy-food|swiggy-instamart|swiggy-dineout`
- Ensure `mcp.json` points to the Swiggy MCP endpoints:

```json
{
  "mcpServers": {
    "swiggy-food": { "type": "http", "url": "https://mcp.swiggy.com/food" },
    "swiggy-instamart": { "type": "http", "url": "https://mcp.swiggy.com/im" },
    "swiggy-dineout": { "type": "http", "url": "https://mcp.swiggy.com/dineout" }
  }
}
```

If your Swiggy MCP setup requires auth, set `SWIGGY_MCP_AUTH_HEADER` and `SWIGGY_MCP_AUTH_TOKEN` in `.env`.

## Notes

- Nutrition is a deterministic estimate derived from the ingredient list and serving assumption.
- The commerce lookup is optional and non-blocking; it falls back gracefully if MCP is not configured.
