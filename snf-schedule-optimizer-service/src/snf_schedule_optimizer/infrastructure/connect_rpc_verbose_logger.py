# import logging
# import sys
# from collections.abc import Callable
# from typing import Any
#
# from connectrpc._interceptor_async import Interceptor
# from connectrpc.errors import ConnectError
# from connectrpc.request import RequestContext
#
# # 1. Standard Logger Setup
# logging.basicConfig(
#     level=logging.DEBUG,
#     format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
#     stream=sys.stdout,
# )
# logger = logging.getLogger("api-server")
#
#
# # 2. Connect-RPC Verbose Interceptor
# class VerboseLoggingInterceptor(Interceptor):
#     """
#     Interceptor to log the full request and response payloads
#     for all Connect-RPC calls.
#     """
#
#     async def unary_stream(
#         self, next_call: Callable, request: Any, ctx: RequestContext[Any, Any]
#     ) -> Any:
#         return await self._log_call(next_call, request, ctx)
#
#     async def stream_unary(
#         self, next_call: Callable, request: Any, ctx: RequestContext[Any, Any]
#     ) -> Any:
#         return await self._log_call(next_call, request, ctx)
#
#     async def stream_stream(
#         self, next_call: Callable, request: Any, ctx: RequestContext[Any, Any]
#     ) -> Any:
#         return await self._log_call(next_call, request, ctx)
#
#     async def unary_unary(
#         self, next_call: Callable, request: Any, ctx: RequestContext[Any, Any]
#     ) -> Any:
#         return await self._log_call(next_call, request, ctx)
#
#     async def _log_call(
#         self, next_call: Callable, request: Any, ctx: RequestContext[Any, Any]
#     ) -> Any:
#         procedure = ctx.procedure
#         logger.info(f"RPC REQUEST [{procedure}] Payload: {request}")
#
#         try:
#             response = await next_call(request, ctx)
#             logger.info(f"RPC RESPONSE [{procedure}] Success")
#             # For extremely verbose payload logging:
#             # logger.debug(f"RPC RESPONSE [{procedure}] Payload: {response}")
#             return response
#         except ConnectError as e:
#             logger.error(f"RPC ERROR [{procedure}] Code: {e.code} Message: {e.message}")
#             raise
#         except Exception as e:
#             logger.exception(f"RPC UNCAUGHT EXCEPTION [{procedure}]")
#             raise
