"""
Domain layer with bounded contexts.
Each sub-package is a self-contained bounded context.
Imports between contexts should only use the package's public __init__.py API, not internal modules.
"""
