"""Tests for database engine, configuration, and connection checking."""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch
from sqlalchemy.engine.url import make_url
from sqlalchemy.orm import Session

from backend.app.core.config import Settings, normalize_database_url, sanitize_database_url
from backend.app.db.session import check_database_connection, create_db_engine, normalize_db_url


class DatabaseConfigurationTests(unittest.TestCase):
    """Test suite covering the 10 database URL normalization and engine requirements."""

    def test_01_valid_postgresql_url_remains_unchanged(self) -> None:
        """1. Valid postgresql:// URL remains unchanged."""
        url = "postgresql://iris_user:secret_pass@db.example.com:5432/iris_prod"
        normalized = normalize_database_url(url)
        self.assertEqual(normalized, url)

    def test_02_valid_postgresql_plus_driver_url_remains_unchanged(self) -> None:
        """2. Valid postgresql+driver:// URL remains unchanged."""
        url_psycopg = "postgresql+psycopg://iris_user:secret_pass@db.example.com:5432/iris_prod"
        url_psycopg2 = "postgresql+psycopg2://iris_user:secret_pass@db.example.com:5432/iris_prod"
        self.assertEqual(normalize_database_url(url_psycopg), url_psycopg)
        self.assertEqual(normalize_database_url(url_psycopg2), url_psycopg2)

    def test_03_jdbc_postgresql_url_converted_correctly(self) -> None:
        """3. JDBC PostgreSQL URL is converted correctly to postgresql://."""
        jdbc_url = "jdbc:postgresql://db.example.com:5432/iris_prod"
        expected = "postgresql://db.example.com:5432/iris_prod"
        self.assertEqual(normalize_database_url(jdbc_url), expected)

    def test_04_jdbc_url_with_query_parameters_preserves_them(self) -> None:
        """4. JDBC URL with query parameters preserves them."""
        jdbc_url = (
            "jdbc:postgresql://ep-pooler.us-east-2.aws.neon.tech/neondb"
            "?user=neondb_owner&password=secret_password&sslmode=require&channelBinding=require"
        )
        expected = (
            "postgresql://ep-pooler.us-east-2.aws.neon.tech/neondb"
            "?user=neondb_owner&password=secret_password&sslmode=require&channelBinding=require"
        )
        self.assertEqual(normalize_database_url(jdbc_url), expected)

    def test_05_missing_or_empty_database_url_fails_clearly(self) -> None:
        """5. Missing/empty DATABASE_URL fails clearly with ValueError."""
        with self.assertRaises(ValueError) as ctx_empty:
            normalize_database_url("")
        self.assertIn("DATABASE_URL must be a non-empty string", str(ctx_empty.exception))

        with self.assertRaises(ValueError) as ctx_ws:
            normalize_database_url("   ")
        self.assertIn("DATABASE_URL must be a non-empty string", str(ctx_ws.exception))

        with self.assertRaises(ValueError):
            normalize_database_url(None)  # type: ignore[arg-type]

    def test_06_unsupported_database_url_scheme_fails_clearly(self) -> None:
        """6. Unsupported database URL scheme fails clearly."""
        unsupported_urls = [
            "mysql://user:pass@localhost:3306/db",
            "oracle://user:pass@localhost:1521/db",
            "http://example.com/db",
            "redis://localhost:6379/0",
        ]
        for bad_url in unsupported_urls:
            with self.subTest(bad_url=bad_url):
                with self.assertRaises(ValueError) as ctx:
                    normalize_database_url(bad_url)
                self.assertIn("Unsupported database URL scheme", str(ctx.exception))

    def test_07_credentials_not_exposed_in_error_messages(self) -> None:
        """7. Credentials are not exposed in error messages."""
        secret = "SuperSecretP@ssword123!"
        url_with_secret = f"mysql://dbuser:{secret}@localhost:3306/db"
        with self.assertRaises(ValueError) as ctx:
            normalize_database_url(url_with_secret)
        err_msg = str(ctx.exception)
        self.assertNotIn(secret, err_msg)
        self.assertIn("***", err_msg)

        # Also test query parameter credential masking in sanitizer
        sanitized = sanitize_database_url(f"jdbc:mysql://host/db?password={secret}")
        self.assertNotIn(secret, sanitized)
        self.assertIn("***", sanitized)

    def test_08_sqlalchemy_can_parse_normalized_url(self) -> None:
        """8. SQLAlchemy make_url can parse the normalized URL."""
        jdbc_url = (
            "jdbc:postgresql://ep-pooler.us-east-2.aws.neon.tech/neondb"
            "?user=neondb_owner&password=secret_pass&sslmode=require"
        )
        normalized = normalize_database_url(jdbc_url)
        parsed = make_url(normalized)
        self.assertEqual(parsed.drivername, "postgresql")
        self.assertEqual(parsed.host, "ep-pooler.us-east-2.aws.neon.tech")
        self.assertEqual(parsed.database, "neondb")
        self.assertEqual(parsed.query["sslmode"], "require")
        self.assertEqual(parsed.query["user"], "neondb_owner")

    def test_09_existing_create_db_engine_behavior_remains_compatible(self) -> None:
        """9. Existing create_db_engine() behavior remains compatible."""
        # SQLite in-memory engine creation
        engine = create_db_engine("sqlite:///:memory:")
        self.assertIsNotNone(engine)
        self.assertEqual(engine.name, "sqlite")

        # normalize_db_url backwards compatibility helper
        self.assertEqual(
            normalize_db_url("jdbc:postgresql://host:5432/db"),
            "postgresql://host:5432/db",
        )

    def test_10_environment_configuration_initializes_engine_without_parsing_failure(self) -> None:
        """10. Environment configuration can initialize the database engine without import-time parsing failure."""
        jdbc_url = (
            "jdbc:postgresql://ep-pooler.us-east-2.aws.neon.tech/neondb"
            "?user=neondb_owner&password=testpass&sslmode=require"
        )
        with patch.dict(os.environ, {"DATABASE_URL": jdbc_url}):
            s = Settings()
            self.assertTrue(s.DATABASE_URL.startswith("postgresql://"))
            self.assertFalse(s.DATABASE_URL.startswith("jdbc:"))
            # Engine creation parses normalized URL without ArgumentError
            eng = create_db_engine(s.DATABASE_URL)
            self.assertIsNotNone(eng)
            self.assertEqual(eng.name, "postgresql")

    def test_11_create_db_engine_postgresql_scheme_uses_psycopg2_fallback(self) -> None:
        """11. create_db_engine with bare postgresql:// or postgres:// routes to psycopg2 driver without ModuleNotFoundError."""
        url = "postgresql://iris_user:secret_pass@db.example.com:5432/iris_prod"
        eng = create_db_engine(url)
        self.assertIsNotNone(eng)
        self.assertEqual(eng.name, "postgresql")
        self.assertEqual(eng.driver, "psycopg2")

        # Also test legacy postgres://
        legacy_url = "postgres://iris_user:secret_pass@db.example.com:5432/iris_prod"
        eng_legacy = create_db_engine(legacy_url)
        self.assertIsNotNone(eng_legacy)
        self.assertEqual(eng_legacy.name, "postgresql")
        self.assertEqual(eng_legacy.driver, "psycopg2")


def test_sqlite_engine_creation() -> None:
    """Verify SQLite engine creates properly."""
    engine = create_db_engine("sqlite:///:memory:")
    assert engine is not None


def test_check_database_connection_with_live_session(db_session: Session) -> None:
    """Verify check_database_connection returns connected for active session."""
    is_ok, msg = check_database_connection(db_session)
    assert is_ok is True
    assert msg == "connected"
