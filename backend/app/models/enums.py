from enum import StrEnum


class JobStatus(StrEnum):
    UPLOADED = "UPLOADED"
    EXTRACTING = "EXTRACTING"
    UNDERSTANDING_SCHEMA = "UNDERSTANDING_SCHEMA"
    PLANNING = "PLANNING"
    VALIDATING_PLAN = "VALIDATING_PLAN"
    RECONCILING = "RECONCILING"
    INVESTIGATING = "INVESTIGATING"
    GENERATING_REPORT = "GENERATING_REPORT"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class OperationType(StrEnum):
    JOIN = "JOIN"
    COMPARE = "COMPARE"
    MISSING = "MISSING"
    DUPLICATE = "DUPLICATE"
    FILTER = "FILTER"
    GROUP = "GROUP"
    AGGREGATE = "AGGREGATE"


class ComparisonType(StrEnum):
    EQUALS = "EQUALS"
    NOT_EQUALS = "NOT_EQUALS"
    TOLERANCE = "TOLERANCE"
    DATE_DIFF = "DATE_DIFF"
    DATE_WITHIN = "DATE_WITHIN"


class JoinType(StrEnum):
    INNER = "inner"
    LEFT_OUTER = "left_outer"
    FULL_OUTER = "full_outer"


class FilterOperator(StrEnum):
    EQ = "=="
    NE = "!="
    GT = ">"
    LT = "<"
    GE = ">="
    LE = "<="


class AggregateFunction(StrEnum):
    SUM = "SUM"
    COUNT = "COUNT"
    AVG = "AVG"


class RecordStatus(StrEnum):
    MATCHED = "MATCHED"
    MISMATCHED = "MISMATCHED"
    EXCEPTION = "EXCEPTION"
    UNRESOLVED = "UNRESOLVED"


class SemanticType(StrEnum):
    IDENTIFIER = "identifier"
    CURRENCY_AMOUNT = "currency_amount"
    DATE = "date"
    STATUS = "status"
    CUSTOMER_REFERENCE = "customer_reference"
    TEXT = "text"
    OTHER = "other"


class FieldRole(StrEnum):
    PRIMARY_KEY = "primary_key"
    FOREIGN_KEY = "foreign_key"
    MEASURE = "measure"
    ATTRIBUTE = "attribute"
