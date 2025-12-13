2025-12-13T06:29:48.9492434Z   File "/usr/local/lib/python3.11/site-packages/uvicorn/middleware/proxy_headers.py", line 84, in __call__
2025-12-13T06:29:48.949246091Z     return await self.app(scope, receive, send)
2025-12-13T06:29:48.94924848Z            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
2025-12-13T06:29:48.949250921Z   File "/usr/local/lib/python3.11/site-packages/fastapi/applications.py", line 1106, in __call__
2025-12-13T06:29:48.949253441Z     await super().__call__(scope, receive, send)
2025-12-13T06:29:48.949255811Z   File "/usr/local/lib/python3.11/site-packages/starlette/applications.py", line 122, in __call__
2025-12-13T06:29:48.949258531Z     await self.middleware_stack(scope, receive, send)
2025-12-13T06:29:48.949270742Z   File "/usr/local/lib/python3.11/site-packages/starlette/middleware/errors.py", line 184, in __call__
2025-12-13T06:29:48.949272662Z     raise exc
2025-12-13T06:29:48.949274542Z   File "/usr/local/lib/python3.11/site-packages/starlette/middleware/errors.py", line 162, in __call__
2025-12-13T06:29:48.949276332Z     await self.app(scope, receive, _send)
2025-12-13T06:29:48.949278082Z   File "/usr/local/lib/python3.11/site-packages/starlette/middleware/base.py", line 108, in __call__
2025-12-13T06:29:48.949279822Z     response = await self.dispatch_func(request, call_next)
2025-12-13T06:29:48.949281502Z                ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
2025-12-13T06:29:48.949283233Z   File "/app/mcp/server.py", line 1215, in validate_content_type
2025-12-13T06:29:48.949285003Z     response = await call_next(request)
2025-12-13T06:29:48.949286643Z                ^^^^^^^^^^^^^^^^^^^^^^^^
2025-12-13T06:29:48.949288383Z   File "/usr/local/lib/python3.11/site-packages/starlette/middleware/base.py", line 84, in call_next
2025-12-13T06:29:48.949290613Z     raise app_exc
2025-12-13T06:29:48.949293383Z   File "/usr/local/lib/python3.11/site-packages/starlette/middleware/base.py", line 70, in coro
2025-12-13T06:29:48.949296503Z     await self.app(scope, receive_or_disconnect, send_no_error)
2025-12-13T06:29:48.949299134Z   File "/usr/local/lib/python3.11/site-packages/starlette/middleware/base.py", line 108, in __call__
2025-12-13T06:29:48.949301974Z     response = await self.dispatch_func(request, call_next)
2025-12-13T06:29:48.949307574Z                ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
2025-12-13T06:29:48.949310464Z   File "/app/mcp/server.py", line 185, in rate_limit_middleware
2025-12-13T06:29:48.949313484Z     response = await call_next(request)
2025-12-13T06:29:48.949316035Z                ^^^^^^^^^^^^^^^^^^^^^^^^
2025-12-13T06:29:48.949318885Z   File "/usr/local/lib/python3.11/site-packages/starlette/middleware/base.py", line 84, in call_next
2025-12-13T06:29:48.949321695Z     raise app_exc
2025-12-13T06:29:48.949323545Z   File "/usr/local/lib/python3.11/site-packages/starlette/middleware/base.py", line 70, in coro
2025-12-13T06:29:48.949325405Z     await self.app(scope, receive_or_disconnect, send_no_error)
2025-12-13T06:29:48.949327185Z   File "/usr/local/lib/python3.11/site-packages/starlette/middleware/base.py", line 108, in __call__
2025-12-13T06:29:48.949329005Z     response = await self.dispatch_func(request, call_next)
2025-12-13T06:29:48.949330725Z                ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
2025-12-13T06:29:48.949332425Z   File "/app/mcp/server.py", line 114, in add_security_headers
2025-12-13T06:29:48.949334105Z     response.headers.pop("Server", None)
2025-12-13T06:29:48.949335856Z     ^^^^^^^^^^^^^^^^^^^^
2025-12-13T06:29:48.949337556Z AttributeError: 'MutableHeaders' object has no attribute 'pop'
2025-12-13T06:29:49.925848964Z ==> Timed Out
2025-12-13T06:29:49.945115872Z ==> Common ways to troubleshoot your deploy: https://render.com/docs/troubleshooting-deploys
2025-12-13T06:30:52.067892576Z INFO:     Shutting down
2025-12-13T06:30:52.168374562Z INFO:     Waiting for application shutdown.
2025-12-13T06:30:52.16867163Z {"@timestamp": null, "level": "INFO", "logger": "root", "message": "MCP Server shutting down", "timestamp": 1765607452.1683617}
2025-12-13T06:30:52.16868714Z {"@timestamp": null, "level": "INFO", "logger": "mcp.uploader.archiver", "message": "Stopping archiver...", "timestamp": 1765607452.168507}
2025-12-13T06:30:52.171793771Z {"@timestamp": null, "level": "INFO", "logger": "mcp.uploader.archiver", "message": "Archiver stopped. Total archived: 0", "timestamp": 1765607452.1716697}
2025-12-13T06:30:52.171847214Z {"@timestamp": null, "level": "INFO", "logger": "root", "message": "Archiver stopped", "timestamp": 1765607452.1717584}
2025-12-13T06:30:52.177723605Z {"@timestamp": null, "level": "INFO", "logger": "mcp.redis_client", "message": "Redis connection closed", "timestamp": 1765607452.171939}
2025-12-13T06:30:52.177737246Z {"@timestamp": null, "level": "INFO", "logger": "root", "message": "MCP Server stopped", "timestamp": 1765607452.1719975}
2025-12-13T06:30:52.177749697Z INFO:     Application shutdown complete.
2025-12-13T06:30:52.177753057Z INFO:     Finished server process [1]