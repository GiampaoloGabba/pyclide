"""Unit tests for Pydantic models."""

import pytest
from pydantic import ValidationError

from pyclide_server.models import (
    DefsRequest, RefsRequest, HoverRequest, RenameRequest,
    OccurrencesRequest, ExtractMethodRequest, ExtractVarRequest,
    OrganizeImportsRequest, MoveRequest, HealthResponse,
    LocationsResponse, HoverInfo, PatchesResponse, Location
)


@pytest.mark.unit
class TestModels:
    """Test Pydantic model validation."""

    def test_defs_request_validation(self):
        """DefsRequest validates required fields."""
        # Valid request
        req = DefsRequest(file="test.py", line=10, col=5, root="/workspace")
        assert req.file == "test.py"
        assert req.line == 10
        assert req.col == 5
        assert req.root == "/workspace"

        # Missing required fields
        with pytest.raises(ValidationError):
            DefsRequest(file="test.py", line=10)  # missing col and root

    def test_rename_request_validation(self):
        """RenameRequest validates required fields."""
        # Valid request
        req = RenameRequest(
            file="test.py", line=10, col=5, new_name="new_func", root="/workspace"
        )
        assert req.new_name == "new_func"

        # Missing new_name
        with pytest.raises(ValidationError):
            RenameRequest(file="test.py", line=10, col=5, root="/workspace")

    def test_extract_var_request_optional_fields(self):
        """ExtractVarRequest handles optional column fields."""
        # With all fields
        req = ExtractVarRequest(
            file="test.py",
            start_line=10,
            end_line=10,
            start_col=5,
            end_col=15,
            var_name="temp",
            root="/workspace"
        )
        assert req.start_col == 5
        assert req.end_col == 15

        # Without optional columns
        req2 = ExtractVarRequest(
            file="test.py",
            start_line=10,
            var_name="temp",
            root="/workspace"
        )
        assert req2.start_col is None
        assert req2.end_col is None
        assert req2.end_line is None

    def test_health_response_serialization(self):
        """HealthResponse serializes correctly."""
        resp = HealthResponse(
            status="ok",
            workspace="/workspace",
            uptime=123.45,
            requests=10,
            cache_size=5,
            cache_invalidations=2
        )

        data = resp.model_dump()
        assert data["status"] == "ok"
        assert data["uptime"] == 123.45
        assert data["requests"] == 10
        assert data["cache_invalidations"] == 2

    def test_location_model(self):
        """Location model validates correctly."""
        # Basic location
        loc = Location(file="test.py", line=10, column=5)
        assert loc.file == "test.py"
        assert loc.line == 10
        assert loc.column == 5
        assert loc.end_line is None

        # With end positions
        loc2 = Location(
            file="test.py",
            line=10,
            column=5,
            end_line=10,
            end_column=20
        )
        assert loc2.end_line == 10
        assert loc2.end_column == 20

    def test_locations_response_with_empty_list(self):
        """LocationsResponse handles empty locations."""
        resp = LocationsResponse(locations=[])
        assert resp.locations == []
        assert len(resp.locations) == 0

    def test_patches_response_with_empty_dict(self):
        """PatchesResponse handles empty patches."""
        resp = PatchesResponse(patches={})
        assert resp.patches == {}
        assert len(resp.patches) == 0

    def test_hover_info_all_optional(self):
        """HoverInfo handles all optional fields."""
        # Empty hover info
        info = HoverInfo()
        assert info.name is None
        assert info.type is None
        assert info.signature is None
        assert info.docstring is None

        # Partial info
        info2 = HoverInfo(name="func", type="function")
        assert info2.name == "func"
        assert info2.type == "function"
        assert info2.signature is None

    def test_extract_method_request_validation(self):
        """ExtractMethodRequest validates line ranges."""
        req = ExtractMethodRequest(
            file="test.py",
            start_line=10,
            end_line=15,
            method_name="extracted_method",
            root="/workspace"
        )
        assert req.start_line == 10
        assert req.end_line == 15
        assert req.method_name == "extracted_method"

        # Missing method_name
        with pytest.raises(ValidationError):
            ExtractMethodRequest(
                file="test.py",
                start_line=10,
                end_line=15,
                root="/workspace"
            )

    def test_occurrences_request_validation(self):
        """OccurrencesRequest validates correctly."""
        req = OccurrencesRequest(
            file="test.py",
            line=10,
            col=5,
            root="/workspace"
        )
        assert req.file == "test.py"
        assert req.line == 10
        assert req.col == 5

    def test_organize_imports_request_validation(self):
        """OrganizeImportsRequest validates correctly."""
        req = OrganizeImportsRequest(
            file="test.py",
            root="/workspace"
        )
        assert req.file == "test.py"
        assert req.root == "/workspace"

        # Missing file
        with pytest.raises(ValidationError):
            OrganizeImportsRequest(root="/workspace")
