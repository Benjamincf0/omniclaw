# AGENTS.MD

This repo contains the source code for a John Abbott Omnivox MCP server. It exposes tools to do actions in Omnivox for the user, such as gettings recent news.

## How omnivox works

Omnivox doesn't authenticate using headers, but rather via a token sent in the body. When making request to Omnivox, the tool tries to get the auth token in auth.txt to use it in the request body (see the top comment in a_news.html, it shows the curl command with the token in the body to make the request). And if it doesn't find it or it's invalid, the tool will then run the login pipeline which will open a playwright browser and highjack the token returned.

## Stack
- `uv` for everything

## Start MCP server
`uv run omni.py`
