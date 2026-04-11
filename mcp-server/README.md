    "omniMCPserver": {
      "command": "bunx",
      "args": [
        "-y",
        "mcp-remote",
        "http://localhost:8000/mcp",
        "--allow-http",
        "--header",
        "Authorization: Bearer sometingwog"
      ],
      "env": {
        "MCP_TOKEN": "sometingwong"
      }
    },
