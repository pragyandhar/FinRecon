from pydantic import BaseModel, Field

from app.models.enums import FieldRole, SemanticType


class SchemaField(BaseModel):
    name: str
    semantic_type: SemanticType
    role: FieldRole
    nullable: bool = True
    confidence: float = 1.0


class SchemaDataset(BaseModel):
    dataset_id: str
    purpose: str
    fields: list[SchemaField]


class SchemaJSON(BaseModel):
    """Output of the schema-understanding stage. Machine-readable
    contract between schema understanding and canonical mapping."""

    job_id: str
    datasets: list[SchemaDataset]


class CanonicalField(BaseModel):
    canonical_name: str
    raw_field: str


class CanonicalMapping(BaseModel):
    """dataset_id -> {canonical_field_name: raw_field_name}.
    Never rewrites the original files; only a semantic lookup layer."""

    job_id: str
    mapping: dict[str, dict[str, str]] = Field(default_factory=dict)
