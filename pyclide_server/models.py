"""
Pydantic models for request/response validation.
"""

from typing import Optional, List, Dict, Literal

from pydantic import BaseModel, Field


class Location(BaseModel):
    """Represents a code location."""
    file: str
    line: int
    column: int
    end_line: Optional[int] = None
    end_column: Optional[int] = None


class DefsRequest(BaseModel):
    """Request for go-to-definition."""
    file: str = Field(..., description="Relative path to file from workspace root")
    line: int = Field(..., description="1-based line number")
    col: int = Field(..., description="1-based column number")
    root: str = Field(..., description="Workspace root path")


class RefsRequest(BaseModel):
    """Request for find-references."""
    file: str = Field(..., description="Relative path to file from workspace root")
    line: int = Field(..., description="1-based line number")
    col: int = Field(..., description="1-based column number")
    root: str = Field(..., description="Workspace root path")


class HoverRequest(BaseModel):
    """Request for hover information."""
    file: str = Field(..., description="Relative path to file from workspace root")
    line: int = Field(..., description="1-based line number")
    col: int = Field(..., description="1-based column number")
    root: str = Field(..., description="Workspace root path")


class RenameRequest(BaseModel):
    """Request for semantic rename."""
    file: str = Field(..., description="Relative path to file from workspace root")
    line: int = Field(..., description="1-based line number")
    col: int = Field(..., description="1-based column number")
    new_name: str = Field(..., description="New name for the symbol")
    root: str = Field(..., description="Workspace root path")
    output_format: Literal["diff", "full"] = Field("diff", description="Output format: 'diff' for unified diffs, 'full' for complete file contents")


class OccurrencesRequest(BaseModel):
    """Request for semantic occurrences."""
    file: str = Field(..., description="Relative path to file from workspace root")
    line: int = Field(..., description="1-based line number")
    col: int = Field(..., description="1-based column number")
    root: str = Field(..., description="Workspace root path")


class ExtractMethodRequest(BaseModel):
    """Request for extract method refactoring."""
    file: str = Field(..., description="Relative path to file from workspace root")
    start_line: int = Field(..., description="Start line (1-based)")
    end_line: int = Field(..., description="End line (1-based)")
    method_name: str = Field(..., description="Name for the extracted method")
    root: str = Field(..., description="Workspace root path")
    output_format: Literal["diff", "full"] = Field("diff", description="Output format: 'diff' for unified diffs, 'full' for complete file contents")


class ExtractVarRequest(BaseModel):
    """Request for extract variable refactoring."""
    file: str = Field(..., description="Relative path to file from workspace root")
    start_line: int = Field(..., description="Start line (1-based)")
    end_line: Optional[int] = Field(None, description="End line (1-based)")
    start_col: Optional[int] = Field(None, description="Start column (1-based)")
    end_col: Optional[int] = Field(None, description="End column (1-based)")
    var_name: str = Field(..., description="Name for the extracted variable")
    root: str = Field(..., description="Workspace root path")
    output_format: Literal["diff", "full"] = Field("diff", description="Output format: 'diff' for unified diffs, 'full' for complete file contents")


class OrganizeImportsRequest(BaseModel):
    """Request for organize imports."""
    file: str = Field(..., description="Relative path to file from workspace root")
    root: str = Field(..., description="Workspace root path")
    output_format: Literal["diff", "full"] = Field("diff", description="Output format: 'diff' for unified diffs, 'full' for complete file contents")


class MoveRequest(BaseModel):
    """Request for move symbol/module."""
    file: str = Field(..., description="Relative path to file from workspace root")
    line: int = Field(..., description="1-based line number")
    col: int = Field(..., description="1-based column number")
    dest_file: str = Field(..., description="Destination file path")
    root: str = Field(..., description="Workspace root path")
    output_format: Literal["diff", "full"] = Field("diff", description="Output format: 'diff' for unified diffs, 'full' for complete file contents")


class ListRequest(BaseModel):
    """Request for list symbols."""
    path: str = Field(..., description="File or directory path")
    root: str = Field(..., description="Workspace root path")


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    workspace: str
    uptime: float
    requests: int
    cache_size: int
    cache_invalidations: int = 0


class LocationsResponse(BaseModel):
    """Response containing list of locations."""
    locations: List[Location]


class HoverInfo(BaseModel):
    """Hover information response."""
    name: Optional[str] = None
    type: Optional[str] = None
    signature: Optional[str] = None
    docstring: Optional[str] = None


class PatchesResponse(BaseModel):
    """Response containing file patches."""
    patches: Dict[str, str] = Field(..., description="Map of file path to content (diff or full)")
    format: Literal["diff", "full"] = Field("diff", description="Format of patches: 'diff' for unified diffs, 'full' for complete file contents")


class SymbolInfo(BaseModel):
    """Symbol information."""
    name: str
    kind: str
    line: int
    file: str


class SymbolsResponse(BaseModel):
    """Response containing symbols."""
    symbols: List[SymbolInfo]
