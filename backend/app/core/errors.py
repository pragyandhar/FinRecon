class FinReconError(Exception):
    """Base class for explicit, categorized FinRecon failures.

    Every stage should raise one of these rather than letting a bare
    exception surface, so the job record and the API response can carry
    an honest, actionable error code instead of a stack trace.
    """

    code = "INTERNAL_ERROR"

    def __init__(self, message: str, *, details: dict | None = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def to_dict(self) -> dict:
        return {"code": self.code, "message": self.message, "details": self.details}


class UnsupportedFileTypeError(FinReconError):
    code = "UNSUPPORTED_FILE_TYPE"


class FileTooLargeError(FinReconError):
    code = "FILE_TOO_LARGE"


class ExtractionFailedError(FinReconError):
    code = "EXTRACTION_FAILED"


class SchemaUncertainError(FinReconError):
    code = "SCHEMA_UNCERTAIN"


class InvalidReconciliationPlanError(FinReconError):
    code = "INVALID_RECONCILIATION_PLAN"


class UnsupportedOperationError(FinReconError):
    code = "UNSUPPORTED_OPERATION"


class PlanExecutionError(FinReconError):
    code = "PLAN_EXECUTION_FAILED"


class ModelExecutionFailedError(FinReconError):
    code = "MODEL_EXECUTION_FAILED"


class UnresolvedExceptionError(FinReconError):
    code = "UNRESOLVED_EXCEPTION"


class JobNotFoundError(FinReconError):
    code = "JOB_NOT_FOUND"
