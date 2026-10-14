"""MCP server exposing the planner tools to AI assistants (ADR-009). Same registry as the REST API.

    python -m src.serving.mcp_server          # stdio transport
"""

from __future__ import annotations

import inspect

from mcp.server.mcpserver import MCPServer

from src.serving.tools import REGISTRY, Tools

INSTRUCTIONS = ("Tools for mobile network planning in Indonesia, Malaysia, the Philippines, Germany, France, the US and the UAE: "
                "how slow mobile is at a place and for how many people, each country's checked site plan, a grounded note on one "
                "planned site, and a comparison of countries. Answers come from public data (Ookla open speed tiles, two population "
                "maps, satellite land cover); every number in a site note is traced to the tool's facts.")


def build_server(tools: Tools | None = None) -> MCPServer:
    t = tools or Tools()
    srv = MCPServer(name="next-site-planner", instructions=INSTRUCTIONS, version="1")
    for name in REGISTRY:
        fn = getattr(t, name)

        def make(f):
            def call(**kw):
                return f(**kw).model_dump()
            call.__name__, call.__doc__, call.__signature__ = f.__name__, inspect.getdoc(f), inspect.signature(f)
            return call
        srv.tool(name=name, description=inspect.getdoc(fn))(make(fn))
    return srv


if __name__ == "__main__":
    build_server().run("stdio")
