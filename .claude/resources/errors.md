2025-12-13T02:12:35.49645597Z   File "/app/mcp/server.py", line 239, in load_schemas
2025-12-13T02:12:35.496524012Z     log_with_context(logger, 'error', "Failed to load schema", channel=channel, filename=filename, error=str(e))
2025-12-13T02:12:35.496537742Z   File "/app/mcp/logging_config.py", line 200, in log_with_context
2025-12-13T02:12:35.49723244Z     log_method(message, extra=extra)
2025-12-13T02:12:35.497289361Z   File "/usr/local/lib/python3.11/logging/__init__.py", line 1518, in error
2025-12-13T02:12:35.497293281Z     self._log(ERROR, msg, args, **kwargs)
2025-12-13T02:12:35.497295612Z   File "/usr/local/lib/python3.11/logging/__init__.py", line 1632, in _log
2025-12-13T02:12:35.497300842Z     record = self.makeRecord(self.name, level, fn, lno, msg, args,
2025-12-13T02:12:35.497730873Z              ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
2025-12-13T02:12:35.497738163Z   File "/usr/local/lib/python3.11/logging/__init__.py", line 1606, in makeRecord
2025-12-13T02:12:35.497741143Z     raise KeyError("Attempt to overwrite %r in LogRecord" % key)
2025-12-13T02:12:35.497743543Z KeyError: "Attempt to overwrite 'filename' in LogRecord"
2025-12-13T02:12:37.956559162Z [entrypoint] Starting MCP web server on port 8080
2025-12-13T02:12:38.272074449Z ==> Exited with status 1
2025-12-13T02:12:38.289017678Z ==> Common ways to troubleshoot your deploy: https://render.com/docs/troubleshooting-deploys
2025-12-13T02:12:38.956801438Z {"@timestamp": null, "level": "INFO", "logger": "root", "message": "Logging configured", "log_level": "INFO", "format": "json", "handler": "stdout", "timestamp": 1765591958.9566116}
2025-12-13T02:12:38.957154027Z {"@timestamp": null, "level": "INFO", "logger": "root", "message": "CORS disabled (default). Set CORS_ENABLED=true and CORS_ORIGINS to enable.", "timestamp": 1765591958.9570353}
2025-12-13T02:12:38.961014116Z {"@timestamp": null, "level": "INFO", "logger": "mcp.redis_client", "message": "Connected to Redis at redis://red-d4e1gpqdbo4c73d6sj9g:6379", "timestamp": 1765591958.9608476}
2025-12-13T02:12:38.961078337Z {"@timestamp": null, "level": "INFO", "logger": "mcp.auth", "message": "APIKeyManager initialized", "timestamp": 1765591958.9609787}
2025-12-13T02:12:38.96117458Z {"@timestamp": null, "level": "INFO", "logger": "mcp.rate_limiter", "message": "RateLimiter initialized", "timestamp": 1765591958.961051}
2025-12-13T02:12:38.961275102Z {"@timestamp": null, "level": "INFO", "logger": "mcp.rate_limiter", "message": "Rate limit configuration loaded", "global_ip": "100/minute", "global_key": "200/minute", "publish": "60/minute", "retrieve": "30/minute", "timestamp": 1765591958.9611635}
2025-12-13T02:12:38.970325894Z {"@timestamp": null, "level": "INFO", "logger": "botocore.credentials", "message": "Found credentials in environment variables.", "timestamp": 1765591958.9701998}
2025-12-13T02:12:39.1005981Z {"@timestamp": null, "level": "INFO", "logger": "mcp.uploader.archiver", "message": "\u2705 S3 Archiver initialized for bucket: mcp-data-prod-kamesh.888 (us-east-1)", "timestamp": 1765591959.100377}
2025-12-13T02:12:39.101597456Z Traceback (most recent call last):
2025-12-13T02:12:39.101636747Z   File "/app/mcp/server.py", line 237, in load_schemas
2025-12-13T02:12:39.101729749Z     log_with_context(logger, 'info', "Schema loaded successfully", channel=channel, filename=filename)
2025-12-13T02:12:39.1017447Z   File "/app/mcp/logging_config.py", line 200, in log_with_context
2025-12-13T02:12:39.101949135Z     log_method(message, extra=extra)
2025-12-13T02:12:39.101965685Z   File "/usr/local/lib/python3.11/logging/__init__.py", line 1489, in info
2025-12-13T02:12:39.102254073Z     self._log(INFO, msg, args, **kwargs)
2025-12-13T02:12:39.102267983Z   File "/usr/local/lib/python3.11/logging/__init__.py", line 1632, in _log
2025-12-13T02:12:39.1025422Z     record = self.makeRecord(self.name, level, fn, lno, msg, args,
2025-12-13T02:12:39.10254752Z              ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
2025-12-13T02:12:39.10255083Z   File "/usr/local/lib/python3.11/logging/__init__.py", line 1606, in makeRecord
2025-12-13T02:12:39.102870088Z     raise KeyError("Attempt to overwrite %r in LogRecord" % key)
2025-12-13T02:12:39.102981391Z KeyError: "Attempt to overwrite 'filename' in LogRecord"
2025-12-13T02:12:39.102991012Z 
2025-12-13T02:12:39.102994572Z During handling of the above exception, another exception occurred:
2025-12-13T02:12:39.102997452Z 
2025-12-13T02:12:39.103001752Z Traceback (most recent call last):
2025-12-13T02:12:39.103004602Z   File "/usr/local/bin/uvicorn", line 8, in <module>
2025-12-13T02:12:39.103012702Z     sys.exit(main())
2025-12-13T02:12:39.103018852Z              ^^^^^^
2025-12-13T02:12:39.103022272Z   File "/usr/local/lib/python3.11/site-packages/click/core.py", line 1485, in __call__
2025-12-13T02:12:39.10331254Z     return self.main(*args, **kwargs)
2025-12-13T02:12:39.1033186Z            ^^^^^^^^^^^^^^^^^^^^^^^^^^
2025-12-13T02:12:39.10332201Z   File "/usr/local/lib/python3.11/site-packages/click/core.py", line 1406, in main
2025-12-13T02:12:39.103575287Z     rv = self.invoke(ctx)
2025-12-13T02:12:39.103595177Z          ^^^^^^^^^^^^^^^^
2025-12-13T02:12:39.103598547Z   File "/usr/local/lib/python3.11/site-packages/click/core.py", line 1269, in invoke
2025-12-13T02:12:39.103802282Z     return ctx.invoke(self.callback, **ctx.params)
2025-12-13T02:12:39.103817863Z            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
2025-12-13T02:12:39.103823003Z   File "/usr/local/lib/python3.11/site-packages/click/core.py", line 824, in invoke
2025-12-13T02:12:39.104235133Z     return callback(*args, **kwargs)
2025-12-13T02:12:39.104244184Z            ^^^^^^^^^^^^^^^^^^^^^^^^^
2025-12-13T02:12:39.104246344Z   File "/usr/local/lib/python3.11/site-packages/uvicorn/main.py", line 416, in main
2025-12-13T02:12:39.104389177Z     run(
2025-12-13T02:12:39.104394357Z   File "/usr/local/lib/python3.11/site-packages/uvicorn/main.py", line 587, in run
2025-12-13T02:12:39.104556421Z     server.run()
2025-12-13T02:12:39.104561792Z   File "/usr/local/lib/python3.11/site-packages/uvicorn/server.py", line 61, in run
2025-12-13T02:12:39.104655164Z     return asyncio.run(self.serve(sockets=sockets))
2025-12-13T02:12:39.104701245Z            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
2025-12-13T02:12:39.104709216Z   File "/usr/local/lib/python3.11/asyncio/runners.py", line 190, in run
2025-12-13T02:12:39.104867629Z     return runner.run(main)
2025-12-13T02:12:39.1048732Z            ^^^^^^^^^^^^^^^^
2025-12-13T02:12:39.10487668Z   File "/usr/local/lib/python3.11/asyncio/runners.py", line 118, in run
2025-12-13T02:12:39.104978052Z     return self._loop.run_until_complete(task)
2025-12-13T02:12:39.105140727Z            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
2025-12-13T02:12:39.105146317Z   File "uvloop/loop.pyx", line 1518, in uvloop.loop.Loop.run_until_complete
2025-12-13T02:12:39.105154017Z   File "/usr/local/lib/python3.11/site-packages/uvicorn/server.py", line 68, in serve
2025-12-13T02:12:39.105309691Z     config.load()
2025-12-13T02:12:39.105314851Z   File "/usr/local/lib/python3.11/site-packages/uvicorn/config.py", line 467, in load
2025-12-13T02:12:39.105473725Z     self.loaded_app = import_from_string(self.app)
2025-12-13T02:12:39.105488585Z                       ^^^^^^^^^^^^^^^^^^^^^^^^^^^^
2025-12-13T02:12:39.105492465Z   File "/usr/local/lib/python3.11/site-packages/uvicorn/importer.py", line 21, in import_from_string
2025-12-13T02:12:39.105578188Z     module = importlib.import_module(module_str)
2025-12-13T02:12:39.105588238Z              ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
2025-12-13T02:12:39.105592218Z   File "/usr/local/lib/python3.11/importlib/__init__.py", line 126, in import_module
2025-12-13T02:12:39.105715241Z     return _bootstrap._gcd_import(name[level:], package, level)
2025-12-13T02:12:39.105736872Z            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
2025-12-13T02:12:39.105739962Z   File "<frozen importlib._bootstrap>", line 1204, in _gcd_import
2025-12-13T02:12:39.105741832Z   File "<frozen importlib._bootstrap>", line 1176, in _find_and_load
2025-12-13T02:12:39.105743632Z   File "<frozen importlib._bootstrap>", line 1147, in _find_and_load_unlocked
2025-12-13T02:12:39.105745482Z   File "<frozen importlib._bootstrap>", line 690, in _load_unlocked
2025-12-13T02:12:39.105747222Z   File "<frozen importlib._bootstrap_external>", line 940, in exec_module
2025-12-13T02:12:39.105748932Z   File "<frozen importlib._bootstrap>", line 241, in _call_with_frames_removed
2025-12-13T02:12:39.105752892Z   File "/app/mcp/server.py", line 244, in <module>
2025-12-13T02:12:39.105911496Z     load_schemas()
2025-12-13T02:12:39.105920747Z   File "/app/mcp/server.py", line 239, in load_schemas
2025-12-13T02:12:39.106033199Z     log_with_context(logger, 'error', "Failed to load schema", channel=channel, filename=filename, error=str(e))
2025-12-13T02:12:39.10605275Z   File "/app/mcp/logging_config.py", line 200, in log_with_context
2025-12-13T02:12:39.106197164Z     log_method(message, extra=extra)
2025-12-13T02:12:39.106203074Z   File "/usr/local/lib/python3.11/logging/__init__.py", line 1518, in error
2025-12-13T02:12:39.10644911Z     self._log(ERROR, msg, args, **kwargs)
2025-12-13T02:12:39.10646437Z   File "/usr/local/lib/python3.11/logging/__init__.py", line 1632, in _log
2025-12-13T02:12:39.106802299Z     record = self.makeRecord(self.name, level, fn, lno, msg, args,
2025-12-13T02:12:39.106806889Z              ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
2025-12-13T02:12:39.106809549Z   File "/usr/local/lib/python3.11/logging/__init__.py", line 1606, in makeRecord
2025-12-13T02:12:39.107112247Z     raise KeyError("Attempt to overwrite %r in LogRecord" % key)
2025-12-13T02:12:39.107126238Z KeyError: "Attempt to overwrite 'filename' in LogRecord"