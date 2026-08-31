"""Talk to server.py the way an AI host would, and print what crosses the wire.

    uv run python mcp_server/demo_client.py

There is no AI here. This is just a program launching another program and exchanging
JSON with it, which is all MCP ever is.
"""

import asyncio
import json

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# Tell the client how to LAUNCH the server. It becomes a child process of this one.
params = StdioServerParameters(command="python", args=["mcp_server/server.py"])


def show(label, obj):
    print(f"\n{'=' * 70}\n{label}\n{'=' * 70}")
    print(json.dumps(obj, indent=2, default=str))


async def call(session, tool, args):
    """Call a tool and always come back with something printable.

    Two ways a call can come back, and a client MUST handle both:

      is_error=False -> our tool ran. Its return value arrives as JSON text.
      is_error=True  -> the tool never ran. The SDK rejected the arguments before
                        reaching our code, and the text is a human-readable
                        validation message, NOT JSON.

    The first version of this file did json.loads() unconditionally and exploded
    with a stack trace the moment an argument was wrong — hiding a perfectly clear
    error message behind a crash. Exactly the failure this project keeps warning
    about, committed by the client instead of the server.
    """
    r = await session.call_tool(tool, args)
    if r.is_error:
        msg = r.content[0].text if r.content else "(no detail)"
        # is_error covers TWO different causes, and they are worth telling apart:
        #   - bad arguments  -> SDK rejected the call, body never ran, message names
        #                       the offending field
        #   - body raised    -> your code ran and threw. The SDK deliberately does NOT
        #                       forward your exception text (it can leak paths, creds,
        #                       internals), so all the caller gets is a generic line.
        rejected = "validation error" in msg
        return {
            "_is_error": True,
            "_cause": "bad arguments — body never ran"
            if rejected
            else "the tool body raised — your exception text was NOT forwarded",
            "message": msg,
        }
    text = r.content[0].text if r.content else ""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"_not_json": True, "raw": text}


async def main():
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            # STEP 1: "what can you do?" The client asks; the server answers. This is
            # how a model discovers tools — nobody hardcodes the list.
            tools = await session.list_tools()
            show(
                "STEP 1 — the client asks the server what tools exist",
                [
                    {
                        "name": t.name,
                        # full text, NOT .split("\n")[0] — truncating here once hid a real edit
                        "description": t.description,
                        "inputSchema": t.input_schema,
                    }
                    for t in tools.tools
                ],
            )

            # STEP 2: a real call.
            show(
                "STEP 2 — call it: get_player_form(player_name='Josh Allen')",
                await call(session, "get_player_form", {"player_name": "Josh Allen"}),
            )

            # STEP 3: a name that does not exist. Our tool RETURNS an error dict, so
            # is_error stays False — this is a successful call reporting bad input.
            show(
                "STEP 3 — a name that does not exist",
                await call(session, "get_player_form", {"player_name": "Zxqv"}),
            )

            # STEP 4: a name that matches several people.
            show(
                "STEP 4 — a name matching several players",
                await call(session, "get_player_form", {"player_name": "Allen"}),
            )

            # STEP 5: the optional argument. If you deleted `= 3` from the server, this
            # one still works while STEP 2 gets rejected — that contrast IS the lesson.
            out = await call(
                session, "get_player_form", {"player_name": "Josh Allen", "weeks": 6}
            )
            show(
                "STEP 5 — weeks=6 explicitly",
                out
                if "games" not in out
                else {"games_returned": len(out["games"]), "average_ppr": out["average_ppr"]},
            )


asyncio.run(main())
