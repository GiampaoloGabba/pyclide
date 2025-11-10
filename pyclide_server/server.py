"""
PyCLIDE Server - FastAPI server with hot cache for Jedi and Rope.
"""

import asyncio
import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Dict, Optional

import jedi
from fastapi import FastAPI, HTTPException

from .file_watcher import PythonFileWatcher
from .health import HealthMonitor
from .jedi_helpers import jedi_to_locations
from .models import (
    DefsRequest, RefsRequest, HoverRequest, RenameRequest,
    OccurrencesRequest, ExtractMethodRequest, ExtractVarRequest,
    OrganizeImportsRequest, MoveRequest, HealthResponse, LocationsResponse, HoverInfo, PatchesResponse,
    Location
)
from .rope_engine import RopeEngine

# Get logger (configuration done in __main__.py)
logger = logging.getLogger(__name__)


class PyCLIDEServer:
    """
    High-performance Python semantic analysis server with hot RAM cache.

    Architecture:
    - One server per workspace (project root)
    - Hot cache: Jedi Scripts and Rope Project kept in RAM
    - File watcher: Invalidates cache on file changes (added in Phase 3)
    - Auto-shutdown: Closes after inactivity timeout (added in Phase 4)
    """

    def __init__(self, workspace_root: str, port: int):
        """
        Initialize server for a workspace.

        Args:
            workspace_root: Absolute path to project root
            port: Port to bind the server to
        """
        self.root = Path(workspace_root).resolve()
        self.port = port

        # Hot state in RAM
        self.jedi_cache: Dict[str, jedi.Script] = {}
        self.rope_engine: Optional[RopeEngine] = None

        # Statistics
        self.start_time = time.time()
        self.last_activity = time.time()
        self.request_count = 0
        self.cache_invalidations = 0

        # File watcher for cache invalidation
        self.file_watcher: Optional[PythonFileWatcher] = None

        # Health monitor for auto-shutdown
        self.health_monitor: Optional[HealthMonitor] = None

        # Define lifespan context manager for startup/shutdown
        @asynccontextmanager
        async def lifespan(app: FastAPI):
            # Startup
            self.health_monitor = HealthMonitor(self)
            asyncio.create_task(self.health_monitor.start())
            logger.info("Background tasks started")

            yield  # Application runs here

            # Shutdown
            logger.info("Server shutting down...")
            if self.health_monitor:
                self.health_monitor.stop()
            self._stop_file_watcher()

        # Create FastAPI app with lifespan
        self.app = FastAPI(
            title="PyCLIDE Server",
            description="High-performance Python semantic analysis server",
            version="1.0.0",
            lifespan=lifespan
        )

        # Setup routes
        self._setup_routes()

        logger.info(f"Initialized server for workspace: {self.root}")

    def _get_rope_engine(self) -> RopeEngine:
        """Get or create Rope engine (lazy initialization)."""
        if self.rope_engine is None:
            logger.info("Initializing Rope project...")
            self.rope_engine = RopeEngine(self.root)
        return self.rope_engine

    def _get_cached_script(self, file_path: str) -> jedi.Script:
        """
        Get Jedi Script from hot cache or create new one.

        Args:
            file_path: Relative path from workspace root

        Returns:
            Cached or newly created Jedi Script
        """
        abs_path = str((self.root / file_path).resolve())

        if abs_path not in self.jedi_cache:
            logger.debug(f"Cache miss: creating Jedi Script for {file_path}")
            self.jedi_cache[abs_path] = jedi.Script(path=abs_path)
        else:
            logger.debug(f"Cache hit: using cached Jedi Script for {file_path}")

        return self.jedi_cache[abs_path]

    def _invalidate_cache(self, file_path: str):
        """
        Invalidate cache for a file.
        Called by file watcher when file changes (Phase 3).

        Args:
            file_path: Relative path from workspace root
        """
        abs_path = str((self.root / file_path).resolve())

        # Invalidate Jedi cache
        if abs_path in self.jedi_cache:
            logger.info(f"Invalidating Jedi cache for {file_path}")
            del self.jedi_cache[abs_path]

        # Rope auto-detects changes, force validation
        if self.rope_engine is not None:
            logger.info("Validating Rope project after file change")
            self.rope_engine.project.validate()

        self.cache_invalidations += 1

    def _update_activity(self):
        """Update last activity timestamp and request count."""
        self.last_activity = time.time()
        self.request_count += 1

    def _setup_routes(self):
        """Setup FastAPI routes."""

        @self.app.get("/health", response_model=HealthResponse)
        async def health_check():
            """Health check endpoint."""
            return HealthResponse(
                status="ok",
                workspace=str(self.root),
                uptime=time.time() - self.start_time,
                requests=self.request_count,
                cache_size=len(self.jedi_cache),
                cache_invalidations=self.cache_invalidations
            )

        @self.app.post("/defs", response_model=LocationsResponse)
        async def goto_definition(req: DefsRequest):
            """Go to definition using Jedi."""
            try:
                self._update_activity()

                script = self._get_cached_script(req.file)
                results = script.goto(req.line, req.col)
                locations = jedi_to_locations(results)

                return LocationsResponse(
                    locations=[
                        Location(
                            file=loc["path"],
                            line=loc["line"],
                            column=loc["column"]
                        )
                        for loc in locations
                    ]
                )
            except ValueError as e:
                # Jedi raises ValueError for invalid coordinates (e.g., empty lines)
                # Return empty results instead of 500 error
                logger.debug(f"Invalid position in goto_definition: {e}")
                return LocationsResponse(locations=[])
            except Exception as e:
                logger.error(f"Error in goto_definition: {e}", exc_info=True)
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.post("/refs", response_model=LocationsResponse)
        async def find_references(req: RefsRequest):
            """Find references using Jedi."""
            try:
                self._update_activity()

                script = self._get_cached_script(req.file)
                results = script.get_references(req.line, req.col)
                locations = jedi_to_locations(results)

                return LocationsResponse(
                    locations=[
                        Location(
                            file=loc["path"],
                            line=loc["line"],
                            column=loc["column"]
                        )
                        for loc in locations
                    ]
                )
            except ValueError as e:
                # Jedi raises ValueError for invalid coordinates (e.g., empty lines)
                # Return empty results instead of 500 error
                logger.debug(f"Invalid position in find_references: {e}")
                return LocationsResponse(locations=[])
            except Exception as e:
                logger.error(f"Error in find_references: {e}", exc_info=True)
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.post("/hover", response_model=HoverInfo)
        async def hover_info(req: HoverRequest):
            """Get hover information using Jedi."""
            try:
                self._update_activity()

                script = self._get_cached_script(req.file)
                results = script.help(req.line, req.col)

                # Extract hover information
                info = HoverInfo()
                if results:
                    # Get the first result
                    result = results[0] if isinstance(results, list) else results
                    info.name = getattr(result, 'name', None)
                    info.type = getattr(result, 'type', None)

                    # Get signature if available
                    signatures = script.get_signatures(req.line, req.col)
                    if signatures:
                        sig = signatures[0]
                        info.signature = str(sig)

                    # Get docstring
                    info.docstring = getattr(result, 'docstring', lambda: None)()

                return info
            except ValueError as e:
                # Jedi raises ValueError for invalid coordinates (e.g., empty lines)
                # Return empty info instead of 500 error
                logger.debug(f"Invalid position in hover_info: {e}")
                return HoverInfo()
            except Exception as e:
                logger.error(f"Error in hover_info: {e}", exc_info=True)
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.post("/occurrences", response_model=LocationsResponse)
        async def semantic_occurrences(req: OccurrencesRequest):
            """Find semantic occurrences using Rope."""
            try:
                self._update_activity()

                engine = self._get_rope_engine()
                results = engine.occurrences(req.file, req.line, req.col)

                return LocationsResponse(
                    locations=[
                        Location(
                            file=loc["path"],
                            line=loc["line"],
                            column=loc["column"]
                        )
                        for loc in results
                    ]
                )
            except Exception as e:
                logger.error(f"Error in semantic_occurrences: {e}", exc_info=True)
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.post("/rename", response_model=PatchesResponse)
        async def semantic_rename(req: RenameRequest):
            """Semantic rename using Rope."""
            try:
                self._update_activity()

                engine = self._get_rope_engine()
                patches = engine.rename(req.file, req.line, req.col, req.new_name, req.output_format)

                return PatchesResponse(patches=patches, format=req.output_format)
            except Exception as e:
                logger.error(f"Error in semantic_rename: {e}", exc_info=True)
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.post("/extract-method", response_model=PatchesResponse)
        async def extract_method(req: ExtractMethodRequest):
            """Extract method refactoring using Rope."""
            try:
                self._update_activity()

                engine = self._get_rope_engine()
                patches = engine.extract_method(
                    req.file,
                    req.start_line,
                    req.end_line,
                    req.method_name,
                    req.output_format
                )

                return PatchesResponse(patches=patches, format=req.output_format)
            except Exception as e:
                logger.error(f"Error in extract_method: {e}", exc_info=True)
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.post("/extract-var", response_model=PatchesResponse)
        async def extract_variable(req: ExtractVarRequest):
            """Extract variable refactoring using Rope."""
            try:
                self._update_activity()

                engine = self._get_rope_engine()
                patches = engine.extract_variable(
                    req.file,
                    req.start_line,
                    req.end_line or req.start_line,
                    req.var_name,
                    start_col=req.start_col,
                    end_col=req.end_col,
                    output_format=req.output_format
                )

                return PatchesResponse(patches=patches, format=req.output_format)
            except Exception as e:
                logger.error(f"Error in extract_variable: {e}", exc_info=True)
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.post("/organize-imports", response_model=PatchesResponse)
        async def organize_imports(req: OrganizeImportsRequest):
            """Organize imports using Rope."""
            try:
                self._update_activity()

                engine = self._get_rope_engine()
                file_path = self.root / req.file
                patches = engine.organize_imports(file_path, convert_froms=False, output_format=req.output_format)

                return PatchesResponse(patches=patches, format=req.output_format)
            except Exception as e:
                logger.error(f"Error in organize_imports: {e}", exc_info=True)
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.post("/move", response_model=PatchesResponse)
        async def move_symbol(req: MoveRequest):
            """Move symbol/module using Rope."""
            try:
                self._update_activity()

                engine = self._get_rope_engine()
                # Move symbol at specified line/col, or entire file if not specified
                patches = engine.move(req.file, req.dest_file, req.line, req.col, req.output_format)

                return PatchesResponse(patches=patches, format=req.output_format)
            except Exception as e:
                logger.error(f"Error in move_symbol: {e}", exc_info=True)
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.post("/shutdown")
        async def shutdown():
            """Graceful shutdown endpoint."""
            logger.info("Shutdown requested via API")
            if self.health_monitor:
                await self.health_monitor._graceful_shutdown()
            return {"status": "shutting down"}

    def _start_file_watcher(self):
        """Initialize and start file watcher."""
        try:
            self.file_watcher = PythonFileWatcher(self.root, self._invalidate_cache)
            self.file_watcher.start()
            logger.info("File watcher started")
        except Exception as e:
            logger.warning(f"Failed to start file watcher: {e}")
            self.file_watcher = None

    def _stop_file_watcher(self):
        """Stop file watcher."""
        if self.file_watcher:
            try:
                self.file_watcher.stop()
                logger.info("File watcher stopped")
            except Exception as e:
                logger.error(f"Error stopping file watcher: {e}")

    def start(self):
        """Start the server (blocking)."""
        import uvicorn

        # Start file watcher
        self._start_file_watcher()

        logger.info(f"Starting server on port {self.port}...")
        try:
            uvicorn.run(
                self.app,
                host="127.0.0.1",
                port=self.port,
                log_level="warning"
            )
        finally:
            # Cleanup on shutdown
            self._stop_file_watcher()
