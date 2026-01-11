"""Data stores for persistence and caching.

Stores handle:
- PostgreSQL: DB session, repositories, ORM operations
- Redis: caching, locks, TTL policies

No business/ranking logic in stores - that belongs in services.
"""
