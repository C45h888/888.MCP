#!/bin/bash
curl -X POST "https://mcp-server-7h8i.onrender.com/tool/publish" \
  -H "x-api-key: 92a746171ea6a580f8b29bf31dfe0b0c" \
  -H "Content-Type: application/json" \
  -d '{"channel":"market:data","message":{"schema_version":"v1","timestamp":1764157400,"pair":"BTC-ETH","price_btc":30000.0,"price_eth":2000.0,"volume_btc":150.5}}'
