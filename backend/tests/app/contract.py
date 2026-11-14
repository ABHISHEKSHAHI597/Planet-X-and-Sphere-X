"""Validate a JSON body against a component schema of the app's own /openapi.json (workflow.md §7.3)."""
from jsonschema import Draft202012Validator


def validator(openapi: dict, name: str) -> Draft202012Validator:
    doc = {"$schema": "https://json-schema.org/draft/2020-12/schema", "components": openapi["components"],
           "$ref": f"#/components/schemas/{name}"}
    return Draft202012Validator(doc)


def check(openapi: dict, name: str, body: object) -> None:
    errs = sorted(validator(openapi, name).iter_errors(body), key=lambda e: list(e.path))
    assert not errs, f"{name}: " + "; ".join(f"{list(e.path)}: {e.message}" for e in errs[:5])
